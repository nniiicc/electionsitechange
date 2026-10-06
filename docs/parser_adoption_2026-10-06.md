# Parser adoption, 6 Oct 2026 (issue #5)

The daily run now parses pages with `monitor/detect.py`, the method chosen by the parser evaluation
(`docs/parser_evaluation_2026-10-06.md`):

- visible text and outgoing links from EDGI `web-monitoring-diff` (`html_text_diff`, `links_diff`), compared with
  whitespace ignored;
- an image-and-embed list (images normalised so another size of the same image compares equal, alt texts, video and
  iframe sources);
- noise rules applied to the HTML first (all in `detect.py`, each with a unit test in `tests/test_detect.py`).

A page has changed when the fingerprint of its text, links, media, title and description changes. Only then are its
snapshot files and raw HTML written. The old normaliser, its noise rules and `trafilatura` are no longer used.
Parsing runs in worker processes with a 60-second limit per page: today's 08:00 run hung for six hours inside one of
the old noise-rule regular expressions, which a thread could not stop.

## Acceptance (tests/test_parser_corpus.py, run with the daily run's own venv on the VM, 28 min)

| Set | Pairs | Result |
|---|---|---|
| Parser evaluation corpus: edits | 1,040 | all detected and located |
| Parser evaluation corpus: noise / unchanged copies | 871 / 97 | none flagged |
| Kinds found on real pages (below): Cloudflare email re-encoding, form honeypot labels, dates in links | 291 | none flagged |
| Encoded email address changed (edit) | 97 | all detected and located |
| Second noise set, 16 templates | 1,552 | none flagged |

The labelled pairs are regenerated from the 97 corpus pages in `tests/corpus/pages` by `tests/corpus/make_pairs.py`;
the test also checks the labels reproduce exactly.

**The second noise set is not an independent held-out test.** I wrote it after the first noise rules. Its first run
failed 7 of its 16 templates (donor counts in a sentence, a copyright year after the name, a clock without units,
"Election Day is in N days", a flip clock, "N minutes ago" in a feed, "Yesterday"). I then generalised the rules until
all 16 passed, so it now only guards against regressions.

## Code review (two reviewers, then a re-review of the fixes)

Fixed:
- Inside a countdown or fundraising widget, every number in the block had been masked, so a phone number or date next
  to a countdown could be hidden. Now only the widget's own numbers are masked (a bare number, amount, percentage or
  clock; a number followed by a time unit or a count word; dollar amounts only next to fundraising words). Unit tests
  cover a phone number, a date and a policy dollar figure inside widget blocks.
- Worker-pool errors raised at submission escaped the error handling; a pool replaced by another thread could be used
  after shutdown. Both are now caught and the page is retried once on the new pool. A page that times out still stops
  every worker in the pool, so pages being parsed at the same moment are retried, not lost.
- `meta.json` had lost the "Paid for by" text and years mentioned that the spec's data contract names; restored.
- The three real-world noise kinds and the encoded-email edit were added to the labelled corpus (their own random
  stream, so the evaluation's 2,008 pairs are unchanged).

Not changed, by decision: two rules fitted to real pages (scrambled `mailto:` links, Google Sites image URLs) have unit
tests but no corpus pairs; the scorer still matches removed text on its first 25 characters.

## Day-over-day check on real pages


Every page whose raw HTML was saved on both days (12,988 pages, 1099 sites) was parsed by the
adopted method on both days. No ground truth exists for real pages; this measures how often a page is reported as
changed, and what the reported differences are.

| Version of detect.py | Pages reported changed | Sites with a changed page |
|---|---|---|
| First build (corpus rules only) | 1,493 | 212 |
| With five rules added from this check | 551 | 120 |

4,972 pages were byte-identical on both days. 42 pages were empty HTML documents (now logged as `empty_page`).
Parse time per page on the VM: median 145 ms, 90th percentile 368 ms, max 3864 ms.

## Rules added from the first run (each now has a unit test)
In the first run, 1,493 pages were reported changed. Of those, most were re-encoding on every page load rather than edits:
- Cloudflare email protection re-encodes each email link with a random key (642 pages): links are now decoded to the address.
- Gravity Forms / WPForms anti-spam fields show a random label on every load (208 pages): removed.
- Dates in link queries, e.g. a calendar's `?range=<today>` (142 pages): masked.
- Percent- or entity-scrambled `mailto:` links (44 pages): decoded.
- Google Sites image URLs, which are re-signed per load: normalised.
None of the second run's 551 pages were new; every one was also reported in the first run.

## What the remaining 551 are (25 checked by hand)
Of the 25 checked, 18 are not edits, 5 are real edits and 2 are unclear (form fields re-ordered). The 18 are kinds of noise the corpus did not contain:
- **Calendar views of today** (events/today, day lists): 33 pages. The page shows a different day each day.
- **Rotating lists**: "related posts", "you may also like", related products in campaign shops; the order or selection changes per load.
- **Embedded social feeds and counters**: Instagram/Facebook feed posts, like and comment counts.
- **Shop cart counters**; Google Docs/Sites images with per-load signed URLs (6 pages).

The 5 real edits were: two new menu items ("Jobs", "Anti-Corruption Plan"), a rewritten page description with a new
event link, privacy-policy text changes, and a title removed from a header line.

These remaining noise kinds are not handled by rules in this build. As built, they are recorded as changes and would go to
the change classifier (not built yet), whose routine/cosmetic categories are meant for them. Handling them by rule instead
would mean adding each kind to the corpus as labelled noise first, then re-running both the corpus test and this check.
