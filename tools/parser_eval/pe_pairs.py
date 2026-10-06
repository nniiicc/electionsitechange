"""Parser evaluation, step 2: build labelled page pairs from the corpus (spec: Parser evaluation).

For every corpus page, `a` is the page and `b` is the page with ONE labelled change:
  edit  - a change that must be detected (each carries a unique token, or the removed text, to check
          that the reported difference points at the right place)
  noise - a change that must be ignored
  identity - a == b, a sanity control
Both sides are serialised by the same parser, so serialisation itself never differs between a and b.
Writes pairs/<pair_id>/{a,b}.html and pairs.jsonl.
"""
import copy, csv, json, os, random, re, string
import lxml.html
from lxml import etree

random.seed(6)
SKIP_ANC = {"script", "style", "noscript", "template", "head", "svg"}
CHROME_ANC = {"nav", "header", "footer"}
HIDDEN_CLASS = re.compile(r"accordion|collaps|tab-pane|tabs__panel|toggle-content|faq-answer|panel-body", re.I)
VIDEO = re.compile(r"youtube|youtu\.be|vimeo|player|video|wistia|facebook\.com/plugins/video", re.I)


def ser(doc):
    return lxml.html.tostring(doc, encoding="unicode", doctype="<!DOCTYPE html>")


def parse(html):
    return lxml.html.fromstring(html)


def token():
    return "Quillfeather" + "".join(random.choice(string.ascii_lowercase) for _ in range(5))


def ancestors(el):
    p = el.getparent()
    while p is not None:
        yield p
        p = p.getparent()


def is_hidden(el):
    for e in [el, *ancestors(el)]:
        st = (e.get("style") or "").replace(" ", "").lower()
        if e.get("hidden") is not None or "display:none" in st or e.get("aria-hidden") == "true":
            return True
        if e.tag == "details" and el.tag != "summary" and not any(a.tag == "summary" for a in [el, *ancestors(el)]):
            return True
        if HIDDEN_CLASS.search(e.get("class") or "") and e is not el:
            return True
    return False


def ok(el, chrome=False, hidden=None):
    if not isinstance(el.tag, str):
        return False
    tags = {a.tag for a in ancestors(el)} | {el.tag}
    if tags & SKIP_ANC:
        return False
    if not chrome and tags & CHROME_ANC:
        return False
    if hidden is not None and is_hidden(el) != hidden:
        return False
    return True


def holder(el, n):
    """el or its first descendant whose own text has at least n characters"""
    for e in el.iter():
        if isinstance(e.tag, str) and e.text and len(e.text.strip()) >= n and e.tag not in SKIP_ANC:
            return e
    return None


def replace_word(e, tok):
    w = e.text.split()
    i = min(3, len(w) - 1)
    lead = e.text[:len(e.text) - len(e.text.lstrip())]
    w[i] = tok
    e.text = lead + " ".join(w)


def pick(cands):
    return random.choice(cands) if cands else None


# ------------------------------------------------------------------ edits (must be detected)
def ed_sentence_reworded(doc, tok):
    e = pick([h for h in (holder(p, 40) for p in doc.iter("p") if ok(p, hidden=False)) if h is not None])
    if e is None: return None
    replace_word(e, tok); return {"added": tok}


def ed_sentence_added(doc, tok):
    e = pick([h for h in (holder(p, 40) for p in doc.iter("p") if ok(p, hidden=False)) if h is not None])
    if e is None: return None
    e.text = e.text.rstrip() + f" We will also fund the {tok} project in every county."
    return {"added": tok}


def ed_sentence_removed(doc, tok):
    ps = [p for p in doc.iter("p") if ok(p, hidden=False) and len(" ".join(p.text_content().split())) >= 40]
    p = pick(ps)
    if p is None: return None
    txt = " ".join(p.text_content().split())
    parts = re.split(r"(?<=[.!?])\s+", (p.text or "").strip()) if not len(p) else []
    if len(parts) >= 2 and len(parts[0]) >= 25:
        p.text = " ".join(parts[1:]); return {"removed": parts[0]}
    p.drop_tree(); return {"removed": txt}


def ed_heading_changed(doc, tok):
    hs = [h for h in (holder(x, 3) for x in doc.iter("h1", "h2", "h3", "h4") if ok(x, hidden=False)) if h is not None]
    e = pick(hs)
    if e is None: return None
    e.text = e.text.rstrip() + f" {tok}"; return {"added": tok}


COLLAPSE = re.compile(r"accordion|tab-?pane|tabs__panel|tabpanel|collaps|toggle-content|faq-answer|panel-body", re.I)


def is_collapsed(el):
    """inside a collapsible accordion, tab panel or <details> body (content a visitor opens by clicking).
    Plain display:none utility text (screen-reader hints, form success messages) does not count."""
    anc = list(ancestors(el))
    if any(a.tag == "summary" for a in [el, *anc]):
        return False
    return any(a.tag == "details" or a.get("role") == "tabpanel" or COLLAPSE.search(a.get("class") or "") for a in anc)


