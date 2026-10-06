"""Page parsing and change detection for the daily snapshot (issue #5).

The method is the one the parser evaluation selected (docs/parser_evaluation_2026-10-06.md):

  * visible text and outgoing links come from EDGI's web-monitoring-diff (`html_text_diff`,
    `links_diff`), compared with whitespace ignored;
  * images and embeds come from the image-and-embed list below, which EDGI does not report;
  * a small set of noise rules (`mask_noise`) is applied to the HTML first, so that the visible-text
    noise the evaluation found every method flags - cookie banners, countdown and donation widgets,
    relative dates and copyright years - does not count as a change.

The noise rules never delete campaign content. They remove cookie-consent banners, and replace
each number with "#" only where the surrounding text shows they are a counter, a donation total, a
relative date or a copyright year. The snapshot text is the masked text, so the Git history shows
exactly the change that was detected.

`page(html, final_url)` is the single entry point. It is pure (no I/O) so it can run in worker
processes: lxml and html5-parser are not safe to call from many threads at once.
"""
import hashlib, json, re
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode, unquote

import lxml.html
from lxml import etree
from web_monitoring_diff import html_text_diff, links_diff
from web_monitoring_diff.exceptions import UndiffableContentError  # noqa: F401  (re-exported for snapshot.py)

FORMAT = 3                     # 3 = EDGI text and links + image list + noise rules (6 Oct 2026)
EMPTY = "<html><head></head><body></body></html>"

# ---------------------------------------------------------------- noise rules
SKIP = {"script", "style", "noscript", "template"}
INLINE = {"span", "strong", "b", "em", "i", "a", "small", "sup", "sub", "font", "label", "mark", "u", "time", "abbr"}
KEEP_TAGS = {"html", "body", "main", "article"}

# banner kits by id/class; the element must also mention cookies ("consent" alone also names SMS opt-in text)
COOKIE_ATTR = re.compile(r"cookie|gdpr|ccpa|onetrust|cookiebot|cmplz|termly|cookieyes|truste|osano", re.I)
CONSENT_ATTR = re.compile(r"consent", re.I)
COOKIE_WORD = re.compile(r"\bcookies?\b", re.I)
CONSENT_WORD = re.compile(r"\b(accept|consent|agree|privacy|experience|analytics|partners|continuing|preferences|opt[ -]?out|personali[sz]e|tracking)\b", re.I)
COOKIE_MAX = 600               # a banner is short; never remove a large block

UNIT = r"(?:d|h|m|s|days?|hours?|hrs?|minutes?|mins?|seconds?|secs?)"
# a relative date becomes one token, so "45 minutes ago", "1 hour ago" and "Yesterday" compare equal
RE_AGO = re.compile(r"\b(?:\d+|an?|one)\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s+ago\b", re.I)
RE_DAYWORD = re.compile(r"\s*(?:yesterday|today|just now)\s*", re.I)       # only as a whole date label
# "© 2025", "Copyright 2024-2026", "2025 ©", "© Smith for Senate 2025"
RE_COPY = re.compile(r"(?:©|\(c\)|copyright)[^\d\n]{0,60}?\d{4}(?:\s*[-–—]\s*\d{4})?|\d{4}(?=\s*©)", re.I)
YEAR = re.compile(r"\d{4}")
# a counter widget: two or more number-unit pairs ("29 Days 14 Hours", "29d : 14h"), or one followed by
# "until / to go / left / remaining / away" ("Only 29 days until Election Day")
# a counter widget: two or more number-unit pairs ("29 Days 14 Hours", "29d : 14h"), one followed by
# "until / to go / left / remaining / away", a clock ("29 : 14 : 07"), or days counted to the election
COUNTER_CTX = re.compile(rf"\b\d+\s*{UNIT}\b.*?\b\d+\s*{UNIT}\b|\b\d+\s*{UNIT}\b.{{0,40}}?\b(?:until|to go|left|remaining|away)\b"
                         r"|\b\d+\s*:\s*\d+\s*:\s*\d+\b"
                         r"|\b(?:election|vote|voting|polls?)\b.{0,60}?\b\d+\s*days?\b|\b\d+\s*days?\b.{0,60}?\b(?:election|vote|voting|polls?)\b",
                         re.I | re.S)
