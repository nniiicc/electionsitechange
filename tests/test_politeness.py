"""Unit check of per-site request spacing (issue #4): www.x and x are one site."""
import importlib.util, os, time, unittest

spec = importlib.util.spec_from_file_location(
    "snapshot", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "snapshot.py"))
snapshot = importlib.util.module_from_spec(spec); spec.loader.exec_module(snapshot)


class RequestSpacing(unittest.TestCase):
    def test_www_and_bare_domain_share_one_request_queue(self):
        snapshot.wait_turn("https://www.janedoe2026.test/issues")
        t0 = time.monotonic()
        snapshot.wait_turn("https://janedoe2026.test/about")          # no network: wait_turn only waits
        self.assertGreaterEqual(time.monotonic() - t0, snapshot.HOST_GAP_S - 0.05)

    def test_different_sites_do_not_wait_for_each_other(self):
        snapshot.wait_turn("https://pat-moe.test/")
        t0 = time.monotonic()
        snapshot.wait_turn("https://sam-roe.test/")
        self.assertLess(time.monotonic() - t0, 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
