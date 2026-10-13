"""Wayback Machine archiving around spn.sh (issue #8).

Submission itself is done by spn.sh (overcast07/wayback-machine-spn-scripts, MIT, vendored in tools/vendor/), which
handles Save Page Now authentication, parallel jobs, retries and the account's limits. This module only decides WHAT
to submit and records WHAT came back. archive.sh runs it alongside the daily crawl:

  The crawler (snapshot.py --archive-queue) appends "<priority>\t<url>" to STATE/live/DAY.tsv for every new or
  changed page that step 0 keeps, as soon as it is found. daily.sh touches STATE/live/DAY.done when the crawl ends.

  homepages  REPO STATE              write STATE/homepages.txt (the site list's homepages)
  next-batch STATE DAY N             the N highest-priority queued pages not yet submitted today, in priority order,
                                     into STATE/queue/DAY-batch.txt; they are added to STATE/queue/DAY-changed.txt
                                     (everything submitted today). Prints how many.
  backlog    STATE DAY N             up to N homepages never archived and not submitted today -> DAY-backlog.txt
  queue      REPO DAY STATE          for a day archived by hand after its run: build live/DAY.tsv from the day's
                                     change records (same priorities) and mark it done
  record     STATE DAY               read spn.sh's logs for DAY into STATE/results/DAY.csv (url, queue, capture,
                                     status) and add archived homepages to the done list
  apply      REPO STATE              copy results into REPO/wayback/ and fill each change record's wayback links:
                                     after = the capture made by that day's archiving, before = the latest capture
                                     of the page made on an earlier day

Priorities: 0 homepage (a site-wide change submits the homepage), 1 new page, 2 text/links/metadata changed,
3 only images changed. STATE (~/monitor/wayback) is outside the snapshot repository: daily.sh discards uncommitted
files in the repository at the start of each run, so results are copied in by `apply` just before the snapshot.
"""
import argparse, csv, glob, json, os, re, sys

WAYBACK = "https://web.archive.org"
CAPTURE = re.compile(r"^/web/(\d{14})/(.+)$")


def _norm(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip()).rstrip("/").lower()


def _read(path):
    with open(path) as f:
        return f.read()


def _write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(l + "\n" for l in lines)
    os.replace(tmp, path)


def homepages(repo):
    with open(os.path.join(repo, "monitor", "monitor_urls.csv"), newline="") as f:
        return [(r["site_id"], r["url"]) for r in csv.DictReader(f)
                if r.get("reachability", "reachable") == "reachable" and r.get("url")]


def done_homepages(state):
    p = os.path.join(state, "homepages_done.txt")
    return set(_read(p).split()) if os.path.exists(p) else set()


def _live(state, day):
    return os.path.join(state, "live", f"{day}.tsv")


def priority(r, home):
    """(priority, url) for a change record, or None if it is not submitted"""
    if (r.get("step0") or {}).get("discard") or r["kind"] == "removed":
        return None
    if r["kind"] == "sitewide":
        return 0, home.get(r["site_id"]) or r.get("url")
    if r["page"] == "/":
        return 0, r.get("url")
    if r["kind"] == "added":
        return 1, r.get("url")
    content = any((r.get(k) or {}).get("removed") or (r.get(k) or {}).get("added") for k in ("text", "links")) or r.get("meta")
    return (2 if content else 3), r.get("url")


def queue(repo, day, state):
    p = os.path.join(repo, "changes", f"{day}.jsonl")
    recs = [json.loads(l) for l in _read(p).splitlines() if l.strip()] if os.path.exists(p) else []
    home = {sid: url for sid, url in homepages(repo)}
    lines = [f"{pu[0]}\t{pu[1]}" for pu in (priority(r, home) for r in recs) if pu and pu[1]]
    _write(_live(state, day), lines)
    _write(_live(state, day)[:-4] + ".done", [])
    return {"queued": len(lines)}


def _submitted(state, day):
    p = os.path.join(state, "queue", f"{day}-changed.txt")
    return _read(p).split() if os.path.exists(p) else []


