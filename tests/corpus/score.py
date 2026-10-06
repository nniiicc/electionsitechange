"""Score monitor/detect.py on the labelled pairs (issue #5).

An edit counts only if it is detected (the page's fingerprint changes) AND located (the snapshot
difference contains the edit's token, or the removed text). A noise or identity pair must not be
detected. `python score.py [--holdout]` prints the tally by type and every failure.
"""
import json, os, re, sys
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "monitor"))
import detect  # noqa: E402

URL = "https://example-campaign.test/"


def flat(p):
    """everything a snapshot records, as one string, digits masked as the noise rules may mask them"""
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", (p["text"] + json.dumps(p["links"], ensure_ascii=False)
                                                   + json.dumps(p["media"], ensure_ascii=False) + p["meta"]["title"]
                                                   + p["meta"]["description"]).lower()))


def N(s):
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", (s or "").lower()))


def score_pair(pair):
    out = {k: v for k, v in pair.items() if k not in ("a", "b")}
    try:
        pa, pb = detect.page(pair["a"], URL), detect.page(pair["b"], URL)
    except Exception as e:
        out.update(ok=False, problem=f"error: {type(e).__name__}: {e}"[:200]); return out
    detected = pa["meta"]["fingerprint"] != pb["meta"]["fingerprint"]
    if pair["kind"] != "edit":
        out.update(ok=not detected, problem="noise flagged as a change" if detected else "")
        if detected:
            la, lb = set(pa["lines"]), set(pb["lines"])
            out["reported"] = {"text_removed": sorted(la - lb)[:3], "text_added": sorted(lb - la)[:3],
                               "links": pa["links"] != pb["links"], "media": pa["media"] != pb["media"]}
        return out
    fa, fb = flat(pa), flat(pb)
    if "added" in pair:
        # located = the snapshot holds the edit's text more times after than before (a menu item or a
        # sentence may also appear elsewhere on the page, e.g. in the footer)
        t = N(pair["added"]); located = fb.count(t) > fa.count(t)
    else:
        r = N(pair["removed"])[:25]; h = N(pair.get("removed_href"))
        located = (bool(r) and fa.count(r) > fb.count(r)) or (bool(h) and fa.count(h) > fb.count(h))
    out.update(ok=detected and located,
               problem="" if detected and located else ("missed" if not detected else "reported, but not at the edit"))
    return out


def run(pairs, procs=None):
    with Pool(procs) as pool:
        return list(pool.imap_unordered(score_pair, pairs, chunksize=8))


def tally(results):
    t = defaultdict(lambda: [0, 0])
    for r in results:
        t[(r["kind"], r["type"])][0] += r["ok"]; t[(r["kind"], r["type"])][1] += 1
    return dict(sorted(t.items()))


if __name__ == "__main__":
    import make_pairs, holdout_noise
    gen = holdout_noise.pairs(HERE) if "--holdout" in sys.argv else make_pairs.pairs(HERE)
    res = run(gen)
    for (k, typ), (ok, n) in tally(res).items():
        print(f"{k:8s} {typ:34s} {ok:4d}/{n:<4d} {'ok' if ok == n else 'FAIL'}")
    bad = sorted((r for r in res if not r["ok"]), key=lambda r: r["pair_id"])
    print(f"\n{len(bad)} failures")
    for r in bad:
        print(json.dumps({k: v for k, v in r.items() if k in ("pair_id", "problem", "reported", "added", "removed")},
                         ensure_ascii=False)[:400])
    json.dump(res, open(os.environ.get("SCORE_OUT", os.devnull), "w"), indent=0)
