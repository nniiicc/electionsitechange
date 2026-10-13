#!/bin/bash
# Submit the day's new and changed pages to the Wayback Machine (issue #8) WHILE the crawl runs.
# Started in the background by daily.sh just before the crawl; can also be run by hand for an earlier day:
#   archive.sh YYYY-MM-DD   (its queue is then built from that day's change records)
#
# - The crawler appends each new or changed page that step 0 keeps to ~/monitor/wayback/live/DAY.tsv as soon as
#   it finds it. This script repeatedly takes the BATCH highest-priority pages not yet submitted (homepages first,
#   then new pages, then text/link/metadata changes, then image-only changes) and submits them with spn.sh
#   (tools/vendor/), at most 3 jobs at a time: this account's limit. While the queue is empty and the crawl is
#   still running it waits POLL seconds. When the crawl has ended (live/DAY.done) and the queue is used up, the
#   remaining time goes to homepages never archived (the first round).
# - Submission stops at 07:30 UTC the next day, before the next run starts; whatever is left is the
#   lowest-priority end of the queue. Pages left unsent are not carried over.
# - Days run one after another: if yesterday's archiving is still going, today's waits for it.
# - Keys come from ~/.config/archiveorg/spn_keys ("access:secret", mode 600); without them nothing is submitted.
#   spn.sh only accepts them on its command line, so they are visible in this user's process list while it runs
#   (the VM has one user). Never list processes with their arguments while this runs.
# - Results go to ~/monitor/wayback/results/DAY.csv; daily.sh copies them into the repository next morning.
set -uo pipefail
MON="${MONITOR_HOME:-$HOME/monitor}"
REPO="$MON/snapshots"
PY="${MONITOR_PY:-$MON/.venv/bin/python}"
A="$REPO/monitor/archive.py"
SPN="${SPN_SH:-$REPO/tools/vendor/spn.sh}"
STATE="$MON/wayback"
KEYS="${SPN_KEYS:-$HOME/.config/archiveorg/spn_keys}"
DAY="${1:-$(date -u +%F)}"
BACKLOG="${ARCHIVE_BACKLOG:-2000}"
BATCH="${ARCHIVE_BATCH:-90}"          # 30-40 minutes of captures; the queue is re-sorted between batches
POLL="${ARCHIVE_POLL_S:-120}"
LIVE="$STATE/live/$DAY.tsv"; DONE="$STATE/live/$DAY.done"
mkdir -p "$STATE/runs" "$STATE/live" "$STATE/queue"
exec 8>"$STATE/.archive.lock"
flock 8                                   # wait for an earlier day's archiving to finish
echo "=== $(date -u +%FT%TZ) archive $DAY start"
[ -s "$KEYS" ] || { echo "no Save Page Now keys at $KEYS; nothing submitted"; exit 0; }
[ "$(stat -c %a "$KEYS" 2>/dev/null || stat -f %Lp "$KEYS")" = 600 ] || chmod 600 "$KEYS"
"$PY" "$A" homepages "$REPO" "$STATE" || exit 1
# a day archived by hand after its run: no live queue, so build it from the day's change records
if [ ! -e "$LIVE" ] && [ -f "$REPO/changes/$DAY.jsonl" ]; then "$PY" "$A" queue "$REPO" "$DAY" "$STATE"; fi
STOP=$(( $(date -u -d "$DAY" +%s) + 86400 + 7*3600 + 1800 ))
newdir() { local n=1; while [ -e "$STATE/runs/$DAY-$1.$(printf %03d $n)" ]; do n=$((n+1)); done; echo "$STATE/runs/$DAY-$1.$(printf %03d $n)"; }
spn() {   # kind list seconds-left opts
    local d; d=$(newdir "$1")
    timeout "$3" "$SPN" -a "$(cat "$KEYS")" -f "$d" -p 3 -n -q -t 1800 -d "$4" "$2" > "$d.out" 2>&1
    echo "$(date -u +%FT%TZ) $1: spn.sh exit $? ($(wc -l < "$2") submitted) $(basename "$d")"
}
batches=0
while :; do
    left=$(( STOP - $(date +%s) )); [ "$left" -gt 60 ] || { echo "out of time for $DAY"; break; }
    ended=0; [ -e "$DONE" ] && ended=1     # checked BEFORE reading the queue, so nothing appended earlier is missed
    got=$("$PY" "$A" next-batch "$STATE" "$DAY" "$BATCH") || { echo "next-batch failed"; break; }
    if [ "$got" -gt 0 ]; then
        # changed pages: capture today's version even if archived before (skip only a capture made in the last 3 hours)
        spn changed "$STATE/queue/$DAY-batch.txt" "$left" "if_not_archived_within=3h"; batches=$((batches+1)); continue
    fi
    [ "$ended" = 1 ] && break
    sleep "$POLL"
done
echo "changed pages: $batches batches, $(wc -l < "$STATE/queue/$DAY-changed.txt" 2>/dev/null || echo 0) submitted"
left=$(( STOP - $(date +%s) ))
if [ -e "$DONE" ] && [ "$left" -gt 60 ]; then
    "$PY" "$A" backlog "$STATE" "$DAY" "$BACKLOG"
    # first-round homepages: skip any already archived in the last 30 days
    [ -s "$STATE/queue/$DAY-backlog.txt" ] && spn backlog "$STATE/queue/$DAY-backlog.txt" "$left" "if_not_archived_within=30d"
fi
"$PY" "$A" record "$STATE" "$DAY"
echo "=== $(date -u +%FT%TZ) archive $DAY end"