def next_batch(state, day, n):
    best = {}                                             # page -> (priority, arrival order, url)
    p = _live(state, day)
    text = _read(p) if os.path.exists(p) else ""
    if text and not text.endswith("\n"):
        text = text[:text.rfind("\n") + 1]               # the last line is still being written: next time
    for k, line in enumerate(text.splitlines()):
        prio, _, url = line.partition("\t")
        if not url.strip() or not prio.isdigit():
            continue                                      # a line still being written, or damaged
        key = _norm(url)
        if key not in best or int(prio) < best[key][0]:
            best[key] = (int(prio), best.get(key, (0, k))[1], url.strip())
    done = {_norm(u) for u in _submitted(state, day)}
    batch = [u for _, _, u in sorted(v for key, v in best.items() if key not in done)][:n]
    _write(os.path.join(state, "queue", f"{day}-batch.txt"), batch)
    if batch:
        os.makedirs(os.path.join(state, "queue"), exist_ok=True)
        with open(os.path.join(state, "queue", f"{day}-changed.txt"), "a") as f:
            f.writelines(u + "\n" for u in batch)
    return len(batch)


def backlog(state, day, n):
    done = done_homepages(state) | {_norm(u) for u in _submitted(state, day)}
    homes = [u for _, u in homepages_from_state(state)]
    out = [u for u in homes if _norm(u) not in done][:n]
    _write(os.path.join(state, "queue", f"{day}-backlog.txt"), out)
    return {"backlog": len(out), "homepages_never_archived": sum(1 for u in homes if _norm(u) not in done_homepages(state))}


def record(state, day):
    rows = {}
    for kind in ("changed", "backlog"):
        submitted = _read(os.path.join(state, "queue", f"{day}-{kind}.txt")).split() \
            if os.path.exists(os.path.join(state, "queue", f"{day}-{kind}.txt")) else []
        for u in submitted:
            rows.setdefault(_norm(u), {"url": u, "queue": kind, "capture": "", "status": "not_captured"})
        # every run folder of the day: an interrupted day that was re-run keeps its earlier folder (DAY-kind.N)
        for d in sorted(glob.glob(os.path.join(state, "runs", f"{day}-{kind}")) + glob.glob(os.path.join(state, "runs", f"{day}-{kind}.*"))):
            if not os.path.isdir(d):
                continue
            # captures.log: one line per capture, "/web/<timestamp>/<url>", written in a single append by spn.sh,
            # so lines from parallel jobs never mix. A capture whose URL differs from what was submitted
            # (Save Page Now normalised or followed it) is kept as its own row.
            caps = _read(os.path.join(d, "captures.log")).split("\n") if os.path.exists(os.path.join(d, "captures.log")) else []
            for c in caps:
                m = CAPTURE.match(c.strip())
                if m:
                    rows.setdefault(_norm(m.group(2)), {"url": m.group(2), "queue": kind})
                    rows[_norm(m.group(2))].update(capture=f"{WAYBACK}/web/{m.group(1)}/{m.group(2)}", status="captured")
            # failures spn.sh gave up on: failed.log "<date> <time> [<reason>] <url>"; invalid.log "<date> <time> <url>"
            # followed by the server's message on the next line(s)
            fails = []
            if os.path.exists(os.path.join(d, "failed.log")):
                fails += [(m.group(2), m.group(1)) for m in
                          (re.match(r"^\S+ \S+ \[([^\]]+)\] (\S+)", l) for l in _read(os.path.join(d, "failed.log")).splitlines()) if m]
            if os.path.exists(os.path.join(d, "invalid.log")):
                lines = _read(os.path.join(d, "invalid.log")).splitlines()
                for k, l in enumerate(lines):
                    m = re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d (\S+)$", l)
                    if m:
                        msg = lines[k + 1].strip() if k + 1 < len(lines) else ""
                        fails.append((m.group(1), "invalid: " + re.sub(r"\s+", " ", msg)[:120]))
            for u, why in fails:
                if rows.get(_norm(u), {}).get("status") != "captured":
                    rows.setdefault(_norm(u), {"url": u, "queue": kind, "capture": ""})
                    rows[_norm(u)]["status"] = "failed: " + why
    out = os.path.join(state, "results", f"{day}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url", "queue", "capture", "status"]); w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["queue"], r["url"])))
    os.replace(out + ".tmp", out)
    homes = {_norm(u) for _, u in homepages_from_state(state)}
    # a homepage leaves the first-round backlog once captured, or once Save Page Now gave up on it for good
    # (e.g. the site refuses the archive's crawler); otherwise it would be resubmitted every day
    new_done = done_homepages(state) | {k for k, r in rows.items() if k in homes and r["status"] != "not_captured"}
    _write(os.path.join(state, "homepages_done.txt"), sorted(new_done))
    st = {}
    for r in rows.values():
        st[r["status"].split(":")[0]] = st.get(r["status"].split(":")[0], 0) + 1
    return {"day": day, **st}


