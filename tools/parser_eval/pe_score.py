"""Parser evaluation, step 4: score every method on every labelled pair (spec: Parser evaluation).

edit pairs:  detected?  and does the reported difference point at the edit (the edit's token appears in the
             reported added content, or the removed text in the reported removed content)?
noise pairs and the identity control: wrongly flagged?
A method passes only if every edit type is fully detected-and-located and no noise or identity pair is flagged.
Writes score_by_type.csv, misses.csv and score_summary.json.
"""
import csv, json, re
from collections import defaultdict

pairs = {json.loads(l)["pair_id"]: json.loads(l) for l in open("pairs.jsonl")}
corpus = {r["page_id"]: r for r in csv.DictReader(open("corpus.csv", newline=""))}
res = defaultdict(dict)
import os
for f in ("results_tools.jsonl", "results_baseline.jsonl", "results_cdio.jsonl", "results_swap.jsonl",
          "results_baseline_swap.jsonl", "results_render.jsonl", "results_render_swap.jsonl",
          "results_collapsed.jsonl", "results_baseline_collapsed.jsonl"):   # later files override
    if os.path.exists(f):
        for l in open(f):
            r = json.loads(l); res[r.pop("pair_id")].update(r)

VARIANTS = {"EDGI text + links": ["edgi_text", "edgi_links"], "EDGI render diff": ["edgi_render"],
            "changedetection.io text": ["cdio"], "snapshot.py (current)": ["baseline"]}
VARIANTS.update({k + " + media list": v + ["media"] for k, v in list(VARIANTS.items())})
N = lambda s: re.sub(r"\s+", "", (s or "").lower())


def combine(r, parts):
    if any("error" in r.get(p, {"error": "missing"}) for p in parts):
        errs = [p for p in parts if "error" in r.get(p, {"error": "missing"})]
        return None, f"error in {','.join(errs)}: {r.get(errs[0], {}).get('error', 'missing')[:80]}"
    return {"detected": any(r[p]["detected"] for p in parts), "ins": " ".join(r[p]["ins"] for p in parts),
            "del": " ".join(r[p]["del"] for p in parts)}, None


def located(lab, out):
    if "added" in lab:
        # character-level diffs (EDGI) can share a letter of the token with the old word, so the token is
        # located when its fixed prefix or its random 5-letter suffix appears in the reported added content
        tok, ins = N(lab["added"]), N(out["ins"])
        return tok[:13] in ins or tok[-5:] in ins
    rem = N(lab["removed"])[:25]
    return bool(rem) and rem in N(out["del"]) or (lab.get("removed_href") and N(lab["removed_href"]) in N(out["del"]))


rows, misses = [], []
summary = {}
for v, parts in VARIANTS.items():
    by = defaultdict(lambda: {"n": 0, "detected": 0, "located": 0, "flagged": 0, "errors": 0})
    for pid, lab in pairs.items():
        t = by[(lab["kind"], lab["type"])]
        t["n"] += 1
        out, err = combine(res.get(pid, {}), parts)
        if err:
            t["errors"] += 1; misses.append({"method": v, "pair_id": pid, "kind": lab["kind"], "type": lab["type"], "problem": err}); continue
        if lab["kind"] == "edit":
            t["detected"] += out["detected"]
            loc = out["detected"] and located(lab, out)
            t["located"] += bool(loc)
            if not loc:
                misses.append({"method": v, "pair_id": pid, "kind": "edit", "type": lab["type"],
                               "problem": "missed" if not out["detected"] else "reported, but not at the edit",
                               "builder": corpus[lab["page_id"]]["builder"], "source": corpus[lab["page_id"]]["source"]})
        else:
            t["flagged"] += out["detected"]
            if out["detected"]:
                misses.append({"method": v, "pair_id": pid, "kind": lab["kind"], "type": lab["type"],
                               "problem": "noise flagged as a change", "builder": corpus[lab["page_id"]]["builder"],
                               "source": corpus[lab["page_id"]]["source"], "reported": (out["ins"] or out["del"])[:200]})
    for (k, typ), t in sorted(by.items()):
        rows.append({"method": v, "kind": k, "type": typ, **t})
    e = [t for (k, _), t in by.items() if k == "edit"]; nz = [t for (k, _), t in by.items() if k != "edit"]
    summary[v] = {"edit_pairs": sum(t["n"] for t in e), "located": sum(t["located"] for t in e),
                  "detected": sum(t["detected"] for t in e),
                  "edit_types_all_located": sum(t["located"] == t["n"] - t["errors"] and not t["errors"] for t in e),
                  "edit_types": len(e), "noise_pairs": sum(t["n"] for t in nz), "noise_flagged": sum(t["flagged"] for t in nz),
                  "errors": sum(t["errors"] for t in by.values())}
    summary[v]["passes"] = (summary[v]["edit_types_all_located"] == summary[v]["edit_types"]
                            and summary[v]["noise_flagged"] == 0 and summary[v]["errors"] == 0)

with open("score_by_type.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
with open("misses.csv", "w", newline="") as f:
    keys = sorted({k for m in misses for k in m})
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(misses)
json.dump(summary, open("score_summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
