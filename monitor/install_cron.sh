#!/bin/bash
# Install (or reinstall) the daily 08:00 UTC run in this user's crontab (issue #1).
# Safe to re-run: any existing daily.sh line is replaced, other cron lines are kept.
# Always schedules the daily-run clone (~/monitor/snapshots), never the dev clone.
set -euo pipefail
SCRIPT="$HOME/monitor/snapshots/monitor/daily.sh"
[ -x "$SCRIPT" ] || { echo "not found or not executable: $SCRIPT" >&2; exit 1; }
[ "$(date +%Z)" = "UTC" ] || echo "WARNING: system clock is $(date +%Z), so 08:00 is not 08:00 UTC" >&2
LINE="0 8 * * * $SCRIPT"
{ crontab -l 2>/dev/null | grep -vF "monitor/daily.sh" || true; echo "$LINE"; } | crontab -
crontab -l | grep -F "monitor/daily.sh"
