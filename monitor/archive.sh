#!/bin/bash
# Submit the day's changed pages to the Wayback Machine (issue #8). Started in the background by daily.sh after
# the snapshot is pushed; can also be run by hand: archive.sh YYYY-MM-DD
#
# - Submission is done by spn.sh (tools/vendor/), at most 3 jobs at a time: this account's limit.
# - Changed pages first (homepages first), then up to $BACKLOG homepages never archived (the first round).
# - Days run one after another: if yesterday's archiving is still going, today's waits for it. Each day stops
#   submitting at 07:30 UTC the next morning, so a day can never hold up the next one for long.
# - Keys come from ~/.config/archiveorg/spn_keys ("access:secret", mode 600); without them nothing is submitted.
#   spn.sh only accepts them on its command line, so they are visible in this user's process list while it runs
#   (the VM has one user).
# - Results go to ~/monitor/wayback/results/DAY.csv; daily.sh copies them into the repository next morning.
set -uo pipefail
MON="${MONITOR_HOME:-$HOME/monitor}"
REPO="$MON/snapshots"
PY="${MONITOR_PY:-$MON/.venv/bin/python}"
SPN="${SPN_SH:-$REPO/tools/vendor/spn.sh}"
STATE="$MON/wayback"
KEYS="${SPN_KEYS:-$HOME/.config/archiveorg/spn_keys}"
DAY="${1:-$(date -u +%F)}"
BACKLOG="${ARCHIVE_BACKLOG:-2000}"
mkdir -p "$STATE/runs"
exec 8>"$STATE/.archive.lock"
flock 8                                   # wait for an earlier day's archiving to finish
echo "=== $(date -u +%FT%TZ) archive $DAY start"
[ -s "$KEYS" ] || { echo "no Save Page Now keys at $KEYS; nothing submitted"; exit 0; }
[ "$(stat -c %a "$KEYS" 2>/dev/null || stat -f %Lp "$KEYS")" = 600 ] || chmod 600 "$KEYS"
"$PY" "$REPO/monitor/archive.py" queue "$REPO" "$DAY" "$STATE" --backlog "$BACKLOG" || exit 1
# stop submitting at 07:30 UTC the next day, before the next run's changes are queued; what is left is the
# lowest-priority end of the list (the queue is in priority order)
STOP=$(( $(date -u -d "$DAY" +%s) + 86400 + 7*3600 + 1800 ))
for kind in changed backlog; do
    list="$STATE/queue/$DAY-$kind.txt"
    [ -s "$list" ] || continue
    left=$(( STOP - $(date +%s) ))
    [ "$left" -gt 60 ] || { echo "$kind: out of time for $DAY; skipped"; continue; }
    # changed pages: capture today's version even if archived before (only skip a capture made in the last 3 hours);
    # first-round homepages: skip any already archived in the last 30 days
    opts=$([ "$kind" = changed ] && echo "if_not_archived_within=3h" || echo "if_not_archived_within=30d")
    # a re-run of the same day keeps the earlier run's logs (record reads all of them)
    if [ -d "$STATE/runs/$DAY-$kind" ]; then
        n=1; while [ -e "$STATE/runs/$DAY-$kind.$n" ]; do n=$((n+1)); done
        mv "$STATE/runs/$DAY-$kind" "$STATE/runs/$DAY-$kind.$n"
    fi
    timeout "$left" "$SPN" -a "$(cat "$KEYS")" -f "$STATE/runs/$DAY-$kind" -p 3 -n -q -t 1800 -d "$opts" "$list" \
        > "$STATE/runs/$DAY-$kind.out" 2>&1
    echo "$kind: spn.sh exit $? ($(wc -l < "$list") submitted)"
done
"$PY" "$REPO/monitor/archive.py" record "$STATE" "$DAY"
echo "=== $(date -u +%FT%TZ) archive $DAY end"
