"""Chromium rendering failure handling (issue #6), with a stand-in browser script; no real browser or site."""
import importlib.util, os, stat, subprocess, tempfile, time, unittest

spec = importlib.util.spec_from_file_location(
    "snapshot", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "snapshot.py"))
snapshot = importlib.util.module_from_spec(spec); spec.loader.exec_module(snapshot)


def fake_browser(body):
    f = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
    f.write("#!/bin/sh\n" + body + "\n"); f.close()
    os.chmod(f.name, os.stat(f.name).st_mode | stat.S_IEXEC)
    return f.name


class Render(unittest.TestCase):
    def setUp(self):
        self.saved = snapshot.CHROMIUM, snapshot.RENDER_TIMEOUT_S

    def tearDown(self):
        snapshot.CHROMIUM, snapshot.RENDER_TIMEOUT_S = self.saved

    def test_hung_browser_and_its_children_are_killed(self):
        # the "browser" starts a child that would outlive it, then hangs
        snapshot.CHROMIUM = fake_browser("sleep 300 & echo $! > /tmp/render_test_child.pid; sleep 300")
        snapshot.RENDER_TIMEOUT_S = 2
        t0 = time.time()
        with self.assertRaises(snapshot.RenderFailed) as e:
            snapshot.render("http://127.0.0.1/")
        self.assertEqual(str(e.exception), "render_timeout")
        self.assertLess(time.time() - t0, 10)
        time.sleep(0.5)
        pid = int(open("/tmp/render_test_child.pid").read())
        alive = subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0
        self.assertFalse(alive, "child process survived")

    def test_browser_output_is_returned(self):
        snapshot.CHROMIUM = fake_browser("echo '<html><body>" + "<p>rendered text</p>" * 20 + "</body></html>'")
        self.assertIn(b"rendered text", snapshot.render("http://127.0.0.1/"))

    def test_browser_that_fails_raises_render_failed(self):
        snapshot.CHROMIUM = fake_browser("exit 3")
        with self.assertRaises(snapshot.RenderFailed):
            snapshot.render("http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
