"""Image-and-embed list for a page: the one piece the parser evaluation lets us write ourselves (spec).

Records every image (src, srcset candidates, lazy-load attributes, CSS background images), its alt text,
and every video/iframe/embed source. URLs are normalised so that size variants and cache-busting
parameters of the SAME image compare equal: query and fragment dropped, WordPress `-300x200` size
suffixes dropped, Wix `/v1/...` transform paths dropped.
"""
import re
from html.parser import HTMLParser

BG = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)


def norm_url(u):
    u = (u or "").strip()
    if not u or u.startswith(("data:", "javascript:", "about:")):
        return None
    u = re.split(r"[?#]", u, 1)[0]
    u = re.sub(r"^(https?:)?//", "//", u, flags=re.I)
    m = re.match(r"(//[^/]+)(.*)", u)
    if m:
        u = m.group(1).lower() + m.group(2)
    u = re.sub(r"(wixstatic\.com/media/[^/]+)/v1/.*", r"\1", u)
    u = re.sub(r"-\d{2,4}x\d{2,4}(?=\.\w{3,4}$)", "", u)
    return u or None


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = set()
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "template"):
            self.skip += 1
            return
        if self.skip:
            return
        urls = []
        if tag in ("img", "source"):
            for k in ("src", "data-src", "data-image", "data-lazy-src"):
                urls.append(a.get(k))
            for k in ("srcset", "data-srcset"):
                for part in (a.get(k) or "").split(","):
                    if part.strip():
                        urls.append(part.split()[0])
            for u in filter(None, map(norm_url, urls)):
                self.items.add("img:" + u)
            if tag == "img" and a.get("alt"):
                src = next(filter(None, map(norm_url, urls)), "")
                self.items.add(f"alt:{src}|{' '.join(a['alt'].split())}")
        if tag in ("iframe", "embed", "video", "audio", "object"):
            for k in ("src", "data-src", "data", "poster"):
                u = norm_url(a.get(k))
                if u:
                    self.items.add("embed:" + u)
        for u in BG.findall(a.get("style") or ""):
            u = norm_url(u)
            if u:
                self.items.add("img:" + u)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self.skip:
            self.skip -= 1


def media_list(html):
    p = _P()
    try:
        p.feed(html); p.close()
    except Exception:
        pass
    return p.items
