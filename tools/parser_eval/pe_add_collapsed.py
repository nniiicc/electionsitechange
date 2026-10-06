"""Add one edit type: text changed inside collapsed content (accordion, tab panel, <details>, FAQ answer).
Only 3 of the 97 corpus pages have real collapsible content, too few to judge, so each page also gets a
collapsed block in one of four common markups, present on both sides; only its hidden text differs."""
import json, os, random, sys
sys.path.insert(0, ".")
import pe_pairs as P
random.seed(77)
TEXT = "Our plan expands broadband to every county and caps internet bills for {w} families by 2028."
MARKUP = [
    '<details><summary>Our broadband plan</summary><p>{t}</p></details>',
    '<div class="accordion-item"><button class="accordion-toggle">Our broadband plan</button>'
    '<div class="accordion-content" style="display:none"><p>{t}</p></div></div>',
    '<div class="tabs"><button role="tab">Broadband</button><div class="tab-panel" role="tabpanel" hidden><p>{t}</p></div></div>',
    '<div class="faq"><h3>What is the broadband plan?</h3><div class="faq-answer" aria-hidden="true" '
    'style="max-height:0;overflow:hidden"><p>{t}</p></div></div>']
rows = [json.loads(l) for l in open("pairs.jsonl")]
rows = [r for r in rows if r["type"] != "collapsed_text_injected"]
n = 0
for pid in sorted({r["page_id"] for r in rows}):
    base = P.ser(P.parse(open(f"corpus/{pid}.html").read()))
    m = random.choice(MARKUP); tok = P.token()
    a, b = P.parse(base), P.parse(base)
    P.inject(a, m.format(t=TEXT.format(w="working")), "end")
    P.inject(b, m.format(t=TEXT.format(w=tok)), "end")
    k = f"{pid}-collapsed_text_injected"; os.makedirs(f"pairs/{k}", exist_ok=True)
    open(f"pairs/{k}/a.html", "w").write(P.ser(a)); open(f"pairs/{k}/b.html", "w").write(P.ser(b))
    rows.append({"pair_id": k, "page_id": pid, "kind": "edit", "type": "collapsed_text_injected", "added": tok,
                 "markup": ["details", "display_none_accordion", "hidden_tabpanel", "aria_hidden_faq"][MARKUP.index(m)]})
    n += 1
with open("pairs.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print("added", n)
