#!/usr/bin/env python3
"""Daily snapshot of 2026 candidate campaign websites (issues #1, #4).

For each site in the input CSV (columns: site_id, url, ...), crawl from the homepage,
following links on the candidate's own site up to --max-depth clicks (default 3) and at
most --max-pages pages (default 50), nearest pages first. Each page is normalised and
written to the Git repository:

  sites/<site_id>/{text.md, links.json, meta.json}                  the homepage
  sites/<site_id>/pages/<page-slug>/{text.md, links.json, meta.json}  every other page

then everything is committed once. Files are rewritten only when their normalised content
changes, so the repository history *is* the change log. Pages that are new today appear
as added files; pages that are gone appear as deleted files (see remove_gone_pages).

"Own site" = the start URL's host (www. ignored) plus the host it redirects to; when the
start URL has a path (e.g. sites.google.com/view/jane), only links under that path.
Links to other sites are recorded in links.json but never fetched. robots.txt is obeyed
and requests to one host are at least HOST_GAP_S apart.

Volatile values (fetch time, response time, byte size) go to the per-page run log
logs/<date>.csv, never into snapshot files. A failed fetch never overwrites a good snapshot.

usage: python snapshot.py URLS.csv REPO_DIR [--workers 24] [--max-depth 3] [--max-pages 50]
                          [--raw-dir DIR] [--summary FILE] [--day YYYY-MM-DD] [--limit N]
"""
import argparse, collections, concurrent.futures as cf, csv, dataclasses, datetime as dt, gzip, hashlib
import faulthandler, json, os, re, shutil, subprocess, sys, threading, time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib import robotparser

import requests
import trafilatura

UA = "CampaignSiteMonitor/0.1 (nonpartisan research archive of 2026 candidate websites)"
TIMEOUT = 20
MAX_BYTES = 5_000_000
HOST_GAP_S = 1.0          # minimum spacing between requests to the same host
# links never worth fetching as pages (PDFs are handled separately, issue #7)
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp|ico|bmp|tiff?|css|js|mjs|json|xml|rss|woff2?|ttf|otf|eot|"
                      r"mp[34]|m4[av]|mov|avi|webm|wav|ogg|zip|gz|rar|7z|dmg|exe|pdf|docx?|xlsx?|pptx?|ics|vcf|txt)$", re.I)
SKIP_PATH = re.compile(r"/(wp-admin|wp-login\.php|xmlrpc\.php|wp-json|feed|cart|checkout|my-account)(/|$)", re.I)
# page errors that don't hide any links, so a crawl with only these is still complete
# page outcomes (PageRec.error), grouped by what the crawler does about them
GONE = {"http_404", "http_410"}                       # the page no longer exists
BACKOFF = {"http_429", "http_503"}                    # the site asked us to slow down: leave it for today
HARMLESS = {"robots_disallowed", "not_html", "offsite_redirect"} | GONE   # can't hide any links
HOME = "/"                                            # PageRec.page of a site's homepage
REQUEST_BUDGET = 2                                    # max requests per site = REQUEST_BUDGET * max_pages
# trafilatura/lxml crashed the process ("double free or corruption") with 24 threads parsing at
# once on the first full run; parsing is CPU-bound under the GIL anyway, so do it one page at a time.
_parse_lock = threading.Lock()

# ---------------------------------------------------------------- normalisation
# Snapshot format 2 (issue #5): text.md is the page's FULL visible text, including content in
# tabs, accordions and other collapsed sections; main.md is the extracted main content, kept as a
# reading view only. Changes are detected on text.md.
FORMAT = 2
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head", "iframe", "object", "canvas", "select"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside", "li", "ul", "ol",
              "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "td", "th", "blockquote", "figure",
              "figcaption", "details", "summary", "form", "label", "button", "dd", "dt", "dl", "br", "hr", "pre"}
UNITS = r"(days?|hours?|hrs?|minutes?|mins?|seconds?|secs?)"
NOISE_LINE = re.compile(
    rf"^\d+\s*{UNITS}\b.*|"                                                   # countdowns: "12 days until ..."
    rf"^{UNITS}$|"                                                            # countdown unit labels
    rf"^(\s*\d+\s*{UNITS}?\s*[:,|]?)+$|"                                       # widgets: "12Days05Hours", "12 : 05"
    rf"^.{{0,40}}\b\d+\s+{UNITS}\s+(until|to go|left|away|remaining)\b.{{0,40}}$|"
    r"^\d[\d,]*\s+(donors?|contributors?|supporters?)( so far| and counting)?[.!]?$|"   # live donor counters
    r"^(accept|accept all|reject|reject all|decline|cookie settings|manage cookies)$", re.I)
