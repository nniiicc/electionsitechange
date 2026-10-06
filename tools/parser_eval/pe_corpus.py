"""Parser evaluation, step 1: select the corpus from the 5 Oct crawl's raw HTML (spec: Parser evaluation).

~100 raw pages, stratified by site builder x homepage/inner page, spread across office tiers, plus aaron4az.com.
A separate set of JavaScript-built homepages (little text in the raw HTML) is rendered once in Chromium.
Read-only on ~/monitor. Writes corpus/<page_id>.html and corpus.csv in the working directory.
"""
import csv, glob, gzip, os, random, re, sys, asyncio
import lxml.html

RAW = os.path.expanduser("~/monitor/raw/2026-10-05")
URLS = os.path.expanduser("~/monitor/snapshots/monitor/monitor_urls.csv")
random.seed(20261006)
BUILDERS = [("squarespace", r"static1\.squarespace\.com|squarespace-cdn|<!-- This is Squarespace"),
            ("wix", r"wixstatic\.com|_wixCssImports|X-Wix-|wix-bolt|thunderbolt"),
            ("wordpress", r"/wp-content/|/wp-includes/|content=\"WordPress"),
            ("nationbuilder", r"nationbuilder\.com|nbuild\.|NationBuilder")]


def builder(html):
    for name, pat in BUILDERS:
        if re.search(pat, html[:400000], re.I):
            return name
    return "other"


def visible_chars(html):
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        return 0
    for bad in doc.xpath("//script|//style|//noscript|//template|//svg|//head"):
        bad.drop_tree()
    return len(" ".join(doc.text_content().split()))


def read(p):
    b = gzip.open(p).read()
    m = re.search(rb'charset=["\']?([A-Za-z0-9_\-]+)', b[:3000])
    try:
        return b.decode(m.group(1).decode() if m else "utf-8", errors="replace")
    except LookupError:
        return b.decode("utf-8", errors="replace")


sites = {r["site_id"]: r for r in csv.DictReader(open(URLS, newline=""))}
homes = [p for p in glob.glob(f"{RAW}/*.html.gz")]
inner = [p for p in glob.glob(f"{RAW}/*/*.html.gz")]
random.shuffle(homes); random.shuffle(inner)

# classify a random pool (enough to fill every stratum), keeping tier diversity
pool = {}
for kind, files in (("home", homes[:2500]), ("inner", inner[:4000])):
    for p in files:
        sid = os.path.basename(p)[:-8] if kind == "home" else os.path.basename(os.path.dirname(p))
        if sid not in sites:
            continue
        h = read(p)
        pool.setdefault((builder(h), kind), []).append((p, sid, visible_chars(h)))

PER = 10
chosen, js_candidates = [], []
for b in [x[0] for x in BUILDERS] + ["other"]:
    for kind in ("home", "inner"):
        rows = pool.get((b, kind), [])
        if kind == "home":
            js_candidates += [r for r in rows if r[2] < 200]
        ok = [r for r in rows if r[2] >= 500]
        by_tier = {}
        for r in ok:
            by_tier.setdefault(sites[r[1]]["office_tier"], []).append(r)
        picks = []
        while len(picks) < PER and any(by_tier.values()):          # round-robin over tiers
            for t in sorted(by_tier):
                if by_tier[t] and len(picks) < PER:
                    picks.append(by_tier[t].pop())
        chosen += [(b, kind, *r) for r in picks]

aaron = f"{RAW}/aaron4az.com__6eb11f.html.gz"
if not any(c[2] == aaron for c in chosen):
    chosen.append(("squarespace", "home", aaron, "aaron4az.com__6eb11f", visible_chars(read(aaron))))

os.makedirs("corpus", exist_ok=True)
out = []
for i, (b, kind, p, sid, vc) in enumerate(chosen):
    pid = f"r{i:03d}"
    open(f"corpus/{pid}.html", "w").write(read(p))
    s = sites[sid]
    out.append(dict(page_id=pid, source="raw", builder=b, kind=kind, site_id=sid, office_tier=s["office_tier"],
                    state=s["state"], raw_path=p, visible_chars=vc))

# JavaScript-built homepages, rendered once in Chromium (connects to a Chromium started by the job on :9222)
from playwright.async_api import async_playwright
random.shuffle(js_candidates)


async def render(cands, n):
    got = []
    async with async_playwright() as pw:
        br = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = await br.new_context(user_agent="CampaignSiteMonitor/0.1 (nonpartisan research archive of 2026 candidate websites)")
        page = await ctx.new_page()
        for p, sid, vc in cands:
            if len(got) >= n:
                break
            try:
                await page.goto(sites[sid]["url"], wait_until="load", timeout=45000)
                await page.wait_for_timeout(4000)
                html = await page.content()
            except Exception as e:
                print("render failed", sid, type(e).__name__, file=sys.stderr); continue
            if visible_chars(html) >= 500:
                got.append((p, sid, vc, html))
        await br.close()
    return got

for j, (p, sid, vc, html) in enumerate(asyncio.run(render(js_candidates, 15))):
    pid = f"j{j:03d}"
    open(f"corpus/{pid}.html", "w").write(html)
    s = sites[sid]
    out.append(dict(page_id=pid, source="rendered", builder=builder(html), kind="home", site_id=sid,
                    office_tier=s["office_tier"], state=s["state"], raw_path=p, visible_chars=visible_chars(html)))

with open("corpus.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
from collections import Counter
print(len(out), "pages |", dict(Counter((r["source"], r["builder"], r["kind"]) for r in out)))
print("tiers:", dict(Counter(r["office_tier"] for r in out)))
print("js candidates seen:", len(js_candidates))
