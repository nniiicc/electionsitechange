#!/usr/bin/env python3
"""Daily snapshot of 2026 candidate campaign homepages.

For each URL in the input CSV (columns: site_id, url, ...):
  fetch -> normalise -> write sites/<site_id>/{text.md, links.json, meta.json}
in a Git repository, then commit once. Git only records files whose normalised
content changed, so the repository history *is* the change log.

Volatile values (fetch time, response time, raw byte size) go to the daily log
logs/<date>.csv, never into the per-site files, so they cannot create false changes.
A failed fetch never overwrites the last good snapshot.

usage: python snapshot.py URLS.csv REPO_DIR [--limit N] [--workers 8] [--raw-dir DIR]
"""
import argparse, concurrent.futures as cf, csv, datetime as dt, gzip, hashlib, json, os, re
import subprocess, sys, threading, time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib import robotparser

import requests
import trafilatura

UA = "CampaignSiteMonitor/0.1 (nonpartisan research archive of 2026 candidate websites)"
TIMEOUT = 20
MAX_BYTES = 5_000_000
HOST_GAP_S = 1.0          # minimum spacing between requests to the same host

# ---------------------------------------------------------------- normalisation
NOISE_LINE = re.compile(
    r"^(\d+\s*(days?|hours?|hrs?|minutes?|mins?|seconds?|secs?)\b.*|"      # countdowns
    r".*\b(raised|of \$[\d,]+ goal|donors? so far)\b.*\$[\d,]+.*|"           # progress bars
    r"(©|copyright)\s*\d{4}.*|"                                              # footer year
    r"(accept|reject) (all )?cookies.*|this (web)?site uses cookies.*)$", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“(])")
TRACK_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|_ga|ref$|refcode|source$)", re.I)
DISCLAIMER = re.compile(r"(paid for by[^.\n]{3,140})", re.I)
YEAR = re.compile(r"\b(20[12]\d)\b")


class Meta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.desc, self.links, self._in_title = "", "", [], False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title": self._in_title = True
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description"):
            self.desc = self.desc or (a.get("content") or "").strip()
        elif tag == "a" and a.get("href"): self.links.append(a["href"].strip())
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
    def handle_data(self, d):
        if self._in_title: self.title += d


def norm_link(base, href):
    if href.startswith(("javascript:", "mailto:", "tel:", "#", "data:")): return None
    u = urlparse(urljoin(base, href))
    if u.scheme not in ("http", "https"): return None
    q = urlencode([(k, v) for k, v in parse_qsl(u.query) if not TRACK_PARAMS.match(k)])
    return urlunparse((u.scheme, u.netloc.lower().removeprefix("www."), u.path.rstrip("/") or "/", "", q, ""))


def normalise(html, final_url):
    text = trafilatura.extract(html, output_format="txt", include_comments=False,
                               include_tables=True, favor_recall=True) or ""
    lines = []
    for para in text.splitlines():
        para = " ".join(para.split())
        if not para: continue
        for s in SENT_SPLIT.split(para):
            s = s.strip()
            if s and not NOISE_LINE.match(s): lines.append(s)
    p = Meta()
    try: p.feed(html)
    except Exception: pass
    links = sorted({l for l in (norm_link(final_url, h) for h in p.links) if l})
    body = " ".join(lines)
    # The "Paid for by" disclaimer lives in the footer, which main-content extraction
    # removes, so search the whole visible page text for it.
    visible = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>", " ", html)
    m = DISCLAIMER.search(" ".join(visible.split()))
    meta = {"final_url": final_url,
            "title": " ".join(p.title.split()),
            "description": " ".join(p.desc.split()),
            "paid_for_by": " ".join(m.group(1).split()) if m else None,
            "years_mentioned": sorted(set(YEAR.findall(body)))}
    return "\n".join(lines) + ("\n" if lines else ""), links, meta


# ---------------------------------------------------------------- politeness
_robots, _robots_lock = {}, threading.Lock()
_last_hit, _hit_lock = {}, threading.Lock()

