# Working on the monitor

## Layout

| Path | What |
|---|---|
| `monitor/` | Code the daily run uses: `snapshot.py` (crawl and write), `detect.py` (parse a page and decide whether it changed), `changes.py` (change records), `step0.py` (noise rules for change records), `pdf.py` (text of PDFs on the candidate's site; needs poppler-utils), `site_noise.csv` (per-site noise patterns), `daily.sh`, `monitor_urls.csv`, plus `install_cron.sh` to schedule it |
| `tests/` | Tests of the daily run and the page parser (see below); `tests/corpus/` holds the labelled parser corpus |
| `tools/` | One-off scripts: reachability check (`check_urls.py`), attribution fetcher (`fetch_pages.py`), coverage check (`cov.py`), the parser evaluation (`parser_eval/`), day-over-day parser check on saved raw HTML (`real_pairs_check.py`), calibration sample (`sample_changes.py`) and labelling tool (`label_changes.html`) |
| `docs/` | Spec and design documents |
| `data/` | Dated results of one-off checks that changed the site list, such as `attribution_<day>.csv` with its `-summary.json` |
| `sites/`, `logs/`, `changes/` | Snapshot data and change records, written only by the daily run |

## Snapshot layout

Each day's run crawls every site from its homepage: links on the candidate's own site only, up to
3 clicks deep and 50 pages, nearest pages first; robots.txt obeyed; at least 1 s between requests to a
site; a site answering 429/503 is left alone for the rest of the day.

| Path | What |
|---|---|
| `sites/<site_id>/{text.md,links.json,media.json,meta.json}` | The homepage |
| `sites/<site_id>/pages/<slug>/{…same four files…}` | Every other page; `<slug>` is the page path plus a short hash |
| `logs/<day>.csv` | One row per page fetched (or found gone) that day |
| `logs/<day>-summary.json` | That day's totals |
| `changes/<day>.jsonl` | One change record per page added, removed or changed that day, plus one per site for edits repeated on 3+ pages (`page` = `*`); `step0` says whether the noise rules discarded it and why |

Pages are parsed by `monitor/detect.py`, the method chosen by the parser evaluation
(`docs/parser_evaluation_2026-10-06.md`): EDGI web-monitoring-diff's visible text and links, an image-and-embed
list, and noise rules applied first.

- `text.md`: the page's visible text as EDGI extracts it, including tabs and accordions, one sentence per line.
- `links.json`: outbound links as `{text, href}`, absolute, with tracking parameters removed and re-encoded email links decoded.
- `media.json`: images (normalised so another size of the same image is equal), alt texts and video/iframe embeds.
- `meta.json`: `format` (currently 3), final URL, title, description, "Paid for by" text, years mentioned, and
  `fingerprint`, a hash of the text, links, media, title and description.
  **A page has changed when its fingerprint changes**; only then are its files rewritten.

Noise rules (all in `detect.py`, each with a test in `tests/test_detect.py`): cookie-consent banners and form
anti-spam honeypot fields are removed; inside a countdown or fundraising widget, the widget's own numbers (a bare
number or clock, a number followed by a time unit or a count word such as "donors", fundraising amounts) become `#`,
while other numbers in the same block are kept; "N days ago" dates and copyright years become `#`; tracking parameters and dates in link queries are dropped. Nothing
else is removed. Nothing volatile (fetch time, size) is written to these files; that goes to `logs/`. The first run of
each new format rewrites every page once; that run's summary counts them as `pages_reformatted`, not as changes.

A file changes only when the page's content does, so `git log`/`git diff` on these paths are the change
history. A page that has disappeared shows up as deleted files; compare with `--no-renames`, or Git may
pair a deleted page with a new one that has an identical file and report a rename.

## Where code changes happen

- Code is developed in a separate clone on the VM, `~/monitor/dev`, never in the daily run's clone (`~/monitor/snapshots`). The daily run discards uncommitted files in its own clone before it starts.
- Every change is committed and pushed to `main` as soon as it works, with the issue it belongs to in the message (`refs #4`, or `closes #4` for the final commit).
- The daily run pulls `main` before it starts, so pushed code is used from the next 08:00 UTC run.
- Don't edit `sites/` or `logs/` by hand.
- Run the tests before every push (a few seconds; they never contact a real website, the real
  `~/monitor` folder or the real GitHub repository):
  `~/monitor/.venv/bin/python -m unittest discover -s tests -v`
  - `tests/test_daily_run.py` runs the real `monitor/snapshot.py` over two simulated days against local fake sites.
  - `tests/test_daily_sh.py` runs the real `monitor/daily.sh` in a throwaway folder whose "GitHub" is a local
    bare repository: commit and push, a commit made on GitHub, discarding half-written files, and the lock.
  - `tests/test_detect.py` checks each noise rule, and that the matching campaign content is still detected.
- **Any change to `monitor/detect.py` must also pass the parser acceptance test** (about 25 minutes on the VM, so it is skipped by default):
  `RUN_CORPUS_TEST=1 ~/monitor/.venv/bin/python -m unittest discover -s tests -p test_parser_corpus.py -v`
  It runs the 2,008 labelled pairs from the parser evaluation plus 388 pairs of kinds found on real sites (every
  edit found, no noise flagged), and a second noise set of 1,552 pairs. After changing the pair generator, regenerate the labels with `python tests/corpus/make_pairs.py`.

## Schedule

The daily run is a cron job: `0 8 * * * ~/monitor/snapshots/monitor/daily.sh` (the VM clock is UTC).
To install or restore it, for example on a rebuilt VM, run `~/monitor/snapshots/monitor/install_cron.sh`.
It is safe to re-run. Each run's output is appended to `~/monitor/runs.log`.

The plan and its tickets are GitHub issues #1–#16; the spec is `docs/spec_campaign_site_monitor_v2.md`.