COUNTER_ATTR = re.compile(r"count-?down|timer|flip-?clock|flipdown|clock", re.I)
DONATION_CTX = re.compile(r"\b(raised|goal|funded|donors?|contributors?|donations?|chipped in|toward)\b", re.I)
CTX_MAX = 300                  # context only counts inside a short block (a widget, not a paragraph run)
DIGITS = re.compile(r"\d+")


def _block(el):
    while el is not None and el.tag in INLINE:
        el = el.getparent()
    return el


def _text(el):
    return " ".join(el.text_content().split())


def drop_cookie_banners(doc):
    """remove cookie-consent containers: by id/class, or a short element about cookies and consent"""
    n = 0
    for el in list(doc.iter()):
        if not isinstance(el.tag, str) or el.tag in KEEP_TAGS or el.getparent() is None:
            continue
        if _gone(el):
            continue
        attrs = (el.get("id") or "") + " " + (el.get("class") or "")
        t = None
        if COOKIE_ATTR.search(attrs) or CONSENT_ATTR.search(attrs):
            t = _text(el)
            if len(t) <= COOKIE_MAX * 3 and COOKIE_WORD.search(t):       # a banner says "cookies"
                el.drop_tree(); n += 1
                continue
        if el.tag in INLINE:
            continue
        t = t if t is not None else _text(el)
        if len(t) <= COOKIE_MAX and COOKIE_WORD.search(t) and CONSENT_WORD.search(t):
            el.drop_tree(); n += 1
    return n


def _gone(el):
    """True once an ancestor has been removed from the document"""
    while el.getparent() is not None:
        el = el.getparent()
    return el.tag != "html"


def mask_text_nodes(doc):
    """replace noise digits with '#' in text nodes"""
    ctx = {}
    for el in doc.iter():
        if not isinstance(el.tag, str) or el.tag in SKIP:
            continue
        for att, owner in (("text", el), ("tail", el.getparent())):
            v = getattr(el, att)
            if not v or owner is None or owner.tag in SKIP or not (DIGITS.search(v) or RE_DAYWORD.fullmatch(v)):
                continue
            # every masked number becomes one "#", whatever its length, so "9" and "10" compare equal
            new = RE_COPY.sub(lambda m: YEAR.sub("#", m.group(0)), v)
            new = RE_AGO.sub("#ago", new)
            if RE_DAYWORD.fullmatch(new):
                new = "#ago"
            if DIGITS.search(new) and _noisy_context(_block(owner), ctx):
                new = mask_widget_numbers(new)
            if new != v:
                setattr(el, att, new)


# Inside a counter or fundraising widget, only the widget's own numbers are masked: a text node that is
# nothing but a number, amount, percentage or clock, and numbers followed by a time unit or a count word.
# Other numbers in the same block (a phone number, a date, a policy figure) are kept.
# a widget value: "29", "1,204", "$8,140", "62%", "29 : 14 : 07". Phone numbers and dates do not match.
PURE_NUMBER = re.compile(r"\s*\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*[%kKmM+]?\s*|\s*\d{1,3}(?:\s*:\s*\d{1,2}){1,3}\s*")
COUNTED = re.compile(rf"[$]?\d[\d,.]*(?=\s*(?:%|\+|{UNIT}\b|(?:donors?|people|contributors?|supporters?|backers?|"
                     r"members?|signatures?|likes?|comments?|shares?|followers?)\b))", re.I)
MONEY = re.compile(r"\$\s?\d[\d,.]*[kKmM]?")


def mask_widget_numbers(text):
    if PURE_NUMBER.fullmatch(text):
        return DIGITS.sub("#", text)
    text = COUNTED.sub("#", text)
    if DONATION_CTX.search(text):                # "$12,450 raised of $25,000 goal", not "cap insulin at $35"
        text = MONEY.sub("$#", text)
    return text


