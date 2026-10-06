"""Parser evaluation, step 3b: the current monitor/snapshot.py parser (baseline). Run with ~/monitor/.venv.
A change is reported when the stored text.md, links.json or meta.json would differ (main.md is a reading
view and is not compared, as in the monitor). Writes results_baseline.jsonl.
"""
import importlib.util, json, os, sys
from concurrent.futures import ProcessPoolExecutor

spec = importlib.util.spec_from_file_location("snapshot", os.path.expanduser("~/monitor/dev/monitor/snapshot.py"))
snapshot = importlib.util.module_from_spec(spec); spec.loader.exec_module(snapshot)
URL = "https://example-campaign.test/"


def run(pair_id):
    a = open(f"pairs/{pair_id}/a.html").read(); b = open(f"pairs/{pair_id}/b.html").read()
    try:
        pa, pb = snapshot.normalise(a, URL), snapshot.normalise(b, URL)
        import difflib
        d = list(difflib.ndiff(pa.text.splitlines(), pb.text.splitlines()))   # sequence order, as git diff would show
        ma = {f"{k}={v}" for k, v in pa.meta.items()}; mb = {f"{k}={v}" for k, v in pb.meta.items()}
        det = pa.text != pb.text or pa.links != pb.links or pa.meta != pb.meta
        ins = [x[2:] for x in d if x[:2] == "+ "] + sorted(set(pb.links) - set(pa.links)) + sorted(mb - ma)
        dele = [x[2:] for x in d if x[:2] == "- "] + sorted(set(pa.links) - set(pb.links)) + sorted(ma - mb)
        return {"pair_id": pair_id, "baseline": {"detected": det, "ins": "\n".join(ins)[:20000], "del": "\n".join(dele)[:20000]}}
    except Exception as e:
        return {"pair_id": pair_id, "baseline": {"error": f"{type(e).__name__}: {e}"[:300]}}


if __name__ == "__main__":
    types = set(sys.argv[1].split(",")) if len(sys.argv) > 2 else None
    outfile = sys.argv[2] if len(sys.argv) > 2 else "results_baseline.jsonl"
    ids = [json.loads(l)["pair_id"] for l in open("pairs.jsonl") if types is None or json.loads(l)["type"] in types]
    with ProcessPoolExecutor(2) as ex, open(outfile, "w") as f:
        for r in ex.map(run, ids, chunksize=8):
            f.write(json.dumps(r) + "\n")
    print("done", len(ids))
