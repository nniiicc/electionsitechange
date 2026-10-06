"""End-to-end test of the daily run (issues #2, #4, #5).

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


def noisy_page(days, raised, year, utm):
    """the same page on two days, differing only in noise: countdown widget, donation progress,
    copyright year, cookie banner wording and a tracking parameter on a link"""
    return (f'<html><head><title>Sam Roe</title></head><body><div id="cookie">This site uses cookies. '
            f'<button>Accept all</button></div><nav><a href="/issues?utm_campaign={utm}&amp;id=1">Issues</a></nav>'
            f'<main>{"".join(f"<p>{x}</p>" for x in OTHER)}'
            f'<div class="countdown"><span>{days}</span><span>Days</span><span>0{days % 7}</span><span>Hours</span></div>'
            f'<p>{days} days until Election Day</p><div class="thermo">${raised:,} raised of $50,000 goal</div></main>'
            f'<footer>Copyright © {year} Friends of Sam Roe. Paid for by Friends of Sam Roe.</footer></body></html>')


ACCORDION = ["Pat will cap insulin at $35 a month.", "Pat backs a public option in every county."]
ACCORDION2 = "Pat will cap insulin at $25 a month for every patient."


def collapsed_page(health):
    """content that a browser hides until clicked: a display:none tab and a <details> accordion"""
    return ('<html><head><title>Pat Moe</title></head><body><main><h1>Pat Moe</h1>'
            f'<p>{OTHER[0]}</p><div class="tab-pane" style="display:none" aria-hidden="true">'
            '<p>Pat grew up on a dairy farm outside town.</p></div>'
            f'<details><summary>Health care</summary>{"".join(f"<p>{x}</p>" for x in health)}</details>'
            '</main><footer>Paid for by Pat Moe for Congress.</footer></body></html>')


def photo_page(src, alt):
    return page("Ann Loe", OTHER).replace("<main>", f'<main><img src="{src}" alt="{alt}">')


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
    broken = {"index.html": page("Max Poe for State Senate", OTHER,
                                 [f"/a-missing{i}.html" for i in range(1, 4)] + [f"/p{i}.html" for i in range(1, 9)])}
    broken.update({f"p{i}.html": page(f"Page {i}", filler(f"topic {i}")) for i in range(1, 9)})
    return {
        "broken":    (broken, broken),  # 3 dead links first: they must not use up the page cap
        "limited":   (limited, limited),   # /a.html answers 429 Too Many Requests (see TooMany)
        "edited":    ({"index.html": page("Jane Doe for Congress", ISSUES)},
                      {"index.html": page("Jane Doe for Congress", [ISSUES[0], REWORDED, ISSUES[2]])}),
        "unchanged": (home(OTHER), home(OTHER)),
        "noisy":     ({"index.html": noisy_page(12, 12000, 2025, "fall")},
                      {"index.html": noisy_page(11, 14500, 2026, "gotv")}),
        "collapsed": ({"index.html": collapsed_page(ACCORDION)},
                      {"index.html": collapsed_page([ACCORDION2, ACCORDION[1]])}),
        "down":      (home(OTHER), None),
        "photo":     ({"index.html": photo_page("/img/ann-fair.jpg?v=1", "Ann at the county fair")},
                      {"index.html": photo_page("/img/ann-rally.jpg?v=9", "Ann at the county fair")}),
        "resized":   ({"index.html": photo_page("/img/ann-300x200.jpg?v=1", "Ann")},       # same image, new size
                      {"index.html": photo_page("/img/ann-600x400.jpg?v=2", "Ann")}),
        "campaign":  (camp1, camp2),
        "big":       (big, big),
    }


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serves files from a directory and records (time, path) of every request it gets."""
    def log_message(self, *a): pass
    def record(self): self.server.requests.append((time.monotonic(), self.path))
    def send_head(self):
        self.record(); return super().send_head()


class Forbidden(Quiet):
    """A site that answers every request with HTTP 403, as bot-blocking sites do."""
    def do_GET(self):
        self.record(); self.send_error(403)


