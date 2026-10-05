"""End-to-end test of the daily run (issues #2, #4).

Serves small fake campaign sites from local web servers, runs the real
monitor/snapshot.py over two simulated days, and checks what ended up in the
repository and the run log. Nothing here contacts a real website.

run:  ~/monitor/.venv/bin/python -m unittest discover -s tests -v
"""
import csv, functools, http.server, json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "snapshot.py")
DAY1, DAY2 = "2026-10-06", "2026-10-07"
MAX_PAGES = 6          # small cap so the cap test stays fast; the daily run uses 50

ISSUES = [
    "Jane Doe will fight to lower property taxes for working families across the district.",
    "She supports expanding rural broadband so every household can get online.",
    "Jane believes public schools deserve full funding and smaller class sizes.",
]
REWORDED = "She supports expanding rural broadband and cell coverage so every household can get online."
OTHER = [
    "Sam Roe is a nurse and small business owner running for State Senate.",
    "Sam will protect access to affordable health care in every county.",
    "Sam has lived in the district for thirty years with his family.",
]


def page(title, paras, links=()):
    nav = "".join(f'<a href="{h}">{h}</a> ' for h in links)
    body = "".join(f"<p>{p}</p>" for p in paras)
    return (f"<html><head><title>{title}</title></head><body><nav>{nav}</nav><main><h1>{title}</h1>"
            f"{body}</main><footer>Paid for by Friends of {title}.</footer></body></html>")


def filler(topic):
    return [f"This page explains the candidate's plan on {topic} in detail for voters.",
            f"Read more about why {topic} matters to families across the district."]