COUNTER_CHARS = re.compile(r"^[\d\s:.,%$+]+$")       # digits and counter punctuation only (no - or /: phones, dates)
MAX_COUNTER_DIGITS = 6                               # longer digit runs are phone numbers, dates, IDs: keep them
MAX_PROGRESS_LEN = 80                                # a progress-bar label is short; prose about money is longer
MAX_BANNER_LEN = 300                                 # a cookie banner is a sentence or two
PROGRESS = re.compile(r"\$[\d,.]+[kKmM]?\b.*\b(raised|goal|to go)\b|\b(raised|goal)\b.*\$[\d,.]+|"
                      r"\d+(\.\d+)?\s*%\s*(funded|of (our |the )?goal)", re.I)
COOKIE = re.compile(r"\bcookies?\b", re.I)
BANNER = re.compile(r"\b(website|site|experience|browsing|consent|accept|privacy policy|cookie policy)\b", re.I)

def is_noise(s):
    if NOISE_LINE.match(s): return True
    if COUNTER_CHARS.match(s) and sum(ch.isdigit() for ch in s) <= MAX_COUNTER_DIGITS: return True
    if len(s) <= MAX_PROGRESS_LEN and PROGRESS.search(s): return True                    # donation progress
    if len(s) <= MAX_BANNER_LEN and COOKIE.search(s) and BANNER.search(s): return True   # cookie banners
    return False
COPYRIGHT = re.compile(r"(©|\(c\)|copyright)(\s*(©|\(c\)))?\s*\d{4}(\s*[-–]\s*\d{4})?", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“(])")
TRACK_PARAMS = re.compile(r"^(utm_|fbclid|gclid|wbraid|gbraid|msclkid|dclid|igshid|ttclid|twclid|li_fat_id|"
                          r"mc_|_ga|_gl|_hs|hsCta|mkt_tok|srsltid|gad_|s_kwcid|ref$|refcode|source$)", re.I)
DISCLAIMER = re.compile(r"(paid for by[^.\n]{3,140})", re.I)
YEAR = re.compile(r"\b(20[12]\d)\b")


