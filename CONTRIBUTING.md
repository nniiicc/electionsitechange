# Working on the monitor

## Layout

| Path | What |
|---|---|
| `monitor/` | Code the daily run uses: `snapshot.py`, `daily.sh`, `monitor_urls.csv` |
| `tools/` | One-off scripts: reachability check (`check_urls.py`), attribution fetcher (`fetch_pages.py`), coverage check (`cov.py`) |
| `docs/` | Spec and design documents |
| `sites/`, `logs/` | Snapshot data, written only by the daily run |

## Where code changes happen

- Code is developed in a separate clone on the VM, `~/monitor/dev`, never in the daily run's clone (`~/monitor/snapshots`). The daily run discards uncommitted files in its own clone before it starts.
- Every change is committed and pushed to `main` as soon as it works, with the issue it belongs to in the message (`refs #4`, or `closes #4` for the final commit).
- The daily run pulls `main` before it starts, so pushed code is used from the next 08:00 UTC run.
- Don't edit `sites/` or `logs/` by hand.
- Run the tests before every push (about 3 seconds; they never contact a real website):
  `~/monitor/.venv/bin/python tests/test_daily_run.py`
  They run the real `monitor/snapshot.py` over two simulated days against local fake sites.
  `daily.sh` (lock, discard partial files, push) is not covered by them.

The plan and its tickets are GitHub issues #1–#16; the spec is `docs/spec_campaign_site_monitor_v2.md`.
