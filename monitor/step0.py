"""Step 0 of the labelling cascade (issue #10): rules that discard noise-only change records.

detect.py already masks noise inside a page (cookie banners, countdowns, donation totals, relative dates,
copyright years, re-encoded links). These rules handle noise that only shows up when two days are
compared, found in the 5-vs-6 Oct real-page check (docs/parser_adoption_2026-10-06.md):

  counters        a short line differs only in a number, next to a count word ("12 likes", "Cart (2)")
  calendar_dates  on a calendar or events page, lines and links differ only in dates
  social_feed     links to individual social-media posts, and their CDN images (embedded feeds)
  signed_media    images on hosts that sign their URLs per request (Google, Facebook, Instagram, X)
  url_tokens      a line or link differs only in a one-time token in a URL (WordPress nonces, signatures)
  site_rule       a pattern listed for one site in monitor/site_noise.csv

A "related posts" sidebar that changes on every page of a site is folded into one site-wide record by
changes.py rather than discarded here: a new post is a routine change, not noise.

Rules remove noise ITEMS from a record. A record is discarded only when nothing is left, and the reasons
are kept in record["step0"]; discarded records stay in the day's file. Added and removed pages are
never discarded.
"""
import csv, os, re
from collections import Counter

COUNT_WORDS = re.compile(r"\b(likes?|comments?|shares?|followers?|following|views?|retweets?|reposts?|replies|reactions?|"
                         r"cart|bag|basket|items?|sold|in stock|signatures?|signers?|members?|subscribers?|"
                         r"attending|going|interested|rsvps?)\b", re.I)
COUNTER_MAX = 60                  # a counter is a short label, not a sentence
NUM = re.compile(r"\$?\d[\d,.]*[kKmM]?")
MONTHS = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
DAYS = r"mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?"
DATE_WORDS = re.compile(rf"\b(?:{MONTHS}|{DAYS}|today|tomorrow|tonight)\b\.?", re.I)
CALENDAR_URL = re.compile(r"/(events?|calendar|schedule)(/|\?|$)|[?&](tribe-bar-date|eventDisplay|date|day|month|range)=", re.I)
SOCIAL_POST = re.compile(r"^https?://(www\.)?(instagram\.com/(p|reel|tv)/|facebook\.com/.+/(posts|photos|videos)/|"
                         r"facebook\.com/(photo|permalink|story)\.php|(x|twitter)\.com/[^/]+/status/|tiktok\.com/@[^/]+/video/|"
                         r"youtube\.com/(watch|shorts/)|youtu\.be/|threads\.net/@[^/]+/post/)", re.I)
SIGNED_HOSTS = re.compile(r"(googleusercontent\.com|ggpht\.com|fbcdn\.net|cdninstagram\.com|twimg\.com|ytimg\.com|"
                          r"tiktokcdn\.com|licdn\.com)", re.I)


def _host(u):
    m = re.match(r"^(?:[a-z]+:)?//([^/?#]+)", u or "", re.I)
    return m.group(1).lower().removeprefix("www.") if m else ""


def _pair_off(removed, added, key):
    """remove pairs whose key() is equal; returns (removed_left, added_left, n_paired)"""
    a = Counter(key(x) for x in added)
    left_r, used = [], Counter()
    for x in removed:
        k = key(x)
        if k is not None and a[k] - used[k] > 0:
            used[k] += 1
        else:
            left_r.append(x)
    need, left_a = Counter(used), []
    for x in added:
        k = key(x)
        if k is not None and need[k] > 0:
            need[k] -= 1
        else:
            left_a.append(x)
    return left_r, left_a, sum(used.values())


def _counter_key(line):
    return NUM.sub("#", line) if len(line) <= COUNTER_MAX and COUNT_WORDS.search(line) else None


URL_TOKEN = re.compile(r"([?&;](?:_?wpnonce|nonce|_?token|sig|signature|expires|hash|ver|v|_|sid|session|redirect_to)=)[^&\s\"]+", re.I)
LONG_HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)


def _token_key(s):
    k = LONG_HEX.sub("~", URL_TOKEN.sub(r"\1~", s))
    return k if k != s else None


def _date_key(s):
    return DATE_WORDS.sub("@", NUM.sub("#", s))