class Page(HTMLParser):
    """One pass over the HTML: title, description, <a href> targets and visible text blocks."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.desc, self.links, self.blocks = "", "", [], [[]]
        self._skip, self._in_title = 0, False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title": self._in_title = True
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description"):
            self.desc = self.desc or (a.get("content") or "").strip()
        elif tag == "a" and a.get("href"): self.links.append(a["href"].strip())
        if tag in SKIP_TAGS: self._skip += 1
        if tag in BLOCK_TAGS: self.blocks.append([])
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in SKIP_TAGS: self._skip -= 1
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        if tag in SKIP_TAGS and self._skip: self._skip -= 1
        if tag in BLOCK_TAGS: self.blocks.append([])
    def handle_data(self, d):
        if self._in_title: self.title += d
        elif not self._skip: self.blocks[-1].append(d)


def sentences(paragraphs):
    """one sentence per line; noise lines dropped; copyright years neutralised"""
    out = []
    for para in paragraphs:
        para = COPYRIGHT.sub("© YEAR", " ".join(para.split()))
        if not para: continue
        for s in SENT_SPLIT.split(para):
            s = s.strip()
            if s and not is_noise(s): out.append(s)
    return out


def norm_link(base, href):
    if href.startswith(("javascript:", "mailto:", "tel:", "#", "data:")): return None
    u = urlparse(urljoin(base, href))
    if u.scheme not in ("http", "https"): return None
    q = urlencode([(k, v) for k, v in parse_qsl(u.query) if not TRACK_PARAMS.match(k)])
    return urlunparse((u.scheme, u.netloc.lower().removeprefix("www."), u.path.rstrip("/") or "/", "", q, ""))


@dataclasses.dataclass
class PageData:
    """normalised page. text, main, links and meta are the snapshot files, so nothing volatile
    (fetch time, response time, size) goes into them; hrefs are the raw link targets for the crawler."""
    text: str
    main: str
    links: list
    meta: dict
    hrefs: list


def normalise(html, final_url):
    p = Page()
    try: p.feed(html); p.close()
    except Exception: pass
    full = sentences("".join(b) for b in p.blocks)
    main = sentences((trafilatura.extract(html, output_format="txt", include_comments=False,
                                          include_tables=True, favor_recall=True) or "").splitlines())
    links = sorted({l for l in (norm_link(final_url, h) for h in p.links) if l})
    hrefs = [urljoin(final_url, h).split("#")[0] for h in p.links
             if not h.startswith(("javascript:", "mailto:", "tel:", "#", "data:"))]
    body = " ".join(full)
    m = DISCLAIMER.search(body)
    meta = {"format": FORMAT,
            "final_url": final_url,
            "title": " ".join(p.title.split()),
            "description": " ".join(p.desc.split()),
            "paid_for_by": " ".join(m.group(1).split()) if m else None,
            "years_mentioned": sorted(set(YEAR.findall(body)))}
    as_file = lambda ls: "\n".join(ls) + ("\n" if ls else "")
    return PageData(as_file(full), as_file(main), links, meta, hrefs)


# ---------------------------------------------------------------- politeness
_robots, _robots_lock = {}, threading.Lock()
_last_hit, _hit_lock = {}, threading.Lock()

def wait_turn(url):
    host = host_of(url)              # www.x.org and x.org are one site: one queue
    while True:
        with _hit_lock:
            now = time.monotonic(); last = _last_hit.get(host, 0)
            if now - last >= HOST_GAP_S:
                _last_hit[host] = now; return
        time.sleep(HOST_GAP_S - (now - last))

def robots_ok(sess, url):
    u = urlparse(url); key = f"{u.scheme}://{u.netloc}"
    with _robots_lock:
        rp = _robots.get(key)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            wait_turn(key)                       # robots.txt is a request to the site too
            r = sess.get(key + "/robots.txt", timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        with _robots_lock: _robots[key] = rp
    return rp.can_fetch(UA, url)


# ---------------------------------------------------------------- one site
_local = threading.local()
def session():
    if not hasattr(_local, "s"):
        s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept": "text/html,*/*;q=0.5"})
        _local.s = s
    return _local.s


@dataclasses.dataclass
class Run:
    """settings shared by every site in one daily run"""
    repo: str
    raw_dir: str | None
    day: str
    max_depth: int = 3
    max_pages: int = 50


@dataclasses.dataclass
class PageRec:
    """one row of the run log: one page fetched (or found gone) today"""
    site_id: str
    page: str              # HOME for the homepage, otherwise the page's slug under pages/
    url: str
    depth: int
    status: int | str = ""
    final_url: str = ""
    bytes: int = 0
    text_chars: int = 0
    changed: bool = False
    first_seen: bool = False
    removed: bool = False
    low_text: bool = False
    error: str = ""
    elapsed_s: float = 0.0

    @property
    def is_home(self): return self.page == HOME

LOG_FIELDS = [f.name for f in dataclasses.fields(PageRec)]


@dataclasses.dataclass
class SiteResult:
    pages: list            # PageRecs, homepage first
    capped: bool = False   # stopped at max_pages with in-scope pages still unvisited


def host_of(url):
    return urlparse(url).netloc.lower().removeprefix("www.")

def page_key(url):
    """identity of a page within its site: path + query, ignoring scheme, www., fragment, tracking"""
    n = urlparse(norm_link(url, url) or url)
    return n.path + ("?" + n.query if n.query else "")

def page_slug(key):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", key.strip("/")).strip("_")[:80] or "index"
    return f"{s}-{hashlib.sha1(key.encode()).hexdigest()[:6]}"

def write_if_changed(path, data):
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old != data:
        with open(path, "wb") as f: f.write(data)
        return True
    return False

def error_name(e):
    if isinstance(e, requests.exceptions.SSLError): return "ssl_error"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "dns_or_connect" if "resolve" in str(e).lower() or "Name or service" in str(e) else "connect_error"
    if isinstance(e, requests.exceptions.Timeout): return "timeout"
    return f"{type(e).__name__}: {str(e)[:120]}"


def fetch_page(rec, run, page_dir, hosts):
    """Fetch one page and save its snapshot into page_dir. Fills in rec.
    Returns the page's absolute outgoing link targets, or [] when nothing was saved."""
    s = session()
    if not robots_ok(s, rec.url):
        rec.error = "robots_disallowed"; return []
    wait_turn(rec.url)
    r = s.get(rec.url, timeout=TIMEOUT, allow_redirects=True, stream=True)
    raw = r.raw.read(MAX_BYTES, decode_content=True); r.close()
    rec.status, rec.final_url, rec.bytes = r.status_code, r.url, len(raw)
    if r.status_code >= 400:
        rec.error = f"http_{r.status_code}"; return []
    if hosts and host_of(r.url) not in hosts:
        rec.error = "offsite_redirect"; return []
    ctype = r.headers.get("Content-Type", "")
    if ctype and "html" not in ctype.lower():
        rec.error = "not_html"; return []
    enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
    with _parse_lock:
        pg = normalise(raw.decode(enc, errors="replace"), r.url)
    rec.text_chars, rec.low_text = len(pg.text), len(pg.text) < 200
    rec.first_seen = not os.path.exists(os.path.join(page_dir, "text.md"))
    os.makedirs(page_dir, exist_ok=True)
    ch = write_if_changed(os.path.join(page_dir, "text.md"), pg.text.encode())
    write_if_changed(os.path.join(page_dir, "main.md"), pg.main.encode())   # reading view; not used for change detection
    ch |= write_if_changed(os.path.join(page_dir, "links.json"), (json.dumps(pg.links, indent=0) + "\n").encode())
    ch |= write_if_changed(os.path.join(page_dir, "meta.json"), (json.dumps(pg.meta, indent=1, sort_keys=True) + "\n").encode())
    rec.changed = ch
    if ch and run.raw_dir:                       # keep raw HTML only when content changed
        d = os.path.join(run.raw_dir, run.day, rec.site_id); os.makedirs(d, exist_ok=True)
        with gzip.open(os.path.join(d, ("_home" if rec.is_home else rec.page) + ".html.gz"), "wb") as f:
            f.write(raw)
    return pg.hrefs