def robots_ok(sess, url):
    u = urlparse(url); key = f"{u.scheme}://{u.netloc}"
    with _robots_lock:
        rp = _robots.get(key)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            r = sess.get(key + "/robots.txt", timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        with _robots_lock: _robots[key] = rp
    return rp.can_fetch(UA, url)

def wait_turn(url):
    host = urlparse(url).netloc.lower()
    while True:
        with _hit_lock:
            now = time.monotonic(); last = _last_hit.get(host, 0)
            if now - last >= HOST_GAP_S:
                _last_hit[host] = now; return
        time.sleep(HOST_GAP_S - (now - last))


# ---------------------------------------------------------------- one site
_local = threading.local()
def session():
    if not hasattr(_local, "s"):
        s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept": "text/html,*/*;q=0.5"})
        _local.s = s
    return _local.s

def write_if_changed(path, data):
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old != data:
        with open(path, "wb") as f: f.write(data)
        return True
    return False

def do_site(row, repo, raw_dir, day):
    sid, url = row["site_id"], row["url"]
    rec = {"site_id": sid, "url": url, "status": "", "final_url": "", "bytes": 0,
           "text_chars": 0, "changed": False, "first_seen": False, "low_text": False,
           "error": "", "elapsed_s": 0.0}
    t0 = time.monotonic()
    s = session()
    try:
        if not robots_ok(s, url):
            rec["error"] = "robots_disallowed"; return rec
        wait_turn(url)
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        raw = r.raw.read(MAX_BYTES, decode_content=True); r.close()
        rec.update(status=r.status_code, final_url=r.url, bytes=len(raw))
        if r.status_code >= 400:
            rec["error"] = f"http_{r.status_code}"; return rec
        enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        html = raw.decode(enc, errors="replace")
        text, links, meta = normalise(html, r.url)
        rec["text_chars"] = len(text); rec["low_text"] = len(text) < 200
        d = os.path.join(repo, "sites", sid)
        rec["first_seen"] = not os.path.exists(d)
        os.makedirs(d, exist_ok=True)
        ch = write_if_changed(os.path.join(d, "text.md"), text.encode())
        ch |= write_if_changed(os.path.join(d, "links.json"), (json.dumps(links, indent=0) + "\n").encode())
        ch |= write_if_changed(os.path.join(d, "meta.json"), (json.dumps(meta, indent=1, sort_keys=True) + "\n").encode())
        rec["changed"] = ch
        if ch and raw_dir:                      # keep raw HTML only when content changed
            os.makedirs(os.path.join(raw_dir, day), exist_ok=True)
            with gzip.open(os.path.join(raw_dir, day, sid + ".html.gz"), "wb") as f: f.write(raw)
    except requests.exceptions.SSLError: rec["error"] = "ssl_error"
    except requests.exceptions.ConnectionError as e:
        rec["error"] = "dns_or_connect" if "resolve" in str(e).lower() or "Name or service" in str(e) else "connect_error"
    except requests.exceptions.Timeout: rec["error"] = "timeout"
    except Exception as e: rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        rec["elapsed_s"] = round(time.monotonic() - t0, 2)
    return rec


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls"); ap.add_argument("repo")
    ap.add_argument("--limit", type=int); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--raw-dir"); ap.add_argument("--summary", default="summary.json")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.urls)))
    if a.limit: rows = rows[:a.limit]
    os.makedirs(os.path.join(a.repo, "logs"), exist_ok=True)
    if not os.path.isdir(os.path.join(a.repo, ".git")):
        git(a.repo, "init", "-q"); git(a.repo, "config", "user.name", "campaign-monitor")
        git(a.repo, "config", "user.email", "monitor@localhost")
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    t0 = time.time(); out = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(do_site, r, a.repo, a.raw_dir, day) for r in rows]
        for i, f in enumerate(cf.as_completed(futs), 1):
            out.append(f.result())
            if i % 250 == 0: print(f"  {i}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)
    out.sort(key=lambda r: r["site_id"])
    logp = os.path.join(a.repo, "logs", f"{day}.csv")
    with open(logp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    n_changed = sum(r["changed"] for r in out)
    summ = {"day": day, "sites": len(out), "wall_s": round(time.time() - t0),
            "ok": sum(1 for r in out if not r["error"]),
            "changed": n_changed, "first_seen": sum(r["first_seen"] for r in out),
            "low_text": sum(r["low_text"] for r in out), "errors": {}}
    for r in out:
        if r["error"]: k = r["error"].split(":")[0]; summ["errors"][k] = summ["errors"].get(k, 0) + 1
    # the summary is committed with the snapshot, so each day's health is in the history
    with open(os.path.join(a.repo, "logs", f"{day}-summary.json"), "w") as f:
        json.dump(summ, f, indent=1, sort_keys=True); f.write("\n")
    git(a.repo, "add", "-A")
    git(a.repo, "commit", "-q", "--allow-empty", "-m",
        f"snapshot {day}: {len(out)} sites, {n_changed} changed")
    summ["commit"] = git(a.repo, "rev-parse", "--short", "HEAD").strip()
    json.dump(summ, open(a.summary, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
