"""Pick the change records to hand-label for calibration (issue #10).

Takes the records kept by step 0 from the given days' changes/<day>.jsonl, and draws about N of them spread
across office tiers and change types (text, links, images, metadata, page added or removed), at most 2 per
site, so a few busy sites can't dominate. Deterministic for the same inputs.

usage: python tools/sample_changes.py REPO 2026-10-08 2026-10-09 ... --n 200 --out data/labels/to_label.jsonl
Open the output in tools/label_changes.html.
"""
import argparse, json, os, random
from collections import defaultdict


def change_type(r):
    if r["kind"] != "changed":
        return "page_" + r["kind"]
    parts = [k for k in ("text", "links", "media") if r[k]["removed"] or r[k]["added"]] + (["meta"] if r["meta"] else [])
    return "+".join(parts) or "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo"); ap.add_argument("days", nargs="+")
    ap.add_argument("--n", type=int, default=200); ap.add_argument("--per-site", type=int, default=2)
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    recs = []
    for d in a.days:
        p = os.path.join(a.repo, "changes", f"{d}.jsonl")
        if os.path.exists(p):
            recs += [r for r in map(json.loads, open(p)) if not (r.get("step0") or {}).get("discard")]
    rng = random.Random(a.seed)
    strata = defaultdict(list)
    for r in recs:
        strata[(r.get("office_tier") or "unknown", change_type(r))].append(r)
    for v in strata.values():
        rng.shuffle(v)
    picked, per_site = [], defaultdict(int)
    keys = sorted(strata)
    while len(picked) < a.n and any(strata.values()):      # round-robin over strata
        for k in keys:
            while strata[k]:
                r = strata[k].pop()
                if per_site[r["site_id"]] < a.per_site:
                    per_site[r["site_id"]] += 1; picked.append(r); break
            if len(picked) >= a.n:
                break
    rng.shuffle(picked)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        for r in picked:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tiers = defaultdict(int); types = defaultdict(int)
    for r in picked:
        tiers[r.get("office_tier") or "unknown"] += 1; types[change_type(r)] += 1
    print(json.dumps({"kept_records": len(recs), "picked": len(picked), "sites": len(per_site),
                      "by_tier": dict(tiers), "by_type": dict(types)}, indent=1))


if __name__ == "__main__":
    main()