def in_scope(url, hosts, prefix):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or host_of(url) not in hosts: return False
    if SKIP_EXT.search(u.path) or SKIP_PATH.search(u.path): return False
    p = u.path.rstrip("/")
    return not prefix or p == prefix or p.startswith(prefix + "/")


def remove_gone_pages(site_dir, discovered, recs, site_id):
    """A known page is gone when today's crawl was complete (homepage fetched, nothing that could
    hide links failed, page cap not hit) and the page was not linked within reach any more."""
    pages = os.path.join(site_dir, "pages")
    if not os.path.isdir(pages): return
    for slug in sorted(set(os.listdir(pages)) - discovered):
        try: url = json.load(open(os.path.join(pages, slug, "meta.json")))["final_url"]
        except Exception: url = ""
        shutil.rmtree(os.path.join(pages, slug))
        recs.append(PageRec(site_id, slug, url, -1, removed=True))


def crawl_site(row, run):
    """Breadth-first crawl of one site, nearest pages first."""
    sid, start = row["site_id"], row["url"]
    site_dir = os.path.join(run.repo, "sites", sid)
    hosts = {host_of(start)}
    prefix = urlparse(start).path.rstrip("/")          # "" = whole host
    queue = collections.deque([(start, 0, HOME)])
    seen, discovered, recs = {page_key(start)}, set(), []
    captured, requests_made, complete, capped = 0, 0, True, False
    while queue:
        # the cap counts pages actually captured; a separate budget bounds requests on sites full of dead links
        if captured >= run.max_pages or requests_made >= REQUEST_BUDGET * run.max_pages:
            capped = True; break
        url, depth, slug = queue.popleft()
        rec = PageRec(sid, slug, url, depth)
        page_dir = site_dir if rec.is_home else os.path.join(site_dir, "pages", slug)
        t0 = time.monotonic()
        try:
            hrefs = fetch_page(rec, run, page_dir, None if rec.is_home else hosts)
        except Exception as e:
            rec.error, hrefs = error_name(e), []
        rec.elapsed_s = round(time.monotonic() - t0, 2)
        recs.append(rec)
        if rec.error != "robots_disallowed": requests_made += 1
        if not rec.error: captured += 1
        if rec.is_home:
            if rec.error: return SiteResult(recs)         # homepage failed: keep everything as it was
            if host_of(rec.final_url) != host_of(start):  # redirected to another domain: crawl that one
                hosts.add(host_of(rec.final_url)); prefix = ""
            seen.add(page_key(rec.final_url))
        elif rec.error in GONE and os.path.isdir(page_dir):
            shutil.rmtree(page_dir); rec.removed = True   # a known page that is now gone
        if rec.error in BACKOFF:
            complete = False; break
        if rec.error and rec.error not in HARMLESS:
            complete = False
        if depth >= run.max_depth: continue
        for h in sorted(set(hrefs)):
            if not in_scope(h, hosts, prefix): continue
            k = page_key(h)
            if k in seen: continue
            seen.add(k); s = page_slug(k); discovered.add(s)
            queue.append((h, depth + 1, s))
    if complete and not capped:
        remove_gone_pages(site_dir, discovered, recs, sid)
    return SiteResult(recs, capped)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def summarise(day, n_sites, sites, wall_s):
    home = [s.pages[0] for s in sites]
    pages = [r for s in sites for r in s.pages]
    inner = [r for r in pages if not r.is_home]
    summ = {"day": day, "sites": n_sites, "wall_s": wall_s,
            "reached": sum(1 for r in home if r.status),     # answered with any HTTP status, incl. 403
            "ok": sum(1 for r in home if not r.error),       # homepage fetched and snapshotted
            "changed": sum(1 for s in sites if any(r.changed or r.removed for r in s.pages)),  # sites
            "first_seen": sum(1 for r in home if r.first_seen),
            "low_text": sum(1 for r in pages if r.low_text),
            "sites_capped": sum(1 for s in sites if s.capped),
            "pages_fetched": sum(1 for r in pages if r.status != ""),
            "pages_ok": sum(1 for r in pages if not r.error and not r.removed),
            "pages_changed": sum(1 for r in pages if r.changed),
            "pages_added": sum(1 for r in inner if r.first_seen),
            "pages_removed": sum(1 for r in pages if r.removed),
            "errors": {}, "page_errors": {}}
    for r in pages:
        if r.error:
            bucket = summ["errors"] if r.is_home else summ["page_errors"]
            k = r.error.split(":")[0]; bucket[k] = bucket.get(k, 0) + 1
    return summ