def load_site_rules(path):
    rules = {}
    if path and os.path.exists(path):
        for r in csv.DictReader(open(path, newline="")):
            if r.get("site_id") and r.get("pattern"):
                rules.setdefault(r["site_id"], []).append((r.get("field") or "any", re.compile(r["pattern"], re.I),
                                                           r.get("reason") or "site rule"))
    return rules


def apply(rec, site_rules=None):
    """sets rec["step0"] = {"discard": bool, "reasons": [...], "kept": {...counts left...}}; returns rec"""
    if rec["kind"] not in ("changed", "sitewide"):
        rec["step0"] = {"discard": False, "reasons": [], "kept": "page " + rec["kind"]}
        return rec
    tr, ta = list(rec["text"]["removed"]), list(rec["text"]["added"])
    lr = [(l["text"], l["href"]) for l in rec["links"]["removed"]]
    la = [(l["text"], l["href"]) for l in rec["links"]["added"]]
    mr, ma = list(rec["media"]["removed"]), list(rec["media"]["added"])
    meta = dict(rec["meta"])
    reasons = Counter()
    page_host = _host(rec.get("url"))

    # site-specific patterns first (they are the most precise)
    for field, pat, why in (site_rules or {}).get(rec["site_id"], []):
        before = len(tr) + len(ta) + len(lr) + len(la) + len(mr) + len(ma)
        if field in ("any", "text"):
            tr = [x for x in tr if not pat.search(x)]; ta = [x for x in ta if not pat.search(x)]
        if field in ("any", "links"):
            lr = [x for x in lr if not (pat.search(x[0]) or pat.search(x[1]))]
            la = [x for x in la if not (pat.search(x[0]) or pat.search(x[1]))]
        if field in ("any", "media"):
            mr = [x for x in mr if not pat.search(x)]; ma = [x for x in ma if not pat.search(x)]
        n = before - (len(tr) + len(ta) + len(lr) + len(la) + len(mr) + len(ma))
        if n:
            reasons[f"site_rule: {why}"] += n

    tr, ta, n = _pair_off(tr, ta, _token_key)
    reasons["url_tokens"] += 2 * n
    lr, la, n = _pair_off(lr, la, lambda l: (l[0], _token_key(l[1])) if _token_key(l[1]) else None)
    reasons["url_tokens"] += 2 * n

    tr, ta, n = _pair_off(tr, ta, _counter_key)
    reasons["counters"] += 2 * n
    lr, la, n = _pair_off(lr, la, lambda l: (_counter_key(l[0]), l[1]) if _counter_key(l[0]) is not None else None)
    reasons["counters"] += 2 * n

    if CALENDAR_URL.search(rec.get("url") or ""):
        tr, ta, n = _pair_off(tr, ta, _date_key); reasons["calendar_dates"] += 2 * n
        lr, la, n = _pair_off(lr, la, lambda l: (_date_key(l[0]), _date_key(l[1]))); reasons["calendar_dates"] += 2 * n

    soc = [l for l in lr + la if SOCIAL_POST.search(l[1])]
    if soc:
        texts = Counter(l[0] for l in soc if l[0])
        lr = [l for l in lr if not SOCIAL_POST.search(l[1])]; la = [l for l in la if not SOCIAL_POST.search(l[1])]
        tr = [x for x in tr if not texts[x]]; ta = [x for x in ta if not texts[x]]
        reasons["social_feed"] += len(soc)

    keep_m = lambda m: not SIGNED_HOSTS.search(m.split("|")[0])
    n = len(mr) + len(ma)
    mr, ma = [m for m in mr if keep_m(m)], [m for m in ma if keep_m(m)]
    reasons["signed_media"] += n - len(mr) - len(ma)
    if "years_mentioned" in meta and not (tr or ta):
        meta.pop("years_mentioned")               # follows from the text; with no text change left it is noise

    kept = {"text": len(tr) + len(ta), "links": len(lr) + len(la), "media": len(mr) + len(ma), "meta": len(meta)}
    rec["step0"] = {"discard": not any(kept.values()), "reasons": sorted(k for k, v in reasons.items() if v), "kept": kept}
    return rec