def ed_hidden_text_changed(doc, tok):
    cands = [e for e in doc.iter() if isinstance(e.tag, str) and e.text and len(e.text.strip()) >= 20
             and ok(e, chrome=True) and is_collapsed(e)]
    e = pick(cands)
    if e is None: return None
    replace_word(e, tok); return {"added": tok}


def ed_list_item_changed(doc, tok):
    lis = [h for h in (holder(li, 10) for li in doc.iter("li") if ok(li, hidden=False)) if h is not None]
    e = pick(lis)
    if e is None: return None
    replace_word(e, tok) if len(e.text.split()) > 1 else setattr(e, "text", e.text + f" {tok}")
    return {"added": tok}


def content_imgs(doc):
    return [i for i in doc.iter("img") if ok(i, chrome=True) and (i.get("src") or i.get("data-src"))
            and not (i.get("src") or "").startswith("data:")]


def ed_image_swapped(doc, tok):
    i = pick(content_imgs(doc))
    if i is None: return None
    # a different image file: a new URL, not a new filename under the old image's path (on Wix the old
    # path carries the media id, so keeping it would keep the same image)
    for att in ("src", "data-src"):
        if i.get(att):
            i.set(att, f"https://images.example-campaign.test/{tok}.jpg")
    for att in ("srcset", "data-srcset"):
        if i.get(att):
            i.set(att, f"/media/{tok}.jpg 1000w")
    par = i.getparent()                                   # <picture><source srcset>
    if par is not None and par.tag == "picture":
        for s in par.iter("source"):
            s.set("srcset", f"/media/{tok}.jpg 1000w")
    return {"added": tok}


def ed_image_alt_changed(doc, tok):
    i = pick(content_imgs(doc))
    if i is None: return None
    i.set("alt", f"{tok} at a town hall"); return {"added": tok}


def ed_link_target_changed(doc, tok):
    links = [a for a in doc.iter("a") if ok(a, hidden=False) and (a.get("href") or "")[:1] not in ("", "#")
             and not re.match(r"(mailto|tel|javascript):", a.get("href") or "", re.I) and a.text_content().strip()]
    a = pick(links)
    if a is None: return None
    a.set("href", f"/{tok.lower()}"); return {"added": tok.lower()}


def nav_lists(doc):
    """menus: a container inside <nav>/<header> (or with a menu/nav class) with 2+ child items that each hold
    a link with text. Lists are preferred; div-based menus (Squarespace, Wix) are used when there is no list."""
    lists, divs = [], []
    for el in doc.iter():
        if not isinstance(el.tag, str) or not ok(el, chrome=True):
            continue
        inside = {x.tag for x in ancestors(el)} & {"nav", "header"} or re.search(r"menu|nav", el.get("class") or "", re.I)
        if not inside:
            continue
        items = [c for c in el if isinstance(c.tag, str)
                 and (c.tag == "a" or len(c.findall(".//a")) == 1) and c.text_content().strip()
                 and len(" ".join(c.text_content().split())) <= 60]
        if len(items) >= 2:
            (lists if el.tag in ("ul", "ol") else divs).append((el, items))
    return lists or divs


def item_link(item):
    return item if item.tag == "a" else item.find(".//a")


def ed_menu_page_added(doc, tok):
    n = pick(nav_lists(doc))
    if n is None: return None
    ul, lis = n
    new = copy.deepcopy(lis[-1])
    a = item_link(new)
    if a is not new:                       # keep only the wrapper chain down to the link
        for sub in list(new):
            if sub is not a and a not in sub.iter():
                new.remove(sub)
    for c in list(a):
        a.remove(c)
    a.text = tok
    a.set("href", f"/{tok.lower()}")
    new.tail = lis[-1].tail
    lis[-1].addnext(new); return {"added": tok}


def ed_menu_page_removed(doc, tok):
    n = pick(nav_lists(doc))
    if n is None: return None
    ul, lis = n
    li = lis[-1]
    a = item_link(li)
    txt = " ".join(a.text_content().split()) or " ".join(li.text_content().split())
    href = a.get("href") or ""
    li.drop_tree(); return {"removed": txt, "removed_href": href}


def ed_video_changed(doc, tok):
    vs = [v for v in doc.iter("iframe", "video", "source", "embed") if VIDEO.search(v.get("src") or v.get("data-src") or "")]
    v = pick(vs)
    if v is None: return None
    att = "src" if v.get("src") else "data-src"
    u = v.get(att)
    head, q = (u.split("?", 1) + [""])[:2]
    v.set(att, head.rsplit("/", 1)[0] + f"/{tok}" + (f"?{q}" if q else ""))
    return {"added": tok}


