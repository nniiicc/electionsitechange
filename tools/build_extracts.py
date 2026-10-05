"""Build one attribution-check row per monitored site from a committed snapshot (read-only: git archive)."""
import csv, io, json, subprocess, sys, tarfile
repo, rev, out = sys.argv[1], sys.argv[2], sys.argv[3]
tar = tarfile.open(fileobj=io.BytesIO(subprocess.run(["git", "-C", repo, "archive", rev, "sites", "monitor/monitor_urls.csv"],
                                                    check=True, capture_output=True).stdout))
files = {}
for m in tar.getmembers():
    p = m.name.split("/")
    if m.isfile() and (m.name == "monitor/monitor_urls.csv" or (len(p) == 3 and p[2] in ("meta.json", "text.md"))):
        files[m.name] = tar.extractfile(m).read().decode("utf-8", "replace")
urls = list(csv.DictReader(io.StringIO(files["monitor/monitor_urls.csv"])))
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(list(urls[0].keys()) + ["snap_final_url", "snap_title", "snap_description", "snap_paid_for_by", "snap_years", "snap_text"])
    n = 0
    for r in urls:
        meta = files.get(f"sites/{r['site_id']}/meta.json"); text = files.get(f"sites/{r['site_id']}/text.md", "")
        m = json.loads(meta) if meta else {}
        n += bool(meta)
        w.writerow(list(r.values()) + [m.get("final_url", ""), m.get("title", ""), m.get("description", ""),
                   m.get("paid_for_by") or "", ";".join(m.get("years_mentioned", [])), " ".join(text.split())[:1500]])
print(f"{len(urls)} sites, {n} with a snapshot at {rev}; columns: {list(urls[0].keys())}")