class TooMany(Quiet):
    """Answers /a.html with HTTP 429, as a small server asking us to slow down."""
    def do_GET(self):
        if self.path == "/a.html":
            self.record(); self.send_error(429)
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
                         for sid in ("edited", "unchanged", "noisy", "down", "collapsed")}
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
        # day 2: 10 sites answered 200 (all but blocked and down); blocked answered 403; down never answered
        self.assertEqual(self.summary2["sites"], 12)
        self.assertEqual(self.summary2["reached"], 11)
        self.assertEqual(self.summary2["ok"], 10)
        self.assertEqual(self.summary2["errors"].get("http_403"), 1)

    # ---- full visible text and noise rules (#5)
    def test_text_in_hidden_tabs_and_accordions_is_captured(self):
        text = self.day1_text["collapsed"]
        self.assertIn("Pat grew up on a dairy farm outside town.", text)
        self.assertIn(ACCORDION[0], text)

    def test_edit_inside_collapsed_section_is_recorded(self):
        # text lines are sentences of the page text, so a line may start with a heading before the sentence
        rem, add = diff_lines(self.repo, "sites/collapsed/text.md")
        self.assertEqual(len(rem), 1); self.assertEqual(len(add), 1)
        self.assertTrue(rem[0].endswith(ACCORDION[0]), rem); self.assertTrue(add[0].endswith(ACCORDION2), add)
        self.assertEqual(self.log2["collapsed"]["changed"], "True")

    def test_text_is_stored_one_sentence_per_line(self):
        lines = Path(self.repo, "sites", "edited", "text.md").read_text().splitlines()
        for s in (ISSUES[0], REWORDED, ISSUES[2]):
            holders = [l for l in lines if s in l]
            self.assertEqual(len(holders), 1, (s, lines))
            self.assertTrue(holders[0].endswith(s), holders)      # nothing after the sentence on its line

    def test_each_page_stores_text_links_media_and_metadata(self):
        d = Path(self.repo, "sites", "noisy")
        self.assertEqual({f.name for f in d.iterdir()}, {"text.md", "links.json", "media.json", "meta.json"})
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(set(meta), {"format", "final_url", "title", "description", "paid_for_by", "years_mentioned", "fingerprint"})
        self.assertEqual(meta["title"], "Sam Roe")
        self.assertEqual(meta["paid_for_by"], "Paid for by Friends of Sam Roe")
        text = (d / "text.md").read_text()
        self.assertIn("Paid for by Friends of Sam Roe.", text)   # footer is in the text
        self.assertIn(OTHER[1], text)
        self.assertNotIn("cookies", text)                        # the cookie banner is removed

    def test_image_swap_is_recorded_in_media_list(self):
        rem, add = diff_lines(self.repo, "sites/photo/media.json")
        self.assertEqual(rem, ['"alt:/img/ann-fair.jpg|Ann at the county fair",', '"img:/img/ann-fair.jpg"'])
        self.assertEqual(add, ['"alt:/img/ann-rally.jpg|Ann at the county fair",', '"img:/img/ann-rally.jpg"'])
        self.assertEqual(self.log2["photo"]["changed"], "True")

    def test_same_image_at_another_size_is_not_a_change(self):
        self.assertEqual(git(self.repo, "diff", "--stat", "HEAD~1", "HEAD", "--", "sites/resized"), "")
        self.assertEqual(self.log2["resized"]["changed"], "False")

    def test_tracking_parameters_are_removed_from_links(self):
        links = json.loads(Path(self.repo, "sites", "noisy", "links.json").read_text())
        self.assertTrue(any(l["href"].endswith("/issues?id=1") for l in links), links)
        self.assertFalse(any("utm_" in l["href"] for l in links))

    def test_no_volatile_values_in_snapshot_files(self):
        for f in Path(self.repo, "sites").rglob("*"):
            if f.is_file():
                body = f.read_text()
                for v in (DAY1, DAY2, "elapsed", "fetched_at", "bytes"):
                    self.assertNotIn(v, body, f)

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
        self.assertTrue(any(l["href"].startswith(self.offsite_url) for l in links), links)
        self.assertEqual(self.offsite.requests, [])

    def test_requests_to_one_site_are_at_least_one_second_apart(self):
        times = sorted(t for t, _ in self.servers["campaign"].requests)
        self.assertGreater(len(times), 5)
        self.assertGreaterEqual(min(b - a for a, b in zip(times, times[1:])), 0.95)

    def test_page_cap_limits_pages_per_site_nearest_first(self):
        self.assertEqual(self.pages("big"), {f"p{i}.html" for i in range(1, MAX_PAGES)})   # homepage + 5
        self.assertEqual(self.summary2["sites_capped"], 2)                                 # big and broken

    def test_page_cap_counts_pages_captured_not_dead_links(self):
        self.assertEqual(self.pages("broken"), {f"p{i}.html" for i in range(1, MAX_PAGES)})

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
