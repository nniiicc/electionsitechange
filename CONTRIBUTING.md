# Working on the monitor

## Layout

| Path | What |
|---|---|
| `monitor/` | Code the daily run uses: `snapshot.py`, `daily.sh`, `monitor_urls.csv`, plus `install_cron.sh` to schedule it |
| `tests/` | End-to-end tests of the daily run (see below) |
| `tools/` | One-off scripts: reachability check (`check_urls.py`), attribution fetcher (`fetch_pages.py`), coverage check (`cov.py`) |
| `docs/` | Spec and design documents |
| `data/` | Dated results of one-off checks that changed the site list, such as `attribution_<day>.csv` with its `-summary.json` |
| `sites/`, `logs/` | Snapshot data, written only by the daily run |

## Snapshot layout

Each day's run crawls every site from its homepage: links on the candidate's own site only, up to
3 clicks deep and 50 pages, nearest pages first; robots.txt obeyed; at least 1 s between requests to a
site; a site answering 429/503 is left alone for the rest of the day.

| Path | What |
|---|---|
| `sites/<site_id>/{text.md,main.md,links.json,meta.json}` | The homepage |
| `sites/<site_id>/pages/<slug>/{…same four files…}` | Every other page; `<slug>` is the page path plus a short hash |
| `logs/<day>.csv` | One row per page fetched (or found gone) that day |
| `logs/<day>-summary.json` | That day's totals |

Per page: `text.md` is the full visible text, one sentence per line, including tabs and accordions, with known noise
(countdowns, donation progress, cookie banners, copyright years) removed. **Changes are detected on this file.**
`main.md` is the extracted main content, a reading view only. `links.json` is outbound links with tracking
parameters removed. `meta.json` holds `format` (currently 2), final URL, title, description, "Paid for by" text and years
mentioned. Nothing volatile (fetch time, size) is written to these files; that goes to `logs/`. The switch to format 2
makes one run record a change on nearly every page; tools reading history should treat that commit as a format change.

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

## Schedule

The daily run is a cron job: `0 8 * * * ~/monitor/snapshots/monitor/daily.sh` (the VM clock is UTC).
To install or restore it, for example on a rebuilt VM, run `~/monitor/snapshots/monitor/install_cron.sh`.
It is safe to re-run. Each run's output is appended to `~/monitor/runs.log`.

The plan and its tickets are GitHub issues #1–#16; the spec is `docs/spec_campaign_site_monitor_v2.md`.
