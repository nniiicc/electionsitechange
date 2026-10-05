"""Noise rules (issue #5): widgets are dropped, real campaign content is kept."""
import importlib.util, os, unittest

spec = importlib.util.spec_from_file_location(
    "snapshot", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor", "snapshot.py"))
snapshot = importlib.util.module_from_spec(spec); spec.loader.exec_module(snapshot)

NOISE = ["12 days until Election Day", "Only 11 days to go!", "Days", "04", "12Days05Hours", "12 : 05 : 33",
         "1,234", "$14,500 raised of $50,000 goal", "72% funded", "Goal: $50,000", "1,204 donors and counting",
         "This website uses cookies to improve your experience.", "Accept all", "Cookie settings"]
CONTENT = ["Thank you to our 500 donors who helped us reach this goal.",
           "The campaign accepted contributions from over 2,000 small donors last year.",
           "I have raised taxes on no one and will fight for schools across our whole district every day.",
           "202-555-0100", "(202) 555-0100", "11/04/2026", "Vote by Nov. 3", "Jane has 3 children and 2 dogs.",
           "We use cookies and local flour in every batch at our family bakery.",
           "In 2 years we will fix every road in the county.", "Pat will cap insulin at $35 a month."]


class NoiseRules(unittest.TestCase):
    def test_widget_lines_are_noise(self):
        for s in NOISE:
            with self.subTest(s=s): self.assertTrue(snapshot.is_noise(s))

    def test_campaign_content_is_kept(self):
        for s in CONTENT:
            with self.subTest(s=s): self.assertFalse(snapshot.is_noise(s))

    def test_copyright_year_is_neutralised_without_dropping_the_line(self):
        self.assertEqual(snapshot.sentences(["Copyright © 2025 Friends of Jane. Paid for by Friends of Jane."]),
                         ["© YEAR Friends of Jane.", "Paid for by Friends of Jane."])


if __name__ == "__main__":
    unittest.main(verbosity=2)