def ed_paid_for_by_changed(doc, tok):
    for e in doc.iter():
        if not isinstance(e.tag, str) or not ok(e, chrome=True):
            continue
        for att in ("text", "tail"):
            v = getattr(e, att)
            if v and re.search(r"paid\s+for\s+by", v, re.I):
                setattr(e, att, re.sub(r"(paid\s+for\s+by)\s*.*", rf"\1 {tok} for Office", v, flags=re.I | re.S))
                return {"added": tok}
    return None


EDITS = [(k[3:], v) for k, v in list(globals().items()) if k.startswith("ed_")]


# ------------------------------------------------------------------ noise (must be ignored)
def body(doc):
    b = doc.find(".//body")
    return b if b is not None else doc


def inject(doc, frag, where="top"):
    el = lxml.html.fragment_fromstring(frag)
    b = body(doc)
    (b.insert(0, el) if where == "top" else b.append(el))


def rnd(n=10):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def nz_tokens_build_ids(a, b):
    for d in (a, b):
        r = rnd()
        for i in d.iter("input"):
            if (i.get("type") or "").lower() == "hidden" and re.search(r"nonce|token|csrf|_wp|build", i.get("name") or "", re.I):
                i.set("value", rnd(16))
        for s in d.iter("script", "link"):
            att = "src" if s.tag == "script" else "href"
            v = s.get(att)
            if v and re.search(r"[?&](ver|v|build|version|ts)=", v):
                s.set(att, re.sub(r"([?&](ver|v|build|version|ts)=)[^&]*", rf"\g<1>{rnd(6)}", v))
        head = d.find(".//head")
        if head is not None:
            head.append(lxml.html.fragment_fromstring(f'<meta name="csrf-token" content="{r}">'))
            head.append(lxml.html.fragment_fromstring(f'<script src="/assets/app.js?build={r}"></script>'))
        inject(d, f'<form action="/signup"><input type="hidden" name="_token" value="{r}"></form>', "end")
        for e in d.iter():
            if isinstance(e.tag, str) and e.get("data-build-id") is not None:
                e.set("data-build-id", r)
    return True


def nz_script_style(a, b):
    for d, k in ((a, "1"), (b, "2")):
        for s in d.iter("script"):
            if s.text and s.text.strip():
                s.text = s.text + f"\n/* r{k}{rnd()} */"
        for s in d.iter("style"):
            if s.text and s.text.strip():
                s.text = s.text + f"\n.x{k}{rnd()}{{color:#0{k}0}}"
        inject(d, f'<script>window.__BUILD="{rnd()}";</script>', "end")
        inject(d, f"<style>.hero-{k}{{margin:{k}px}}</style>", "end")
    return True


def nz_attr_whitespace(a, b):
    for e in b.iter():
        if isinstance(e.tag, str) and len(e.attrib) > 1:
            items = list(e.attrib.items())[::-1]
            e.attrib.clear()
            for k, v in items:
                e.set(k, v)
    return "whitespace"          # whitespace between tags is expanded after serialising b


COUNTDOWN = ['<div class="countdown"><span>{d}</span> Days <span>{h}</span> Hours <span>{m}</span> Minutes</div>',
             '<p class="election-countdown">Only {d} days until Election Day!</p>',
             '<div class="timer">{d}d : {h}h : {m}m : {s}s</div>']
DONATION = ['<div class="donate-progress"><strong>${x:,}</strong> raised of ${g:,} goal</div>',
            '<div class="thermometer">{pct}% funded - {n} donors</div>',
            '<p class="goal">We have raised ${x:,} toward our ${g:,} goal.</p>']
RELDATE = ['<div class="post-date">Posted {n} days ago</div>', '<span class="updated">Updated {n} hours ago</span>',
           '<p class="news-meta">{n} minutes ago - Campaign News</p>']
COOKIE = [('<div id="cookie-banner">We use cookies to improve your experience. <button>Accept</button></div>',
           '<div id="cookie-banner">This website uses cookies to analyse traffic. <button>Accept all</button></div>'),
          ('<div class="cookie-consent">By continuing you agree to our use of cookies. <a href="/privacy">Learn more</a></div>',
           '<div class="cookie-consent">We and our partners use cookies for analytics. <a href="/privacy">Privacy policy</a></div>')]


def nz_countdown(a, b):
    t = random.choice(COUNTDOWN)
    inject(a, t.format(d=29, h=14, m=7, s=41)); inject(b, t.format(d=28, h=13, m=52, s=3)); return True


def nz_donation(a, b):
    t = random.choice(DONATION)
    inject(a, t.format(x=12450, g=25000, pct=49, n=183)); inject(b, t.format(x=14980, g=25000, pct=59, n=211)); return True