def _noisy_context(b, cache):
    """is this block, or a short block around it, a counter or donation widget?"""
    seen = []
    while b is not None and isinstance(b.tag, str):
        if b in cache:
            hit = cache[b]; break
        t = _text(b)
        if len(t) > CTX_MAX:
            hit = False; break
        seen.append(b)
        attrs = (b.get("id") or "") + " " + (b.get("class") or "")
        if COUNTER_CTX.search(t) or DONATION_CTX.search(t) or COUNTER_ATTR.search(attrs):
            hit = True; break
        b = b.getparent()
    else:
        hit = False
    for e in seen:
        cache[e] = hit
    return hit


# form anti-spam honeypots show a randomly chosen label on every load (Gravity Forms, WPForms)
HONEYPOT_ATTR = re.compile(r"gform_validation_container|wpforms-field-hp|\bhoneypot\b", re.I)
HONEYPOT_TEXT = "This field is for validation purposes and should be left unchanged."


def drop_honeypots(doc):
    for el in list(doc.iter()):
        if not isinstance(el.tag, str) or el.tag in KEEP_TAGS or el.getparent() is None or _gone(el):
            continue
        if HONEYPOT_ATTR.search((el.get("id") or "") + " " + (el.get("class") or "")):
            el.drop_tree(); continue
        if el.tag not in INLINE and HONEYPOT_TEXT in (el.text_content() or "") and len(_text(el)) <= 200:
            el.drop_tree()


def mask_noise(doc):
    drop_cookie_banners(doc)
    drop_honeypots(doc)
    mask_text_nodes(doc)


# ---------------------------------------------------------------- images and embeds
def norm_media_url(u):
    """the same image at another size or with a cache-busting parameter compares equal"""
    u = (u or "").strip()
    if not u or u.startswith(("data:", "javascript:", "about:")):
        return None
    u = re.split(r"[?#]", u, maxsplit=1)[0]
    u = re.sub(r"^(https?:)?//", "//", u, flags=re.I)
    m = re.match(r"(//[^/]+)(.*)", u)
    if m:
        u = m.group(1).lower() + m.group(2)
    u = re.sub(r"(/media/[^/]+?)/v1/.*$", r"\1", u)                         # Wix transform path
    u = re.sub(r"-\d{2,5}x\d{2,5}(?=\.\w{3,4}$)", "", u)                     # WordPress size suffix
    u = re.sub(r"/(?:\d{2,5}w|format/\d+w)$", "", u)                         # Squarespace format suffix
    u = re.sub(r"^(//sites\.google\.com/sitesv-images[^/]*)/.*$", r"\1", u)  # Google Sites: a new signed URL per load
    return u or None


BG = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)
IMG_ATTRS = ("src", "data-src", "data-lazy-src", "data-original", "data-image", "data-bg", "data-pin-media")


def media_list(doc):
    items = set()
    for el in doc.iter():
        if not isinstance(el.tag, str) or el.tag in ("script", "style", "template"):
            continue
        if el.tag in ("img", "source"):
            urls = [el.get(k) for k in IMG_ATTRS if el.get(k)]
            for k in ("srcset", "data-srcset"):
                for part in (el.get(k) or "").split(","):
                    if part.strip():
                        urls.append(part.split()[0])
            good = [x for x in map(norm_media_url, urls) if x]
            items.update("img:" + x for x in good)
            if el.tag == "img" and el.get("alt"):
                items.add(f"alt:{good[0] if good else ''}|{' '.join(el.get('alt').split())}")
        if el.tag in ("iframe", "embed", "video", "audio", "object"):
            for k in ("src", "data-src", "data", "poster"):
                x = norm_media_url(el.get(k))
                if x:
                    items.add("embed:" + x)
        for x in BG.findall(el.get("style") or ""):
            x = norm_media_url(x)
            if x:
                items.add("img:" + x)
    return sorted(items)


# ---------------------------------------------------------------- links (crawler) and metadata
TRACK_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|_ga|_gl|ref|refcode|source)$", re.I)


