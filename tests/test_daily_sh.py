"""End-to-end test of monitor/daily.sh, the script cron runs (issues #1, #2).

Builds a throwaway monitor folder whose "GitHub" is a local bare repository, serves one
fake campaign site, and runs the real daily.sh against it. Checks that it commits and
pushes, takes in a commit made on GitHub, discards half-written files from an earlier
crashed run, and skips when another run holds the lock. Nothing here touches the real
~/monitor folder, the real GitHub repository or any real website.

run:  ~/monitor/.venv/bin/python -m unittest discover -s tests -v
"""
import fcntl, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

from test_daily_run import page, serve_dir, OTHER

CODE = Path(__file__).resolve().parent.parent / "monitor"
GIT_ENV = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@localhost",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@localhost"}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout


class DailyShAgainstLocalGitHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Safety: an older daily.sh ignores MONITOR_HOME and would run the REAL job.
        if "MONITOR_HOME" not in (CODE / "daily.sh").read_text():
            raise RuntimeError("daily.sh does not support MONITOR_HOME; refusing to run it")
        cls.tmp = tempfile.TemporaryDirectory(); t = Path(cls.tmp.name)
        cls.mon = t / "monitor"; cls.origin = t / "origin.git"; author = t / "author"
        cls.www = t / "www"; cls.www.mkdir()
        (cls.www / "index.html").write_text(page("Sam Roe for State Senate", OTHER))
        cls.srv = serve_dir(str(cls.www))

        # "GitHub": a bare repo holding the monitor code and a one-site URL list
        git(t, "init", "-q", "--bare", "-b", "main", str(cls.origin))
        git(t, "init", "-q", "-b", "main", str(author))
        (author / "monitor").mkdir()
        for f in ("snapshot.py", "daily.sh"):
            shutil.copy(CODE / f, author / "monitor" / f)
        (author / "monitor" / "monitor_urls.csv").write_text(
            f"site_id,url\nroe,http://127.0.0.1:{cls.srv.server_address[1]}/\n")
        git(author, "add", "-A"); git(author, "commit", "-q", "-m", "code")
        git(author, "remote", "add", "origin", str(cls.origin)); git(author, "push", "-q", "origin", "main")

        # the VM's daily-run clone
        cls.mon.mkdir(); git(t, "clone", "-q", str(cls.origin), str(cls.mon / "snapshots"))
        # someone edits the README on GitHub after the clone
        (author / "README.md").write_text("edited on GitHub\n")
        git(author, "add", "README.md"); git(author, "commit", "-q", "-m", "readme"); git(author, "push", "-q", "origin", "main")
        # an earlier run crashed, leaving a half-written snapshot behind
        partial = cls.mon / "snapshots" / "sites" / "partial"; partial.mkdir(parents=True)
        (partial / "text.md").write_text("half-written\n")

        cls.rc = cls.run_daily()
        cls.log_after_run = (cls.mon / "runs.log").read_text()
        cls.tree = git(cls.origin, "ls-tree", "-r", "--name-only", "main").split()
        cls.head_msg = git(cls.origin, "log", "-1", "--format=%s", "main").strip()

    @classmethod
    def run_daily(cls):
        env = {**os.environ, **GIT_ENV, "MONITOR_HOME": str(cls.mon), "MONITOR_PY": sys.executable}
        return subprocess.run(["bash", str(CODE / "daily.sh")], env=env, timeout=120,
                              capture_output=True, text=True).returncode

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.tmp.cleanup()

    def test_run_commits_snapshot_and_pushes_it(self):
        self.assertEqual(self.rc, 0)
        self.assertTrue(self.head_msg.startswith("snapshot "), self.head_msg)
        self.assertIn("sites/roe/text.md", self.tree)
        self.assertIn("pushed", self.log_after_run)

    def test_commit_made_on_github_is_kept_and_does_not_block_push(self):
        self.assertIn("README.md", self.tree)

    def test_half_written_files_from_a_crashed_run_are_discarded(self):
        self.assertNotIn("sites/partial/text.md", self.tree)

    def test_second_run_is_skipped_while_another_holds_the_lock(self):
        before = git(self.origin, "rev-parse", "main")
        with open(self.mon / ".daily.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rc = self.run_daily()
        self.assertEqual(rc, 0)
        self.assertEqual(git(self.origin, "rev-parse", "main"), before)
        self.assertTrue((self.mon / "runs.log").read_text().rstrip().endswith("skipped"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