def build_sites(offsite):
    """site -> (day-1 files, day-2 files); None on day 2 means the site is unreachable."""
    home = lambda paras: {"index.html": page("Home", paras)}
    camp1 = {
        "robots.txt": "User-agent: *\nDisallow: /private.html\n",
        "index.html": page("Pat Moe for Congress", OTHER,
                           ["/issues.html", "/about.html", "/private.html", offsite + "/donate"]),
        "issues.html": page("Issues", filler("issues"), ["/issues-taxes.html"]),          # depth 1
        "issues-taxes.html": page("Taxes", filler("taxes"), ["/deep3.html"]),            # depth 2
        "deep3.html": page("Deep three", filler("roads"), ["/deep4.html"]),              # depth 3
        "deep4.html": page("Deep four", filler("bridges")),                              # depth 4: never fetched
        "about.html": page("About", filler("biography")),
        "private.html": page("Private", filler("internal")),                             # robots-disallowed
    }
    camp2 = {k: v for k, v in camp1.items() if k != "about.html"}                         # about page deleted
    camp2["index.html"] = page("Pat Moe for Congress", OTHER,
                               ["/issues.html", "/endorsements.html", "/private.html", offsite + "/donate"])
    camp2["endorsements.html"] = page("Endorsements", filler("endorsements"))           # new page
    big = {"index.html": page("Big Site", OTHER, [f"/p{i}.html" for i in range(1, 9)])}
    big.update({f"p{i}.html": page(f"Page {i}", filler(f"topic {i}")) for i in range(1, 9)})
    limited = {"index.html": page("Lou Hoe for State House", OTHER, ["/a.html", "/b.html"]),
               "a.html": page("A", filler("a")), "b.html": page("B", filler("b"))}
    return {
        "limited":   (limited, limited),   # /a.html answers 429 Too Many Requests (see TooMany)
        "edited":    ({"index.html": page("Jane Doe for Congress", ISSUES)},
                      {"index.html": page("Jane Doe for Congress", [ISSUES[0], REWORDED, ISSUES[2]])}),
        "unchanged": (home(OTHER), home(OTHER)),
        "noisy":     (home(OTHER + ["12 days until Election Day", "$12,000 raised of $50,000 goal"]),
                      home(OTHER + ["11 days until Election Day", "$14,500 raised of $50,000 goal"])),
        "down":      (home(OTHER), None),
        "campaign":  (camp1, camp2),
        "big":       (big, big),
    }


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serves files from a directory and records (time, path) of every request it gets."""
    def log_message(self, *a): pass
    def send_head(self):
        self.server.requests.append((time.monotonic(), self.path))
        return super().send_head()


class Forbidden(Quiet):
    """A site that answers every request with HTTP 403, as bot-blocking sites do."""
    def do_GET(self):
        self.server.requests.append((time.monotonic(), self.path)); self.send_error(403)


class TooMany(Quiet):
    """Answers /a.html with HTTP 429, as a small server asking us to slow down."""
    def do_GET(self):
        if self.path == "/a.html":
            self.server.requests.append((time.monotonic(), self.path)); self.send_error(429)
        else:
            super().do_GET()


def serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.requests = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def serve_dir(directory):
    return serve(functools.partial(Quiet, directory=directory))


def write_files(directory, files):
    for p in Path(directory).iterdir(): p.unlink()
    for name, body in files.items(): Path(directory, name).write_text(body)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def diff_lines(repo, path):
    """(removed, added) lines of `path` between the last two commits."""
    out = git(repo, "diff", "--unified=0", "HEAD~1", "HEAD", "--", path)
    rem = [l[1:] for l in out.splitlines() if l.startswith("-") and not l.startswith("---")]
    add = [l[1:] for l in out.splitlines() if l.startswith("+") and not l.startswith("+++")]
    return rem, add


class DailyRunOverTwoDays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = cls.tmp.name
        cls.repo = os.path.join(t, "repo")
        os.makedirs(cls.repo)
        cls.offsite = serve_dir(t)                       # another host: must never be requested
        cls.offsite_url = f"http://127.0.0.1:{cls.offsite.server_address[1]}"
        cls.sites = build_sites(cls.offsite_url)
        cls.servers, docroots = {}, {}
        for sid, (day1, _) in cls.sites.items():
            docroots[sid] = os.path.join(t, "www", sid)
            os.makedirs(docroots[sid])
            write_files(docroots[sid], day1)
            cls.servers[sid] = (serve(functools.partial(TooMany, directory=docroots[sid])) if sid == "limited"
                                else serve_dir(docroots[sid]))
        cls.servers["blocked"] = serve(Forbidden)        # reached, but refuses: HTTP 403 both days
        urls = os.path.join(t, "urls.csv")
        with open(urls, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["site_id", "url"])
            for sid, srv in cls.servers.items():
                w.writerow([sid, f"http://127.0.0.1:{srv.server_address[1]}/"])

        def run(day):
            subprocess.run([sys.executable, SNAPSHOT, urls, cls.repo, "--workers", "4",
                            "--max-pages", str(MAX_PAGES),
                            "--raw-dir", os.path.join(t, "raw"), "--summary", os.path.join(t, "s.json"),
                            "--day", day], check=True, capture_output=True, text=True, timeout=120)

        t0 = time.monotonic()
        run(DAY1)
        cls.day1_text = {sid: Path(cls.repo, "sites", sid, "text.md").read_text()
                         for sid in ("edited", "unchanged", "noisy", "down")}
        for sid, (_, day2) in cls.sites.items():         # switch every site to its day-2 version
            if day2 is None:
                cls.servers[sid].shutdown(); cls.servers[sid].server_close()
            else:
                write_files(docroots[sid], day2)
        run(DAY2)
        cls.elapsed = time.monotonic() - t0
        with open(os.path.join(cls.repo, "logs", f"{DAY2}.csv")) as f:
            cls.rows2 = list(csv.DictReader(f))
        cls.log2 = {r["site_id"]: r for r in cls.rows2 if r["page"] == "/"}     # homepage rows
        cls.summary2 = json.loads(Path(cls.repo, "logs", f"{DAY2}-summary.json").read_text())

    @classmethod
    def tearDownClass(cls):
        for srv in [*cls.servers.values(), cls.offsite]:
            srv.shutdown(); srv.server_close()
        cls.tmp.cleanup()

    def pages(self, sid):
        """captured internal pages of a site, by file name (slug minus its hash suffix)"""
        d = Path(self.repo, "sites", sid, "pages")
        return {p.name.rsplit("-", 1)[0] for p in d.iterdir()} if d.exists() else set()

    def requested(self, sid):
        return [path for _, path in self.servers[sid].requests]

    # ---- homepage behaviour (#2)
    def test_each_run_is_one_commit(self):
        self.assertEqual(git(self.repo, "rev-list", "--count", "HEAD").strip(), "2")

    def test_edited_page_records_exactly_the_reworded_sentence(self):
        self.assertEqual(diff_lines(self.repo, "sites/edited/text.md"), ([ISSUES[1]], [REWORDED]))

    def test_unchanged_page_records_no_change(self):
        self.assertEqual(git(self.repo, "diff", "--stat", "HEAD~1", "HEAD", "--", "sites/unchanged"), "")
        self.assertEqual(self.log2["unchanged"]["changed"], "False")

    def test_noise_only_change_records_no_change(self):
        self.assertEqual(git(self.repo, "diff", "--stat", "HEAD~1", "HEAD", "--", "sites/noisy"), "")
        self.assertEqual(self.log2["noisy"]["changed"], "False")

    def test_unreachable_site_keeps_last_good_snapshot(self):
        self.assertEqual(git(self.repo, "diff", "--stat", "HEAD~1", "HEAD", "--", "sites/down"), "")
        self.assertEqual(Path(self.repo, "sites", "down", "text.md").read_text(), self.day1_text["down"])
        self.assertIn(OTHER[0], self.day1_text["down"])          # the kept snapshot is real content
        self.assertNotEqual(self.log2["down"]["error"], "")      # and the failure is logged

    def test_summary_counts_sites_reached_separately_from_fetched_ok(self):
        # day 2: limited, edited, unchanged, noisy, campaign, big answered 200; blocked 403; down never answered
        self.assertEqual(self.summary2["sites"], 8)
        self.assertEqual(self.summary2["reached"], 7)
        self.assertEqual(self.summary2["ok"], 6)
        self.assertEqual(self.summary2["errors"].get("http_403"), 1)

    # ---- full-site crawl (#4)
    def test_crawl_follows_internal_links_up_to_three_clicks(self):
        self.assertEqual(self.pages("campaign"),
                         {"issues.html", "issues-taxes.html", "deep3.html", "endorsements.html"})
        self.assertNotIn("/deep4.html", self.requested("campaign"))          # 4 clicks deep

    def test_robots_disallowed_page_is_never_requested(self):
        self.assertIn("/robots.txt", self.requested("campaign"))
        self.assertNotIn("/private.html", self.requested("campaign"))

    def test_offsite_links_are_recorded_but_not_fetched(self):
        links = json.loads(Path(self.repo, "sites", "campaign", "links.json").read_text())
        self.assertTrue(any(l.startswith(self.offsite_url) for l in links), links)
        self.assertEqual(self.offsite.requests, [])

    def test_requests_to_one_site_are_at_least_one_second_apart(self):
        times = sorted(t for t, _ in self.servers["campaign"].requests)
        self.assertGreater(len(times), 5)
        self.assertGreaterEqual(min(b - a for a, b in zip(times, times[1:])), 0.95)

    def test_page_cap_limits_pages_per_site_nearest_first(self):
        self.assertEqual(self.pages("big"), {f"p{i}.html" for i in range(1, MAX_PAGES)})   # homepage + 5
        self.assertEqual(self.summary2["sites_capped"], 1)

    def test_removed_and_added_pages_are_recorded(self):
        # --no-renames: two pages with identical files (e.g. empty links.json) must not look like a rename
        st = git(self.repo, "diff", "--name-status", "--no-renames", "HEAD~1", "HEAD", "--", "sites/campaign/pages")
        status = {(l.split("\t")[0], Path(l.split("\t")[1]).parent.name.rsplit("-", 1)[0]) for l in st.splitlines()}
        self.assertEqual(status, {("D", "about.html"), ("A", "endorsements.html")})
        rows = {r["page"].rsplit("-", 1)[0]: r for r in self.rows2 if r["site_id"] == "campaign"}
        self.assertEqual(rows["about.html"]["removed"], "True")
        self.assertEqual(rows["endorsements.html"]["first_seen"], "True")
        self.assertEqual(self.summary2["pages_removed"], 1)

    def test_site_answering_429_is_left_alone_for_the_rest_of_the_day(self):
        req = self.requested("limited")
        self.assertEqual(req.count("/a.html"), 2)        # once per day, then the crawl of that site stops
        self.assertNotIn("/b.html", req)

    def test_runs_in_under_two_minutes(self):
        self.assertLess(self.elapsed, 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