CF_EMAIL = re.compile(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def decode_href(h):
    """links that are re-encoded on every load: Cloudflare email protection (a random XOR key) and
    percent- or entity-scrambled mailto links decode to the same address every time"""
    m = CF_EMAIL.search(h)
    if m and len(m.group(1)) >= 4:
        b = bytes.fromhex(m.group(1)[: len(m.group(1)) // 2 * 2])
        return "mailto:" + bytes(x ^ b[0] for x in b[1:]).decode("utf-8", "replace")
    if re.match(r"\s*mail?to:", h, re.I):
        for _ in range(3):
            h = unescape(unquote(h))
    return h


def clean_href(h):
    u = urlparse(h.strip())
    # tracking parameters dropped; a date in the query ("?range=2026-10-06", a calendar's today) masked
    q = urlencode([(k, ISO_DATE.sub("#", v)) for k, v in parse_qsl(u.query, keep_blank_values=True) if not TRACK_PARAMS.match(k)])
    return urlunparse((u.scheme, u.netloc.lower(), u.path, u.params, q, u.fragment))


def crawl_hrefs(doc, final_url):
    out = []
    for a in doc.iter("a"):
        h = (a.get("href") or "").strip()
        if h and not h.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
            out.append(urljoin(final_url, h).split("#")[0])
    return out


def meta_of(doc):
    t = doc.find(".//title")
    desc = ""
    for m in doc.iter("meta"):
        if (m.get("name") or m.get("property") or "").lower() in ("description", "og:description"):
            desc = m.get("content") or ""; break
    return {"title": " ".join((t.text_content() if t is not None else "").split()), "description": " ".join(desc.split())}


# ---------------------------------------------------------------- the page
class EmptyDocument(Exception):
    pass


def parse(html):
    html = html.replace("\x00", "")
    if not html.strip():
        raise EmptyDocument()
    try:
        return lxml.html.document_fromstring(html)
    except etree.ParserError:
        raise EmptyDocument()
    except ValueError:                           # a str with an XML encoding declaration
        try:
            return lxml.html.document_fromstring(html.encode("utf-8", "replace"),
                                                 parser=lxml.html.HTMLParser(encoding="utf-8"))
        except etree.ParserError:
            raise EmptyDocument()


PAID_FOR = re.compile(r"(?:paid for|authori[sz]ed|sponsored) by\b[^.|\n]{3,160}", re.I)
YEARS = re.compile(r"\b(?:19[5-9]\d|20[0-4]\d)\b")      # copyright years are already masked


def collapse(s):
    return " ".join(s.split())


def as_lines(text):
    """display form of the text file: one sentence per line"""
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[\"'“(]?[A-Z0-9#])", collapse(text)) if s]


def page(html, final_url):
    """Parse one page. Returns a dict of the snapshot contents plus crawl links. Raises
    UndiffableContentError when EDGI does not consider the document HTML."""
    doc = parse(html)
    hrefs = crawl_hrefs(doc, final_url)          # crawling uses every link, before noise removal
    meta = meta_of(doc)
    mask_noise(doc)
    masked = etree.tostring(doc, encoding="unicode", method="html")
    text = collapse("".join(t for op, t in html_text_diff(EMPTY, masked)["diff"] if op != -1))
    links = []
    for op, item in links_diff(EMPTY, masked)["diff"]:
        if op == 1:
            links.append({"text": collapse(item["text"]), "href": clean_href(urljoin(final_url, decode_href(item["href"])))})
    links = sorted({(l["text"], l["href"]) for l in links})
    links = [{"text": t, "href": h} for t, h in links]
    media = media_list(doc)
    content = {"text": text, "links": links, "media": media, **meta}
    m = PAID_FOR.search(text)
    extra = {"paid_for_by": collapse(m.group(0)).rstrip(" .") if m else "",
             "years_mentioned": sorted(set(YEARS.findall(text)))}       # derived from text, so not fingerprinted
    fp = hashlib.sha1(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"text": text, "lines": as_lines(text), "links": links, "media": media,
            "meta": {"format": FORMAT, "final_url": final_url, **meta, **extra, "fingerprint": fp},
            "hrefs": hrefs}


def changed(prev_meta, new_meta):
    """compare by fingerprint; None means the stored snapshot is in an older format"""
    if not prev_meta or prev_meta.get("format") != FORMAT:
        return None
    return prev_meta.get("fingerprint") != new_meta["fingerprint"]
