"""Rebuild three pair types after test-construction fixes, updating pairs.jsonl:
image_swapped (a new image URL), hidden_text_changed (collapsible content only), attr_whitespace (block-level
whitespace only). Pairs of other types are untouched."""
import json, os, random, shutil, sys
sys.path.insert(0, ".")
import pe_pairs as P
random.seed(66)
FIX = {"image_swapped", "hidden_text_changed", "attr_whitespace"}
rows = [json.loads(l) for l in open("pairs.jsonl")]
for r in rows:
    if r["type"] in FIX:
        shutil.rmtree(f"pairs/{r['pair_id']}", ignore_errors=True)
keep = [r for r in rows if r["type"] not in FIX]
pages = sorted({r["page_id"] for r in rows})
new = []
for pid in pages:
    base = P.ser(P.parse(open(f"corpus/{pid}.html").read()))
    def save(kind, typ, a, b, lab):
        k = f"{pid}-{typ}"; os.makedirs(f"pairs/{k}", exist_ok=True)
        open(f"pairs/{k}/a.html", "w").write(a); open(f"pairs/{k}/b.html", "w").write(b)
        new.append({"pair_id": k, "page_id": pid, "kind": kind, "type": typ, **lab})
    for typ, fn in (("image_swapped", P.ed_image_swapped), ("hidden_text_changed", P.ed_hidden_text_changed)):
        d = P.parse(base); tok = P.token(); lab = fn(d, tok)
        if lab is not None and P.ser(d) != base:
            save("edit", typ, base, P.ser(d), lab)
    da, db = P.parse(base), P.parse(base)
    P.nz_attr_whitespace(da, db)
    save("noise", "attr_whitespace", P.ser(da), P.expand_ws(P.ser(db)), {})
with open("pairs.jsonl", "w") as f:
    for r in keep + new:
        f.write(json.dumps(r) + "\n")
from collections import Counter
print("rebuilt:", dict(Counter(r["type"] for r in new)), "| total pairs:", len(keep) + len(new))
