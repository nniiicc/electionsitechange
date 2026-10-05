#!/usr/bin/env python3
"""Fetch a small text extract from each campaign website, for attribution checking.

Run on a machine with ordinary internet access:

    pip install requests
    python fetch_pages.py attribution_pilot_input.csv page_extracts.csv

Reads any CSV with `row_id` and `url` columns. For each URL it saves ONLY a compact
extract - never the full page:
    title, meta description, og:site_name, first H1/H2 headings, any "Paid for by" /
    "Authorized by" disclaimer sentence, the years 2016-2027 mentioned and how often,
    and the first ~1,500 characters of visible body text.

Resumable: re-running with the same output file skips row_ids already recorded.
The pilot (~195 URLs) takes about a minute; the full ~8,500 about 10-15 minutes.
"""
import csv
import os
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

import requests

TIMEOUT = 15
THREADS = 16
MAX_BYTES = 600_000          # stop reading a page after this; extracts only need the top
BODY_CHARS = 1500
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

FIELDS = ["row_id", "url", "status_code", "final_url", "error", "content_type",
          "title", "meta_description", "og_site_name", "headings", "disclaimer",
          "years", "body_text"]

DISCLAIMER = re.compile(
    r"(paid for by[^.<\n]{3,160}|authori[sz]ed by[^.<\n]{3,160}|"
    r"(?:committee|friends|citizens) (?:to|for) (?:elect|re-?elect)[^.<\n]{3,120})", re.I)
YEAR = re.compile(r"\b(20(?:1[6-9]|2[0-7]))\b")


class Extract(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta_desc, self.og_site = "", "", ""
        self.headings, self.text = [], []
        self._in_title = False
        self._heading = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("description", "og:description") and not self.meta_desc:
                self.meta_desc = a.get("content", "")
            elif name == "og:site_name":
                self.og_site = a.get("content", "")
        elif tag in ("h1", "h2") and len(self.headings) < 8:
            self._heading = []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2") and self._heading is not None:
            h = " ".join("".join(self._heading).split())
            if h:
                self.headings.append(h[:140])
            self._heading = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
            return
        if self._heading is not None:
            self._heading.append(data)
        s = data.strip()
        if s:
            self.text.append(s)


def fetch(row):
    out = dict.fromkeys(FIELDS, "")
    out["row_id"], out["url"] = row["row_id"], row["url"]
    url = row["url"].strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True,
                         headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8",
                                  "Accept-Language": "en-US,en;q=0.9"})
        out["status_code"], out["final_url"] = r.status_code, r.url
        out["content_type"] = r.headers.get("Content-Type", "")[:60]
        raw = b""
        for chunk in r.iter_content(32_768):
            raw += chunk
            if len(raw) >= MAX_BYTES:
                break
        r.close()
        html = raw.decode(r.encoding or "utf-8", errors="replace")
    except Exception as e:                      # noqa: BLE001 - never kill the pool
        out["error"] = f"{type(e).__name__}: {str(e)[:140]}"
        return out

    p = Extract()
    try:
        p.feed(html)
    except Exception as e:                      # malformed HTML: keep what was parsed
        out["error"] = f"parse: {type(e).__name__}"
    body = " ".join(" ".join(p.text).split())
    out["title"] = " ".join(p.title.split())[:200]
    out["meta_description"] = " ".join(p.meta_desc.split())[:300]
    out["og_site_name"] = p.og_site[:120]
    out["headings"] = " | ".join(p.headings)[:600]
    d = DISCLAIMER.search(body) or DISCLAIMER.search(html)
    out["disclaimer"] = " ".join(d.group(1).split())[:200] if d else ""
    yrs = Counter(YEAR.findall(body))
    out["years"] = ";".join(f"{y}:{n}" for y, n in sorted(yrs.items()))
    out["body_text"] = body[:BODY_CHARS]
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <input.csv> [output.csv]")
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else "page_extracts.csv"
    with open(inp, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("url") or "").strip()]
    done = set()
    if os.path.exists(outp):
        with open(outp, newline="", encoding="utf-8") as f:
            done = {r["row_id"] for r in csv.DictReader(f)}
        print(f"resuming: {len(done):,} already fetched")
    todo = [r for r in rows if r["row_id"] not in done]
    print(f"{len(rows):,} rows | {len(todo):,} to fetch | {THREADS} threads")
    lock, n = threading.Lock(), 0
    with open(outp, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not done:
            w.writeheader()
        with ThreadPoolExecutor(max_workers=THREADS) as ex:
            for fut in as_completed([ex.submit(fetch, r) for r in todo]):
                with lock:
                    w.writerow(fut.result())
                    n += 1
                    if n % 100 == 0:
                        f.flush()
                        print(f"  {n:,}/{len(todo):,}", flush=True)
    with open(outp, newline="", encoding="utf-8") as f:
        res = list(csv.DictReader(f))
    ok = sum(1 for r in res if r["body_text"] or r["title"])
    err = sum(1 for r in res if r["error"] and not r["body_text"])
    print(f"\nwrote {outp}: {len(res):,} rows | with page text {ok:,} | failed {err:,}")
    print("Attach this CSV back to the conversation.")


if __name__ == "__main__":
    main()