def nz_relative_date(a, b):
    t = random.choice(RELDATE)
    inject(a, t.format(n=3), "end"); inject(b, t.format(n=4), "end"); return True


def nz_copyright_year(a, b):
    found = False
    for da, db in zip(a.iter(), b.iter()):
        if not isinstance(da.tag, str):
            continue
        for att in ("text", "tail"):
            va = getattr(da, att)
            if va and re.search(r"(©|&copy;|copyright)\s*(\d{4})", va, re.I):
                setattr(da, att, re.sub(r"((?:©|copyright)\s*)\d{4}", r"\g<1>2025", va, flags=re.I))
                setattr(db, att, re.sub(r"((?:©|copyright)\s*)\d{4}", r"\g<1>2026", va, flags=re.I))
                found = True
    if not found:
        inject(a, "<p>© 2025 Friends of the Campaign. All rights reserved.</p>", "end")
        inject(b, "<p>© 2026 Friends of the Campaign. All rights reserved.</p>", "end")
    return True


def nz_cookie_banner(a, b):
    ta, tb = random.choice(COOKIE)
    inject(a, ta, "end"); inject(b, tb, "end"); return True


def nz_image_params(a, b):
    ia, ib = content_imgs(a), content_imgs(b)
    if not ia:
        return None

    def bump(u, k):
        if not u or u.startswith("data:"):
            return u
        u = re.sub(r"format=\d+w", f"format={750 if k == 1 else 1000}w", u)
        u = re.sub(r"/v1/fill/w_\d+,h_\d+", f"/v1/fill/w_{400 * k},h_{300 * k}", u)
        u = re.sub(r"-\d{2,4}x\d{2,4}(\.\w{3,4})(?=$|\?)", rf"-{300 * k}x{200 * k}\1", u)
        return u + ("&" if "?" in u else "?") + f"v={k}{rnd(4)}"
    for imgs, k in ((ia, 1), (ib, 2)):
        for i in imgs:
            for att in ("src", "data-src"):
                if i.get(att):
                    i.set(att, bump(i.get(att), k))
            for att in ("srcset", "data-srcset"):
                if i.get(att):
                    i.set(att, ", ".join(" ".join([bump(p.split()[0], k)] + p.split()[1:]) for p in i.get(att).split(",") if p.strip()))
    return True


NOISE = [(k[3:], v) for k, v in list(globals().items()) if k.startswith("nz_")]


BLOCK = r"(?:div|p|li|ul|ol|section|header|footer|nav|main|article|aside|form|table|thead|tbody|tr|td|th|h[1-6]|figure|body|html|head|meta|link|script|style)"


def expand_ws(html):
    """re-indent: widen whitespace only between two block-level tags, where it never renders"""
    parts = re.split(r"(<pre\b.*?</pre>)", html, flags=re.S | re.I)      # never touch preformatted text
    return "".join(p if p[:4].lower() == "<pre" else _ws(p) for p in parts)


def _ws(html):
    return re.sub(rf"(</{BLOCK}>|<{BLOCK}\b[^>]*>)(\s+)(?=</?{BLOCK}\b)", lambda m: m.group(1) + m.group(2) + "  \n   ", html)


def main():
    rows = list(csv.DictReader(open("corpus.csv", newline="")))
    os.makedirs("pairs", exist_ok=True)
    out, na = [], {}
    for r in rows:
        try:
            base_doc = parse(open(f"corpus/{r['page_id']}.html").read())
        except (etree.ParserError, ValueError) as e:
            print("unparseable", r["page_id"], e); continue
        base = ser(base_doc)
        def save(kind, typ, a, b, lab):
            pid = f"{r['page_id']}-{typ}"
            os.makedirs(f"pairs/{pid}", exist_ok=True)
            open(f"pairs/{pid}/a.html", "w").write(a); open(f"pairs/{pid}/b.html", "w").write(b)
            out.append({"pair_id": pid, "page_id": r["page_id"], "kind": kind, "type": typ, **lab})
        save("identity", "identity", base, base, {})
        for typ, fn in EDITS:
            d = parse(base); tok = token()
            lab = fn(d, tok)
            if lab is None:
                na[typ] = na.get(typ, 0) + 1; continue
            b = ser(d)
            if b == base:
                na[typ] = na.get(typ, 0) + 1; continue
            save("edit", typ, base, b, lab)
        for typ, fn in NOISE:
            da, db = parse(base), parse(base)
            res = fn(da, db)
            if res is None:
                na[typ] = na.get(typ, 0) + 1; continue
            a, b = ser(da), ser(db)
            if res == "whitespace":
                b = expand_ws(b)
            save("noise", typ, a, b, {})
    with open("pairs.jsonl", "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    from collections import Counter
    print(len(out), "pairs |", dict(Counter((o["kind"], o["type"]) for o in out)))
    print("not applicable (page lacks the element):", na)


if __name__ == "__main__":
    main()