def main():
    faulthandler.enable()            # a native crash prints every thread's Python stack to the run log
    ap = argparse.ArgumentParser()
    ap.add_argument("urls"); ap.add_argument("repo")
    ap.add_argument("--limit", type=int); ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-depth", type=int, default=3); ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--raw-dir"); ap.add_argument("--summary", default="summary.json")
    ap.add_argument("--day", help="run date YYYY-MM-DD (default: today, UTC); used by tests")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.urls)))
    if a.limit: rows = rows[:a.limit]
    os.makedirs(os.path.join(a.repo, "logs"), exist_ok=True)
    if not os.path.isdir(os.path.join(a.repo, ".git")):
        git(a.repo, "init", "-q"); git(a.repo, "config", "user.name", "campaign-monitor")
        git(a.repo, "config", "user.email", "monitor@localhost")
    run = Run(a.repo, a.raw_dir, a.day or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
              a.max_depth, a.max_pages)
    t0 = time.time(); sites = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(crawl_site, r, run) for r in rows]
        for i, f in enumerate(cf.as_completed(futs), 1):
            sites.append(f.result())
            if i % 250 == 0:
                print(f"  {i}/{len(rows)} sites  {sum(len(s.pages) for s in sites)} pages  {time.time()-t0:.0f}s", flush=True)
    sites.sort(key=lambda s: s.pages[0].site_id)
    with open(os.path.join(a.repo, "logs", f"{run.day}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS); w.writeheader()
        for s in sites:
            w.writerows(dataclasses.asdict(r) for r in s.pages)
    summ = summarise(run.day, len(rows), sites, round(time.time() - t0))
    # the summary is committed with the snapshot, so each day's health is in the history
    with open(os.path.join(a.repo, "logs", f"{run.day}-summary.json"), "w") as f:
        json.dump(summ, f, indent=1, sort_keys=True); f.write("\n")
    git(a.repo, "add", "-A")
    git(a.repo, "commit", "-q", "--allow-empty", "-m",
        f"snapshot {run.day}: {len(rows)} sites, {summ['pages_ok']} pages, "
        f"{summ['pages_changed']} changed, {summ['pages_added']} added, {summ['pages_removed']} removed")
    summ["commit"] = git(a.repo, "rev-parse", "--short", "HEAD").strip()
    json.dump(summ, open(a.summary, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
