#!/usr/bin/env python3
"""Daily snapshot of 2026 candidate campaign websites (issues #1, #4).

For each site in the input CSV (columns: site_id, url, ...), crawl from the homepage,
following links on the candidate's own site up to --max-depth clicks (default 3) and at
most --max-pages pages (default 50), nearest pages first. Each page is parsed by detect.py
(issue #5: EDGI web-monitoring-diff text and links, an image-and-embed list, and noise rules) and
written to the Git repository:

  sites/<site_id>/{text.md, links.json, media.json, meta.json}                  the homepage
  sites/<site_id>/pages/<page-slug>/{text.md, links.json, media.json, meta.json}  every other page

then everything is committed once. Files are rewritten only when detect.py reports a change
(meta.json holds the fingerprint it compares), so the repository history *is* the change log. Pages that are new today appear
as added files; pages that are gone appear as deleted files (see remove_gone_pages).
PDFs on the candidate's own site are fetched too (pdf.py, issue #7): their text is stored and compared like a page.
Before the commit, changes.py writes changes/<day>.jsonl: one change record per page added, removed or changed
(issue #9), each with the step-0 noise rules applied by step0.py (issue #10).

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
import faulthandler, json, os, re, shutil, signal, subprocess, sys, tempfile, threading, time
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib import robotparser

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import changes, detect, pdf, step0  # noqa: E402

UA = "CampaignSiteMonitor/0.1 (nonpartisan research archive of 2026 candidate websites)"
TIMEOUT = 20
MAX_BYTES = 5_000_000
HOST_GAP_S = 1.0          # minimum spacing between requests to the same host
# links never worth fetching as pages (PDFs are handled separately, issue #7)
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp|ico|bmp|tiff?|css|js|mjs|json|xml|rss|woff2?|ttf|otf|eot|"
                      r"mp[34]|m4[av]|mov|avi|webm|wav|ogg|zip|gz|rar|7z|dmg|exe|docx?|xlsx?|pptx?|ics|vcf|txt)$", re.I)
SKIP_PATH = re.compile(r"/(wp-admin|wp-login\.php|xmlrpc\.php|wp-json|feed|cart|checkout|my-account)(/|$)", re.I)
# page errors that don't hide any links, so a crawl with only these is still complete
# page outcomes (PageRec.error), grouped by what the crawler does about them
GONE = {"http_404", "http_410"}                       # the page no longer exists
BACKOFF = {"http_429", "http_503"}                    # the site asked us to slow down: leave it for today
HARMLESS = {"robots_disallowed", "not_html", "empty_page", "offsite_redirect",
            "pdf_failed", "pdf_timeout", "pdf_too_large", "pdf_tools_missing"} | GONE   # can't hide any links
HOME = "/"                                            # PageRec.page of a site's homepage
REQUEST_BUDGET = 2                                    # max requests per site = REQUEST_BUDGET * max_pages
TRACK_PARAMS = re.compile(r"^(utm_|fbclid|gclid|wbraid|gbraid|msclkid|dclid|igshid|ttclid|twclid|li_fat_id|"
                          r"mc_|_ga|_gl|_hs|hsCta|mkt_tok|srsltid|gad_|s_kwcid|ref$|refcode|source$)", re.I)
PARSE_TIMEOUT_S = 60      # a page that takes longer to parse is logged as parse_timeout and skipped


def norm_link(base, href):
    """page identity for the crawler (see page_key); snapshot links come from detect.py"""
    if href.startswith(("javascript:", "mailto:", "tel:", "#", "data:")): return None
    u = urlparse(urljoin(base, href))
    if u.scheme not in ("http", "https"): return None
    q = urlencode([(k, v) for k, v in parse_qsl(u.query) if not TRACK_PARAMS.match(k)])
    return urlunparse((u.scheme, u.netloc.lower().removeprefix("www."), u.path.rstrip("/") or "/", "", q, ""))


# ---------------------------------------------------------------- parsing (issue #5)
# Pages are parsed by detect.page in worker processes. lxml and html5-parser crashed the process
# ("double free or corruption") when many threads parsed at once, and a process can be killed when a
# page hangs the parser, which a thread cannot.
class ParsePool:
    def __init__(self, workers):
        self.workers, self.lock = workers, threading.Lock()
        self.ex = cf.ProcessPoolExecutor(workers) if workers else None

    def parse(self, html, url):
        if self.ex is None:
            return detect.page(html, url)
        for attempt in (1, 2):
            with self.lock:
                ex = self.ex
            try:
                try:
                    fut = ex.submit(detect.page, html, url)
                except RuntimeError:                     # submitted to a pool another thread just shut down
                    raise cf.process.BrokenProcessPool()
                return fut.result(timeout=PARSE_TIMEOUT_S)  # an exception raised by detect.page itself propagates
            except cf.TimeoutError:
                self._restart(ex)
                raise ParseFailed("parse_timeout")
            except cf.process.BrokenProcessPool:
                # the pool was broken or replaced, often because ANOTHER page timed out and its workers were
                # killed; this page is innocent, so it gets one more try on the new pool
                self._restart(ex)
                if attempt == 2:
                    raise ParseFailed("parse_crash")

    def _restart(self, broken):
        with self.lock:
            if self.ex is not broken:
                return                                   # another thread already replaced it
            # ProcessPoolExecutor cannot cancel a running task, so the stuck worker is killed. _processes is
            # private; if a future Python drops it, shutdown still happens but a stuck worker may linger.
            for proc in list((getattr(broken, "_processes", None) or {}).values()):
                proc.kill()
            broken.shutdown(wait=False, cancel_futures=True)
            self.ex = cf.ProcessPoolExecutor(self.workers)

    def close(self):
        if self.ex is not None:
            self.ex.shutdown()


# ---------------------------------------------------------------- JavaScript rendering (issue #6)
# A page whose visible text is under RENDER_MIN_CHARS and that carries a <script> is re-fetched in headless
# Chromium and parsed from the rendered DOM. Pages without scripts are not rendered: a browser would show the
# same text. Chromium identifies itself with the monitor's user agent and doesn't load images; like any browser it
# does load the page's own scripts and styles, so a rendered page costs its host more than one request.
RENDER_MIN_CHARS = 200
RENDER_TIMEOUT_S = 45
RENDER_SLOTS = threading.BoundedSemaphore(2)       # at most 2 browsers at once on the 2-CPU VM
CHROMIUM = next((shutil.which(b) for b in ("chromium", "chromium-browser", "google-chrome") if shutil.which(b)), None)
HAS_SCRIPT = re.compile(rb"<script\b", re.I)


class RenderFailed(Exception):
    pass


def render(url):
    """the page's DOM after JavaScript has run, as HTML. Chromium runs in its own process group, so a timeout
    kills its renderer and helper processes too, not just the parent."""
    with RENDER_SLOTS:
        try:
            prof = tempfile.mkdtemp(prefix="render-")
        except OSError as e:
            raise RenderFailed(f"render_failed: {e.__class__.__name__}")
        try:
            p = subprocess.Popen([CHROMIUM, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
                                  "--disable-extensions", "--mute-audio", "--blink-settings=imagesEnabled=false",
                                  f"--user-agent={UA}", f"--user-data-dir={prof}", "--virtual-time-budget=10000",
                                  "--dump-dom", url], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            try:
                out, _ = p.communicate(timeout=RENDER_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                raise RenderFailed("render_timeout")
            finally:
                try:
                    os.killpg(p.pid, signal.SIGKILL)       # whatever is left of this browser
                except ProcessLookupError:
                    pass
                p.wait()
        except OSError as e:
            raise RenderFailed(f"render_failed: {e.__class__.__name__}")
        finally:
            shutil.rmtree(prof, ignore_errors=True)
    if p.returncode not in (0, -signal.SIGKILL) or len(out) < 100:
        raise RenderFailed("render_failed")
    return out


class ParseFailed(Exception):
    pass


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
    parser: ParsePool | None = None
    render: bool = True


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
    reformatted: bool = False   # rewritten in a new snapshot format; not counted as a change
    removed: bool = False
    low_text: bool = False
    rendered: bool = False      # parsed from the DOM after JavaScript ran (#6)
    pdf: bool = False           # a PDF; its text is stored like a page (#7)
    scanned: bool = False       # a PDF with no text layer
    render_error: str = ""
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


OLD_FILES = ("main.md",)       # snapshot files of earlier formats, removed on rewrite


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
    rec.pdf = pdf.is_pdf(ctype, raw)
    if rec.pdf:                                  # a PDF on the candidate's own site (#7)
        if len(raw) >= MAX_BYTES:
            rec.error = "pdf_too_large"; return []
        try:
            pg = pdf.page(raw, r.url)
            rec.scanned = pg["meta"]["scanned"]
        except pdf.PdfFailed as e:
            rec.error = str(e); return []
    elif ctype and "html" not in ctype.lower():
        rec.error = "not_html"; return []
    else:
        enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        try:
            pg = run.parser.parse(raw.decode(enc, errors="replace"), r.url)
        except detect.UndiffableContentError:
            rec.error = "not_html"; return []
        except detect.EmptyDocument:
            rec.error = "empty_page"; return []
        except ParseFailed as e:
            rec.error = str(e); return []
    meta_path = os.path.join(page_dir, "meta.json")
    rec.first_seen = not os.path.exists(meta_path)
    try:
        prev = json.load(open(meta_path)) if not rec.first_seen else None
    except (OSError, ValueError):
        prev = {}
    if not rec.pdf and len(pg["text"]) < RENDER_MIN_CHARS and run.render and CHROMIUM and HAS_SCRIPT.search(raw):
        try:
            wait_turn(r.url)
            html2 = render(r.url)
            pg2 = run.parser.parse(html2.decode("utf-8", errors="replace"), r.url)
            if len(pg2["text"]) > len(pg["text"]):
                pg, raw, rec.rendered = pg2, html2, True
        except (RenderFailed, ParseFailed, detect.UndiffableContentError, detect.EmptyDocument) as e:
            rec.render_error = str(e) or type(e).__name__
            if prev and prev.get("rendered"):
                # yesterday's snapshot came from a rendered page: keep it rather than record the empty shell
                rec.error = "render_failed"; return []
    pg["meta"]["rendered"] = rec.rendered        # recorded in meta.json, not part of the fingerprint
    rec.text_chars, rec.low_text = len(pg["text"]), len(pg["text"]) < RENDER_MIN_CHARS
    ch = detect.changed(prev, pg["meta"])        # True / False; None = new page or older format
    rec.changed = ch is True
    rec.reformatted = ch is None and not rec.first_seen
    if ch is not False:
        # the snapshot is rewritten only when the detector reports a change, so noise never reaches Git
        os.makedirs(page_dir, exist_ok=True)
        write_if_changed(os.path.join(page_dir, "text.md"), ("\n".join(pg["lines"]) + "\n").encode())
        write_if_changed(os.path.join(page_dir, "links.json"), (json.dumps(pg["links"], indent=0, ensure_ascii=False) + "\n").encode())
        write_if_changed(os.path.join(page_dir, "media.json"), (json.dumps(pg["media"], indent=0, ensure_ascii=False) + "\n").encode())
        write_if_changed(meta_path, (json.dumps(pg["meta"], indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode())
        for old in OLD_FILES:
            if os.path.exists(os.path.join(page_dir, old)):
                os.remove(os.path.join(page_dir, old))
        if run.raw_dir:                          # raw HTML is kept for every recorded version
            d = os.path.join(run.raw_dir, run.day, rec.site_id); os.makedirs(d, exist_ok=True)
            ext = ".pdf.gz" if rec.pdf else ".html.gz"
            with gzip.open(os.path.join(d, ("_home" if rec.is_home else rec.page) + ext), "wb") as f:
                f.write(raw)
    return pg["hrefs"]


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


def git_ok(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True).returncode == 0


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
            "rendered": sum(1 for r in pages if r.rendered),                       # parsed after JavaScript ran
            "rendered_usable": sum(1 for r in pages if r.rendered and not r.low_text),
            "render_errors": sum(1 for r in pages if r.render_error),
            "chromium": CHROMIUM,                                                   # None = rendering unavailable
            "pdfs": sum(1 for r in pages if r.pdf and not r.error),
            "pdfs_scanned": sum(1 for r in pages if r.scanned and not r.error),
            "pdftotext": pdf.PDFTOTEXT,                                             # None = PDFs are skipped
            "sites_capped": sum(1 for s in sites if s.capped),
            "pages_fetched": sum(1 for r in pages if r.status != ""),
            "pages_ok": sum(1 for r in pages if not r.error and not r.removed),
            "pages_changed": sum(1 for r in pages if r.changed),
            "pages_reformatted": sum(1 for r in pages if r.reformatted),
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
    ap.add_argument("--no-render", action="store_true", help="never re-fetch low-text pages in Chromium")
    ap.add_argument("--parse-workers", type=int, default=max(1, (os.cpu_count() or 2)),
                    help="processes that parse pages (0 = parse in the fetching thread)")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.urls)))
    if a.limit: rows = rows[:a.limit]
    os.makedirs(os.path.join(a.repo, "logs"), exist_ok=True)
    if not os.path.isdir(os.path.join(a.repo, ".git")):
        git(a.repo, "init", "-q"); git(a.repo, "config", "user.name", "campaign-monitor")
        git(a.repo, "config", "user.email", "monitor@localhost")
    run = Run(a.repo, a.raw_dir, a.day or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
              a.max_depth, a.max_pages, ParsePool(a.parse_workers), not a.no_render)
    t0 = time.time(); sites = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(crawl_site, r, run) for r in rows]
        for i, f in enumerate(cf.as_completed(futs), 1):
            sites.append(f.result())
            if i % 250 == 0:
                print(f"  {i}/{len(rows)} sites  {sum(len(s.pages) for s in sites)} pages  {time.time()-t0:.0f}s", flush=True)
    run.parser.close()
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
    # change records (#9) with step-0 noise rules (#10), from the staged snapshot against yesterday's commit
    if git_ok(a.repo, "rev-parse", "--verify", "-q", "HEAD"):
        recs, _ = changes.records_between(a.repo, run.day, {r["site_id"]: r for r in rows}, "HEAD")
        rules = step0.load_site_rules(os.path.join(os.path.dirname(os.path.abspath(a.urls)), "site_noise.csv"))
        for r in recs:
            step0.apply(r, rules)
        changes.write_records(a.repo, run.day, recs)
        summ["change_records"] = len(recs)
        summ["change_records_kept"] = sum(1 for r in recs if not r["step0"]["discard"])
        # sites with many kept records today: candidates for a site rule in site_noise.csv (#10)
        busy = collections.Counter(r["site_id"] for r in recs if not r["step0"]["discard"] and r["kind"] in ("changed", "sitewide"))
        summ["busy_sites"] = {sid: n for sid, n in busy.most_common() if n > 3}
        with open(os.path.join(a.repo, "logs", f"{run.day}-summary.json"), "w") as f:
            json.dump(summ, f, indent=1, sort_keys=True); f.write("\n")
        git(a.repo, "add", "-A")
    git(a.repo, "commit", "-q", "--allow-empty", "-m",
        f"snapshot {run.day}: {len(rows)} sites, {summ['pages_ok']} pages, "
        f"{summ['pages_changed']} changed, {summ['pages_added']} added, {summ['pages_removed']} removed"
        + (f", {summ['pages_reformatted']} rewritten in snapshot format {detect.FORMAT}" if summ["pages_reformatted"] else ""))
    summ["commit"] = git(a.repo, "rev-parse", "--short", "HEAD").strip()
    json.dump(summ, open(a.summary, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
