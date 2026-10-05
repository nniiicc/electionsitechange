#!/usr/bin/env python3
"""Check reachability of 2026 candidate campaign URLs.

Run this on a machine with ordinary internet access (the research sandbox routes all
egress through a domain-allowlist proxy and has no DNS, so it cannot do this itself).

    pip install requests
    python check_urls.py national_verify_input.csv url_status.csv

Reads any CSV with a `url` column (extra columns are carried through untouched).
Writes one row per input URL with the HTTP result.

Resumable: if the output file already exists, URLs already recorded in it are skipped,
so you can interrupt with Ctrl-C and re-run the same command to continue.

Runtime: ~8,700 URLs at 24 threads finishes in roughly 10-15 minutes. Most of the wall
time is the slow tail of dead domains waiting out the timeout.
"""
import csv
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter

TIMEOUT = 10            # seconds per request
THREADS = 24
UA = "Mozilla/5.0 (compatible; campaign-link-checker/1.0)"

FIELDS = [
    "url", "status_code", "final_url", "redirected", "scheme_upgraded",
    "error_kind", "error_detail", "verdict",
]

_local = threading.local()


def session():
    """One requests.Session per worker thread, with connection pooling."""
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "*/*"})
        ad = HTTPAdapter(pool_connections=THREADS, pool_maxsize=THREADS, max_retries=0)
        s.mount("https://", ad)
        s.mount("http://", ad)
        _local.s = s
    return s


def normalize(u):
    u = (u or "").strip()
    if not u:
        return None
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    return u


def classify(status, err_kind):
    """Collapse the raw result into a verdict you can filter on."""
    if err_kind == "dns":
        return "dead_dns"                  # domain does not resolve - definitively gone
    if err_kind in ("timeout", "conn"):
        return "unreachable"               # resolves but nothing answered
    if err_kind == "ssl":
        return "ssl_error"                 # cert expired/mismatched - often an abandoned site
    if err_kind:
        return "error"
    if status is None:
        return "error"
    if 200 <= status < 300:
        return "ok"
    if 300 <= status < 400:
        return "redirect_unresolved"
    if status in (401, 403, 405, 406, 429):
        return "ok_blocked"                # server is alive but refused this request
    if status == 404:
        return "not_found"
    if 500 <= status < 600:
        return "server_error"
    return f"http_{status}"


def check(raw_url):
    """HEAD first (cheap); fall back to a ranged GET when HEAD is unsupported."""
    url = normalize(raw_url)
    row = dict.fromkeys(FIELDS, "")
    row["url"] = raw_url
    if not url:
        row.update(error_kind="empty", verdict="error")
        return row

    s = session()
    status = final = None
    err_kind = err_detail = ""

    for method in ("head", "get"):
        try:
            kwargs = dict(timeout=TIMEOUT, allow_redirects=True)
            if method == "get":
                # Ask for only the first bytes so we never download a whole page.
                kwargs["headers"] = {"Range": "bytes=0-2047"}
                kwargs["stream"] = True
            r = getattr(s, method)(url, **kwargs)
            status, final = r.status_code, r.url
            if method == "get":
                r.close()
            # Retry with GET only when HEAD is explicitly unsupported or suspiciously refused.
            if method == "head" and status in (400, 403, 405, 406, 501):
                continue
            err_kind = err_detail = ""
            break
        except requests.exceptions.SSLError as e:
            err_kind, err_detail = "ssl", str(e)[:160]
        except requests.exceptions.ConnectTimeout as e:
            err_kind, err_detail = "timeout", str(e)[:160]
        except requests.exceptions.ReadTimeout as e:
            err_kind, err_detail = "timeout", str(e)[:160]
        except requests.exceptions.ConnectionError as e:
            msg = str(e)
            # Distinguish "no such domain" from "domain exists but refused/unreachable".
            dns = any(k in msg for k in (
                "Name or service not known", "nodename nor servname",
                "getaddrinfo failed", "Temporary failure in name resolution",
                "Name does not resolve", "NameResolutionError",
            ))
            err_kind, err_detail = ("dns" if dns else "conn"), msg[:160]
        except requests.exceptions.RequestException as e:
            err_kind, err_detail = "request", str(e)[:160]
        except Exception as e:                      # noqa: BLE001 - never kill the pool
            err_kind, err_detail = type(e).__name__, str(e)[:160]

    row["status_code"] = "" if status is None else status
    row["final_url"] = final or ""
    row["redirected"] = "" if not final else str(final.rstrip("/") != url.rstrip("/")).lower()
    row["scheme_upgraded"] = str(bool(final and final.startswith("https://")
                                      and url.startswith("http://"))).lower()
    row["error_kind"] = err_kind
    row["error_detail"] = err_detail
    row["verdict"] = classify(status, err_kind)
    return row


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <input.csv> [output.csv]")
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else "url_status.csv"

    with open(inp, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or "url" not in rows[0]:
        sys.exit(f"{inp}: no 'url' column found")

    urls, seen = [], set()
    for r in rows:
        u = (r.get("url") or "").strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)

    done = set()
    if os.path.exists(outp):
        with open(outp, newline="", encoding="utf-8") as f:
            done = {r["url"] for r in csv.DictReader(f) if r.get("url")}
        print(f"resuming: {len(done):,} already checked in {outp}")

    todo = [u for u in urls if u not in done]
    print(f"{len(urls):,} unique URLs | {len(todo):,} to check | {THREADS} threads")
    if not todo:
        return

    write_header = not done
    n = 0
    lock = threading.Lock()
    with open(outp, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        with ThreadPoolExecutor(max_workers=THREADS) as ex:
            futs = {ex.submit(check, u): u for u in todo}
            for fut in as_completed(futs):
                row = fut.result()
                with lock:
                    w.writerow(row)
                    n += 1
                    if n % 250 == 0:
                        f.flush()
                        print(f"  {n:,}/{len(todo):,}", flush=True)

    # Summary straight off the file we just wrote, so the numbers match the artifact.
    with open(outp, newline="", encoding="utf-8") as f:
        res = list(csv.DictReader(f))
    tally = {}
    for r in res:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print(f"\nwrote {outp} ({len(res):,} rows)")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {k:22s} {v:6,}  ({100*v/len(res):.1f}%)")
    broken = sum(v for k, v in tally.items()
                 if k in ("dead_dns", "unreachable", "not_found", "error"))
    print(f"\nlikely broken: {broken:,} ({100*broken/len(res):.1f}%)")
    print("Send the output CSV back and it will be merged into the database as "
          "contact_links.reachability, replacing 'not_tested'.")


if __name__ == "__main__":
    main()