def homepages_from_state(state):
    p = os.path.join(state, "homepages.txt")              # written by `queue` so `record` needs no repo
    return [(None, u) for u in _read(p).split()] if os.path.exists(p) else []


def apply(repo, state):
    results = sorted(glob.glob(os.path.join(state, "results", "*.csv")))
    history, by_day = {}, {}                              # page -> [(timestamp, capture)]; day -> {page: capture}
    for p in results:
        day = os.path.basename(p)[:-4]
        for r in csv.DictReader(_read(p).splitlines()):
            m = CAPTURE.match(r["capture"][len(WAYBACK):]) if r.get("capture", "").startswith(WAYBACK) else None
            if m:
                history.setdefault(_norm(r["url"]), []).append((m.group(1), r["capture"]))
                by_day.setdefault(day, {})[_norm(r["url"])] = r["capture"]
    os.makedirs(os.path.join(repo, "wayback"), exist_ok=True)
    filled = 0
    for p in results:
        day = os.path.basename(p)[:-4]
        dst = os.path.join(repo, "wayback", os.path.basename(p))
        if not os.path.exists(dst) or _read(dst) != _read(p):
            with open(dst, "w") as f:
                f.write(_read(p))
        cp = os.path.join(repo, "changes", f"{day}.jsonl")
        if not os.path.exists(cp):
            continue
        stamp = day.replace("-", "")
        recs, changed = [], False
        for line in _read(cp).splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            # after: the capture made by THAT day's archiving (submitted after the snapshot, before the next run);
            # before: the latest capture we made on an earlier day
            caps = sorted(history.get(_norm(r.get("url")), []))
            after = by_day.get(day, {}).get(_norm(r.get("url")))
            before = next((c for t, c in reversed(caps) if t[:8] < stamp), None)
            new = {"before": before, "after": after}
            if r.get("wayback") != new:
                r["wayback"] = new; changed = True; filled += 1
            recs.append(r)
        if changed:
            with open(cp + ".tmp", "w") as f:
                for r in recs:
                    f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(cp + ".tmp", cp)
    return {"result_days": len(results), "records_updated": filled}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("homepages"); h.add_argument("repo"); h.add_argument("state")
    nb = sub.add_parser("next-batch"); nb.add_argument("state"); nb.add_argument("day"); nb.add_argument("n", type=int)
    b = sub.add_parser("backlog"); b.add_argument("state"); b.add_argument("day"); b.add_argument("n", type=int)
    q = sub.add_parser("queue"); q.add_argument("repo"); q.add_argument("day"); q.add_argument("state")
    r = sub.add_parser("record"); r.add_argument("state"); r.add_argument("day")
    a = sub.add_parser("apply"); a.add_argument("repo"); a.add_argument("state")
    x = ap.parse_args()
    if x.cmd == "homepages":
        _write(os.path.join(x.state, "homepages.txt"), [u for _, u in homepages(x.repo)]); return
    if x.cmd == "next-batch":
        print(next_batch(x.state, x.day, x.n)); return
    out = {"backlog": lambda: backlog(x.state, x.day, x.n), "queue": lambda: queue(x.repo, x.day, x.state),
           "record": lambda: record(x.state, x.day), "apply": lambda: apply(x.repo, x.state)}[x.cmd]()
    print(json.dumps(out))


if __name__ == "__main__":
    sys.exit(main())
