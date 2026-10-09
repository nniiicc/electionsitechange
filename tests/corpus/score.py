"""Score monitor/detect.py, changes.py and step0.py on the labelled pairs (issues #5, #9, #10).

An edit counts only if it is detected (the page's fingerprint changes), located (the change record
contains the edit's token on its added side, or the removed text on its removed side) AND not
discarded by the step-0 noise rules. A noise or identity pair must not be
detected. `python score.py [--holdout]` prints the tally by type and every failure.
"""
import json, os, re, sys
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "monitor"))
import changes, detect, step0  # noqa: E402

URL = "https://example-campaign.test/"


def N(s):
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", (s or "").lower()))


def score_pair(pair):
    out = {k: v for k, v in pair.items() if k not in ("a", "b")}
    try:
        pa, pb = detect.page(pair["a"], URL), detect.page(pair["b"], URL)
    except Exception as e:
        out.update(ok=False, problem=f"error: {type(e).__name__}: {e}"[:200]); return out
    detected = pa["meta"]["fingerprint"] != pb["meta"]["fingerprint"]
    # the change record (#9) the daily run would write for this pair: only for a detected change
    content = changes.diff_pages(changes.from_page(pa), changes.from_page(pb)) if detected else None
    if pair["kind"] != "edit":
        out.update(ok=not detected, problem="noise flagged as a change" if detected else "")
        if detected:
            la, lb = set(pa["lines"]), set(pb["lines"])
            out["reported"] = {"text_removed": sorted(la - lb)[:3], "text_added": sorted(lb - la)[:3],
                               "links": pa["links"] != pb["links"], "media": pa["media"] != pb["media"]}
        return out
    if content is None:
        out.update(ok=False, problem="missed" if not detected else "detected, but the change record is empty")
        return out
    # located = the change record's added side holds the edit's text more times than its removed side
    # (or the other way round for a removal)
    # sentences are joined as on the page, so a removed passage spanning two sentence lines still matches
    side = lambda k: N(" ".join(content["text"][k]) + json.dumps(
        [content["links"][k], content["media"][k], [v["after" if k == "added" else "before"] for v in content["meta"].values()]],
        ensure_ascii=False))
    fa, fb = side("removed"), side("added")
    if "added" in pair:
        t = N(pair["added"]); located = fb.count(t) > fa.count(t)
    else:
        r = N(pair["removed"])[:25]; h = N(pair.get("removed_href"))
        located = (bool(r) and fa.count(r) > fb.count(r)) or (bool(h) and fa.count(h) > fb.count(h))
    rec = step0.apply(changes.record("2026-10-06", pair["page_id"], "/", content, {}))
    kept = not rec["step0"]["discard"]
    out.update(ok=located and kept,
               problem="" if located and kept else ("reported, but not at the edit" if not located
                                                    else f"discarded by step 0: {rec['step0']['reasons']}"))
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
