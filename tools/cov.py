
import os, gzip, glob, json, random, re
from urllib.parse import urlparse
R = os.path.expanduser("~/monitor")
raw = sorted(glob.glob(R + "/raw/2026-10-05/*.html.gz")); random.seed(1); samp = random.sample(raw, 300)
ratios = []
for p in samp:
    html = gzip.open(p).read().decode("utf-8", "replace")
    vis = " ".join(re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>|<[^>]+>", " ", html).split())
    t = " ".join(open(f"{R}/snapshots/sites/{os.path.basename(p)[:-8]}/text.md").read().split())
    if len(vis) > 300: ratios.append(len(t) / len(vis))
q = sorted(ratios); n = len(q)
out = {"sample": n, "kept_p10": round(q[n//10],2), "kept_median": round(q[n//2],2), "kept_p90": round(q[9*n//10],2),
       "kept_under_50pct": sum(r < 0.5 for r in q)}
inner = []
for d in glob.glob(R + "/snapshots/sites/*/"):
    m = json.load(open(d + "meta.json")); host = urlparse(m["final_url"]).netloc.lower().removeprefix("www.")
    pages = {urlparse(u).path for u in json.load(open(d + "links.json"))
             if urlparse(u).netloc == host and urlparse(u).path not in ("", "/")
             and not re.search(r"\.(jpe?g|png|gif|svg|css|js|ico|webp|mp4)$", urlparse(u).path, re.I)}
    inner.append(len(pages))
inner.sort(); n = len(inner)
out.update(sites=n, inner_median=inner[n//2], inner_p75=inner[3*n//4], inner_p90=inner[9*n//10],
           inner_p99=inner[99*n//100], inner_zero=sum(x == 0 for x in inner), inner_total=sum(inner),
           pdf_links=sum(1 for d in glob.glob(R + "/snapshots/sites/*/links.json") for u in json.load(open(d)) if u.lower().endswith(".pdf")))
json.dump(out, open("cov.json", "w"), indent=1); print(json.dumps(out))
