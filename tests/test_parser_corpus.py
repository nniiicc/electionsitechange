"""Acceptance test for the page parser (issue #5): the labelled corpus from the parser evaluation.

97 real campaign pages (tests/corpus/pages) get one labelled change each: the parser evaluation's 1,040 edits,
871 noise changes and 97 unchanged copies, plus 97 encoded-email edits and 291 noise pairs of three kinds found on
real sites (Cloudflare email re-encoding, form honeypot labels, dates in links). Edits must be detected at the
right place; noise and unchanged copies must not be detected. A second
noise set of 1,552 pairs (tests/corpus/holdout_noise.py; not independent, see its docstring) must not be flagged either.
Takes about 25 minutes on the VM's 2 CPUs, so it runs only when asked; run it before pushing ANY
change to monitor/detect.py (CONTRIBUTING.md):

  RUN_CORPUS_TEST=1 ~/monitor/.venv/bin/python -m unittest discover -s tests -p test_parser_corpus.py -v
"""
import json, os, sys, unittest

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
sys.path.insert(0, CORPUS)
import holdout_noise, make_pairs, score  # noqa: E402


def failures(results):
    return [{k: r.get(k) for k in ("pair_id", "problem", "reported")} for r in results if not r["ok"]]


@unittest.skipUnless(os.environ.get("RUN_CORPUS_TEST"), "slow acceptance test; set RUN_CORPUS_TEST=1")
class LabelledCorpus(unittest.TestCase):
    def test_labels_are_reproducible(self):
        with open(os.path.join(CORPUS, "labels.jsonl")) as f:
            committed = [json.loads(l) for l in f]
        self.assertEqual(make_pairs.labels(CORPUS), committed)

    def test_every_edit_detected_and_no_noise_flagged(self):
        res = score.run(make_pairs.pairs(CORPUS))
        # the evaluation's 2,008 pairs (1,040 edits) plus 4 types per page found on real sites (3 noise, 1 edit)
        self.assertEqual(len(res), 2008 + 4 * 97)
        self.assertEqual(sum(r["kind"] == "edit" for r in res), 1040 + 97)
        self.assertEqual(failures(res), [])

    def test_held_out_noise_not_flagged(self):
        res = score.run(holdout_noise.pairs(CORPUS))
        self.assertEqual(len(res), 97 * len(holdout_noise.HOLDOUT))
        self.assertEqual(failures(res), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
