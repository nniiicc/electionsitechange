#!/bin/bash
# Daily snapshot of campaign websites, run by cron at 08:00 UTC (issue #1).
#
# - Only one run at a time: if yesterday's run is still going, today's is skipped.
# - A run that dies before committing leaves half-written files; they are discarded,
#   so a crash can never mix partial data into the next day's commit.
# - The snapshot commits locally first; if the push to GitHub fails, the next
#   successful push carries every unpushed day.
set -uo pipefail
REPO="$HOME/monitor/snapshots"
LOG="$HOME/monitor/runs.log"
PY="$HOME/monitor/.venv/bin/python"
exec 9>"$HOME/monitor/.daily.lock"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous run still active; skipped" >>"$LOG"; exit 0
fi
discard_partial() { git -C "$REPO" reset -q --hard HEAD && git -C "$REPO" clean -qfd; }
{
    echo "=== $(date -u +%FT%TZ) start"
    discard_partial
    if "$PY" "$REPO/monitor/snapshot.py" "$REPO/monitor/monitor_urls.csv" "$REPO" \
            --workers 8 --raw-dir "$HOME/monitor/raw" --summary "$HOME/monitor/last_summary.json"; then
        # Take any commits made on GitHub first (e.g. a README edited in the browser);
        # otherwise every later push would be rejected.
        if git -C "$REPO" pull -q --rebase origin main && git -C "$REPO" push -q origin main; then
            echo "pushed $(git -C "$REPO" rev-parse --short HEAD)"
        else
            git -C "$REPO" rebase --abort 2>/dev/null || true
            echo "PUSH FAILED - will be retried by the next run"
        fi
    else
        echo "SNAPSHOT FAILED (exit $?) - partial files discarded"
        discard_partial
    fi
    echo "=== $(date -u +%FT%TZ) end"
} >>"$LOG" 2>&1
