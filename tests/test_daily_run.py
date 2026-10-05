"""End-to-end test of the daily run (issue #2).

Serves small fake campaign sites from local web servers, runs the real
monitor/snapshot.py over two simulated days, and checks what ended up in the
repository and the run log. Nothing here contacts a real website.

run:  ~/monitor/.venv/bin/python tests/test_daily_run.py
"""
import csv, functools, http.server, json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "snapshot.py")
DAY1, DAY2 = "2026-10-06", "2026-10-07"

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


def page(title, paras):
    body = "".join(f"<p>{p}</p>" for p in paras)
    return (f"<html><head><title>{title}</title></head><body><main><h1>{title}</h1>{body}</main>"
            f"<footer>Paid for by Friends of {title}.</footer></body></html>")


# site -> (day-1 html, day-2 html); None on day 2 means the site is unreachable
SITES = {
    "edited":    (page("Jane Doe for Congress", ISSUES),
                  page("Jane Doe for Congress", [ISSUES[0], REWORDED, ISSUES[2]])),
    "unchanged": (page("Sam Roe for State Senate", OTHER),
                  page("Sam Roe for State Senate", OTHER)),
    "noisy":     (page("Ann Poe for Governor", OTHER + ["12 days until Election Day",
                                                        "$12,000 raised of $50,000 goal"]),
                  page("Ann Poe for Governor", OTHER + ["11 days until Election Day",
                                                        "$14,500 raised of $50,000 goal"])),
    "down":      (page("Lee Coe for Attorney General", OTHER), None),
}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


class Forbidden(Quiet):
    """A site that answers every request with HTTP 403, as bot-blocking sites do."""
    def do_GET(self): self.send_error(403)


def serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def serve_dir(directory):
    return serve(functools.partial(Quiet, directory=directory))


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
        cls.servers, docroots = {}, {}
        for sid, (day1, _) in SITES.items():
            docroots[sid] = os.path.join(t, "www", sid)
            os.makedirs(docroots[sid])
            Path(docroots[sid], "index.html").write_text(day1)
            cls.servers[sid] = serve_dir(docroots[sid])
        cls.servers["blocked"] = serve(Forbidden)        # reached, but refuses: HTTP 403 both days
        urls = os.path.join(t, "urls.csv")
        with open(urls, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["site_id", "url"])
            for sid, srv in cls.servers.items():
                w.writerow([sid, f"http://127.0.0.1:{srv.server_address[1]}/"])

        def run(day):
            subprocess.run([sys.executable, SNAPSHOT, urls, cls.repo, "--workers", "4",
                            "--raw-dir", os.path.join(t, "raw"), "--summary", os.path.join(t, "s.json"),
                            "--day", day], check=True, capture_output=True, text=True, timeout=120)

        t0 = time.monotonic()
        run(DAY1)
        cls.day1_text = {sid: Path(cls.repo, "sites", sid, "text.md").read_text() for sid in SITES}
        for sid, (_, day2) in SITES.items():           # switch every site to its day-2 version
            if day2 is None:
                cls.servers[sid].shutdown(); cls.servers[sid].server_close()
            else:
                Path(docroots[sid], "index.html").write_text(day2)
        run(DAY2)
        cls.elapsed = time.monotonic() - t0
        with open(os.path.join(cls.repo, "logs", f"{DAY2}.csv")) as f:
            cls.log2 = {r["site_id"]: r for r in csv.DictReader(f)}
        cls.summary2 = json.loads(Path(cls.repo, "logs", f"{DAY2}-summary.json").read_text())

    @classmethod
    def tearDownClass(cls):
        for srv in cls.servers.values():
            srv.shutdown(); srv.server_close()
        cls.tmp.cleanup()

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
        self.assertEqual(Path(self.repo, "sites", "down", "text.md").read_text(),
                         self.day1_text["down"])
        self.assertIn(OTHER[0], self.day1_text["down"])          # the kept snapshot is real content
        self.assertNotEqual(self.log2["down"]["error"], "")      # and the failure is logged

    def test_summary_counts_sites_reached_separately_from_fetched_ok(self):
        # day 2: edited, unchanged, noisy answered 200; blocked answered 403; down never answered
        self.assertEqual(self.summary2["sites"], 5)
        self.assertEqual(self.summary2["reached"], 4)
        self.assertEqual(self.summary2["ok"], 3)
        self.assertEqual(self.summary2["errors"].get("http_403"), 1)

    def test_runs_in_under_two_minutes(self):
        self.assertLess(self.elapsed, 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
