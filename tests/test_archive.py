"""Wayback queue, results and record links (issue #8), on hand-made files; nothing is submitted."""
import csv, importlib.util, json, os, tempfile, unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "archive", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "archive.py"))
archive = importlib.util.module_from_spec(spec); spec.loader.exec_module(archive)
DAY = "2026-10-09"


def rec(site, page, kind="changed", url=None, discard=False):
    return {"change_id": f"{site}:{page}", "site_id": site, "page": page, "kind": kind, "url": url,
            "step0": {"discard": discard}, "wayback": {"before": None, "after": None}}


class Archive(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); t = Path(self.t.name)
        self.repo, self.state = t / "repo", t / "state"
        (self.repo / "monitor").mkdir(parents=True); (self.repo / "changes").mkdir()
        (self.repo / "monitor" / "monitor_urls.csv").write_text(
            "site_id,url\na,https://a.test/\nb,https://b.test/\nc,https://c.test/\nd,https://d.test/\n")
        recs = [rec("a", "about-1", url="https://a.test/about"), rec("b", "/", url="https://b.test/"),
                rec("c", "*", kind="sitewide", url="https://c.test/"),
                rec("a", "news-2", url="https://a.test/news", discard=True),
                rec("a", "old-3", kind="removed", url="https://a.test/old")]
        (self.repo / "changes" / f"{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))

    def tearDown(self):
        self.t.cleanup()

    def queued(self, kind):
        return (self.state / "queue" / f"{DAY}-{kind}.txt").read_text().split()

    def test_queue_order_and_what_is_left_out(self):
        out = archive.queue(str(self.repo), DAY, str(self.state), 10)
        # homepages first (b, and c's homepage for its site-wide change), then other pages;
        # noise-only and removed pages are not submitted
        self.assertEqual(self.queued("changed"), ["https://b.test/", "https://c.test/", "https://a.test/about"])
        # first round: homepages never archived and not already queued today
        self.assertEqual(self.queued("backlog"), ["https://a.test/", "https://d.test/"])
        self.assertEqual(out["homepages_never_archived"], 4)

    def test_priority_new_pages_then_text_changes_then_image_only(self):
        recs = [rec("a", "img-1", url="https://a.test/img") | {"media": {"removed": ["img:x"], "added": ["img:y"]}},
                rec("a", "plan-2", url="https://a.test/plan") | {"text": {"removed": ["Old."], "added": ["New."]}},
                rec("a", "new-3", kind="added", url="https://a.test/new"), rec("d", "/", url="https://d.test/")]
        (self.repo / "changes" / f"{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        archive.queue(str(self.repo), DAY, str(self.state), 0)
        self.assertEqual(self.queued("changed"), ["https://d.test/", "https://a.test/new", "https://a.test/plan", "https://a.test/img"])

    def test_backlog_size_is_capped(self):
        archive.queue(str(self.repo), DAY, str(self.state), 1)
        self.assertEqual(self.queued("backlog"), ["https://a.test/"])

    def write_run(self, kind, captures, failed=""):
        d = self.state / "runs" / f"{DAY}-{kind}"; d.mkdir(parents=True)
        (d / "captures.log").write_text("".join(f"/web/{ts}/{u}\n" for ts, u in captures))
        if failed:
            (d / "failed.log").write_text(failed)

    def test_record_reads_captures_and_failures(self):
        archive._write(str(self.state / "homepages.txt"), ["https://a.test/", "https://b.test/", "https://c.test/", "https://d.test/"])
        archive.queue(str(self.repo), DAY, str(self.state), 10)
        self.write_run("changed", [("20261009120000", "https://b.test/"), ("20261009120500", "https://a.test/about")],
                       failed="2026-10-09 12:01:00 [error:http-status-403] https://c.test/\n")
        self.write_run("backlog", [("20261009130000", "https://d.test/")])
        archive.record(str(self.state), DAY)
        rows = {r["url"]: r for r in csv.DictReader(open(self.state / "results" / f"{DAY}.csv"))}
        self.assertEqual(rows["https://b.test/"]["capture"], "https://web.archive.org/web/20261009120000/https://b.test/")
        self.assertEqual(rows["https://c.test/"]["status"], "failed: error:http-status-403")
        self.assertEqual(rows["https://a.test/"]["status"], "not_captured")
        # captured homepages, and ones Save Page Now gave up on, leave the first-round backlog
        self.assertEqual(archive.done_homepages(str(self.state)), {"b.test", "c.test", "d.test"})

    def test_rerun_keeps_earlier_captures_and_reads_invalid_log(self):
        archive.queue(str(self.repo), DAY, str(self.state), 0)
        self.write_run("changed", [("20261009120000", "https://b.test/")])
        os.rename(self.state / "runs" / f"{DAY}-changed", self.state / "runs" / f"{DAY}-changed.1")
        self.write_run("changed", [("20261009150000", "https://a.test/about")])
        (self.state / "runs" / f"{DAY}-changed" / "invalid.log").write_text(
            '2026-10-09 15:01:00 https://c.test/\n{"status":"error","message":"Bad request"}\n')
        archive.record(str(self.state), DAY)
        rows = {r["url"]: r for r in csv.DictReader(open(self.state / "results" / f"{DAY}.csv"))}
        self.assertEqual(rows["https://b.test/"]["status"], "captured")          # from the earlier run
        self.assertEqual(rows["https://a.test/about"]["status"], "captured")
        self.assertTrue(rows["https://c.test/"]["status"].startswith("failed: invalid"))

    def test_apply_fills_before_and_after_links(self):
        res = self.state / "results"; res.mkdir(parents=True)
        (res / "2026-10-07.csv").write_text("url,queue,capture,status\nhttps://b.test/,backlog,"
                                            "https://web.archive.org/web/20261007100000/https://b.test/,captured\n")
        (res / f"{DAY}.csv").write_text("url,queue,capture,status\nhttps://b.test/,changed,"
                                        "https://web.archive.org/web/20261009120000/https://b.test/,captured\n")
        archive.apply(str(self.repo), str(self.state))
        recs = {r["change_id"]: r for r in map(json.loads, open(self.repo / "changes" / f"{DAY}.jsonl"))}
        self.assertEqual(recs["b:/"]["wayback"], {"before": "https://web.archive.org/web/20261007100000/https://b.test/",
                                                 "after": "https://web.archive.org/web/20261009120000/https://b.test/"})
        self.assertEqual(recs["a:about-1"]["wayback"], {"before": None, "after": None})
        # a later day's capture is not that day's "after"
        (res / f"{DAY}.csv").write_text("url,queue,capture,status\n")
        (res / "2026-10-12.csv").write_text("url,queue,capture,status\nhttps://b.test/,backlog,"
                                            "https://web.archive.org/web/20261012100000/https://b.test/,captured\n")
        archive.apply(str(self.repo), str(self.state))
        recs = {r["change_id"]: r for r in map(json.loads, open(self.repo / "changes" / f"{DAY}.jsonl"))}
        self.assertIsNone(recs["b:/"]["wayback"]["after"])
        self.assertTrue((self.repo / "wayback" / f"{DAY}.csv").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
