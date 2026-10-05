"""The monitored site list agrees with the attribution check (issue #3)."""
import csv, os, unittest

MON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor")
read = lambda f: list(csv.DictReader(open(os.path.join(MON, f), newline="")))


class SiteList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.urls = read("monitor_urls.csv")
        cls.ids = [r["site_id"] for r in cls.urls]
        cls.excluded = read("excluded_sites.csv")
        cls.flags = read("site_flags.csv")

    def test_site_ids_are_unique(self):
        self.assertEqual(len(self.ids), len(set(self.ids)))

    def test_wrong_entity_sites_are_not_monitored(self):
        self.assertTrue(self.excluded)
        self.assertEqual({r["site_id"] for r in self.excluded} & set(self.ids), set())

    def test_every_exclusion_records_a_reason_and_date(self):
        for r in self.excluded:
            with self.subTest(site=r["site_id"]):
                self.assertTrue(r["reason"].strip()); self.assertTrue(r["decided"].strip())

    def test_flagged_sites_stay_monitored(self):
        self.assertEqual({r["site_id"] for r in self.flags} - set(self.ids), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
