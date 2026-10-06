"""Day-over-day check of monitor/detect.py on real pages (issue #5). Read-only.

For every page whose raw HTML was saved on both DAY_A and DAY_B, run detect.page on both days and
record whether the fingerprint changed and what the snapshot difference is. Writes real_pairs.jsonl
and prints a summary with timing. Usage: python real_pairs_check.py RAW_DIR DAY_A DAY_B
"""
import glob, gzip, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monitor"))
import detect  # noqa: E402

RAW, A, B = sys.argv[1:4]


def one(rel):
    out = {"page": rel}
    try:
        ha = gzip.open(os.path.join(RAW, A, rel), "rt", encoding="utf-8", errors="replace").read()
        hb = gzip.open(os.path.join(RAW, B, rel), "rt", encoding="utf-8", errors="replace").read()
        t0 = time.time()
        pa, pb = detect.page(ha, "https://example.test/"), detect.page(hb, "https://example.test/")
        out["s_per_page"] = (time.time() - t0) / 2
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:200]; return out
    out["bytes_identical"] = ha == hb
    out["changed"] = pa["meta"]["fingerprint"] != pb["meta"]["fingerprint"]
    if out["changed"]:
        la, lb = pa["lines"], pb["lines"]
        sa, sb = set(la), set(lb)
        out["lines_removed"] = [x for x in la if x not in sb][:6]
        out["lines_added"] = [x for x in lb if x not in sa][:6]
        ka = {(l["text"], l["href"]) for l in pa["links"]}; kb = {(l["text"], l["href"]) for l in pb["links"]}
        out["links_removed"] = sorted(ka - kb)[:6]; out["links_added"] = sorted(kb - ka)[:6]
        out["media_removed"] = sorted(set(pa["media"]) - set(pb["media"]))[:6]
        out["media_added"] = sorted(set(pb["media"]) - set(pa["media"]))[:6]
        out["meta_changed"] = {k: [pa["meta"][k], pb["meta"][k]] for k in ("title", "description") if pa["meta"][k] != pb["meta"][k]}
    return out


if __name__ == "__main__":
    rels = sorted(os.path.relpath(p, os.path.join(RAW, B)) for p in glob.glob(os.path.join(RAW, B, "*", "*.html.gz")))
    rels = [r for r in rels if os.path.exists(os.path.join(RAW, A, r))]
    t0 = time.time()
    res = []
    with ProcessPoolExecutor(2) as ex, open("real_pairs.jsonl", "w") as f:
        for r in ex.map(one, rels, chunksize=16):          # written as it goes, so a stopped run keeps its results
            res.append(r); f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
    ok = [r for r in res if "error" not in r]
    ts = sorted(r["s_per_page"] for r in ok)
    print(json.dumps({"pairs": len(rels), "errors": len(res) - len(ok), "changed": sum(r["changed"] for r in ok),
                      "bytes_identical": sum(r["bytes_identical"] for r in ok),
                      "median_ms": round(1000 * ts[len(ts) // 2]), "p90_ms": round(1000 * ts[9 * len(ts) // 10]),
                      "max_ms": round(1000 * ts[-1]), "wall_s": round(time.time() - t0)}))
