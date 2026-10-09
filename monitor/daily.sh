#!/bin/bash
# Daily snapshot of campaign websites, run by cron at 08:00 UTC (issue #1).
#
# - Only one run at a time: if yesterday's run is still going, today's is skipped.
# - A run that dies before committing leaves half-written files; they are discarded,
#   so a crash can never mix partial data into the next day's commit.
# - The snapshot commits locally first; if the push to GitHub fails, the next
#   successful push carries every unpushed day.
set -uo pipefail
# MONITOR_HOME and MONITOR_PY are only set by the tests (tests/test_daily_sh.py);
# cron uses the defaults.
MON="${MONITOR_HOME:-$HOME/monitor}"
REPO="$MON/snapshots"
LOG="$MON/runs.log"
PY="${MONITOR_PY:-$MON/.venv/bin/python}"
exec 9>"$MON/.daily.lock"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous run still active; skipped" >>"$LOG"; exit 0
fi
discard_partial() { git -C "$REPO" reset -q --hard HEAD && git -C "$REPO" clean -qfd; }
{
    echo "=== $(date -u +%FT%TZ) start"
    discard_partial
    # Code is developed in a separate clone (~/monitor/dev) and pushed to GitHub;
    # pull it so each run uses the latest committed code.
    git -C "$REPO" pull -q --rebase origin main || echo "pull failed; running with local code"
    DAY=$(date -u +%F)
    # Wayback results from earlier days' archiving (issue #8) go into this commit, and fill in the
    # wayback links of those days' change records
    [ -f "$REPO/monitor/archive.py" ] && "$PY" "$REPO/monitor/archive.py" apply "$REPO" "$MON/wayback" \
        || echo "wayback apply skipped or failed"
    if "$PY" "$REPO/monitor/snapshot.py" "$REPO/monitor/monitor_urls.csv" "$REPO" \
            --workers 24 --raw-dir "$MON/raw" --summary "$MON/last_summary.json"; then
        # Take any commits made on GitHub first (e.g. a README edited in the browser);
        # otherwise every later push would be rejected.
        if git -C "$REPO" pull -q --rebase origin main && git -C "$REPO" push -q origin main; then
            echo "pushed $(git -C "$REPO" rev-parse --short HEAD)"
        else
            git -C "$REPO" rebase --abort 2>/dev/null || true
            echo "PUSH FAILED - will be retried by the next run"
        fi
        # archive today's changed pages (issue #8); detached, so this run's lock is released now
        if [ -x "$REPO/monitor/archive.sh" ] && [ -z "${MONITOR_NO_ARCHIVE:-}" ]; then
            # 9>&- : the archiver must not inherit this run's lock, or tomorrow's run would be skipped
            setsid nohup "$REPO/monitor/archive.sh" "$DAY" >>"$MON/archive.log" 2>&1 < /dev/null 9>&- &
            echo "archiving started for $DAY"
        fi
    else
        echo "SNAPSHOT FAILED (exit $?) - partial files discarded"
        discard_partial
    fi
    echo "=== $(date -u +%FT%TZ) end"
} >>"$LOG" 2>&1
