"""Read-only inspection of specific parser-evaluation pairs (local files only)."""
import json, re, sys
import lxml.html
sys.path.insert(0, ".")
P = {json.loads(l)["pair_id"]: json.loads(l) for l in open("pairs.jsonl")}
R = {json.loads(l)["pair_id"]: json.loads(l) for l in open("results_tools.jsonl")}
ws = [k for k, p in P.items() if p["type"] == "attr_whitespace"]
print("== EDGI text, attr_whitespace pairs with non-whitespace diff")
for k in ws:
    t = R[k]["edgi_text"]
    if t.get("detected") and re.sub(r"\s", "", t["ins"] + t["del"]):
        print(k, "| ins:", repr(t["ins"][:90]), "| del:", repr(t["del"][:90]))
print("== EDGI links, attr_whitespace pairs flagged")
for k in ws:
    t = R[k]["edgi_links"]
    if t.get("detected"):
        print(k, "| ins:", t["ins"][:160], "| del:", t["del"][:160])
print("== hidden_text edits: the changed element and its hiding ancestor")
for k in sys.argv[1].split(","):
    tok = P[k]["added"]
    doc = lxml.html.fromstring(open(f"pairs/{k}/b.html").read())
    for e in doc.iter():
        if isinstance(e.tag, str) and e.text and tok in e.text:
            chain = []
            for a in [e, *e.iterancestors()]:
                st, cl = a.get("style") or "", a.get("class") or ""
                if a.get("hidden") is not None or "display" in st.replace(" ", "") or a.tag == "details" or re.search(r"accordion|collaps|tab|toggle|faq|panel", cl, re.I) or a.get("aria-hidden"):
                    chain.append(f"<{a.tag} class='{cl[:50]}' style='{st[:40]}' hidden={a.get('hidden')} aria-hidden={a.get('aria-hidden')}>")
            print(k, "| text:", e.text.strip()[:80], "\n    hiding:", chain[:3])
            break
