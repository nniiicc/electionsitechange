"""Change records (issue #9): what changed on each page that was added, removed or changed today.

The decision *whether* a page changed is made by detect.py when the snapshot is written (its fingerprint);
a page's files are only rewritten when it changed, so the day's Git diff lists exactly the changed pages.
This module turns that diff into one record per page:

  * text: sentences removed and added. Sentences are compared as a multiset, so reordered text is not an edit;
  * links: outbound links removed and added (text and target), with donation-platform links flagged;
  * media: images, alt texts and embeds removed and added;
  * meta: title, description, "Paid for by" text and years mentioned, before and after;
  * wayback: before/after archive links, filled in by the Archiver (#8) when it exists;
  * the labelling fields of the spec's change record (step 0 to review), empty until #10-#12 fill them.

A page rewritten only because the snapshot format changed is not a change and gets no record.
An edit repeated on 3 or more changed pages of one site (a menu, footer or "recent posts" sidebar) is
recorded once, in the site's site-wide record (page "*", kind "sitewide"), with the pages each item changed on.

Used by snapshot.py before each day's commit (working tree against HEAD), and from the command line for
any two commits:  python changes.py REPO --from REV --to REV --day YYYY-MM-DD --urls monitor_urls.csv
"""
import argparse, csv, hashlib, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect import FORMAT  # noqa: E402  (snapshot format; pages stored in an older one are not compared)
from collections import Counter

HOME = "/"                         # page name of a site's homepage, as in the run log
FILES = ("text.md", "links.json", "media.json", "meta.json")
META_FIELDS = ("title", "description", "paid_for_by", "years_mentioned")
DONATION_HOSTS = re.compile(r"(^|\.)(actblue\.com|winred\.com|anedot\.com|donorbox\.org|ngpvan\.com|secure\.ngpvan\.com|"
                            r"givebutter\.com|efundraising\.com|revv\.co|numero\.ai|crowdpac\.com|donate\.stripe\.com|"
                            r"paypal\.com|venmo\.com|square\.link|campaignpartner\.com|politicalpartner\.com|"
                            r"secure\.anedot\.com|actionnetwork\.org)$", re.I)
PAGE_DIR = re.compile(r"^sites/([^/]+)(?:/pages/([^/]+))?/(?:text\.md|links\.json|media\.json|meta\.json)$")


def host(u):
    m = re.match(r"^[a-z]+://([^/?#]+)", u or "", re.I)
    return m.group(1).lower().removeprefix("www.") if m else ""


def multiset_diff(old, new):
    """lines removed and added, compared as a multiset (order ignored), each listed in page order"""
    def excess(xs, other):
        left = Counter(other); out = []
        for x in xs:
            if left[x] > 0:
                left[x] -= 1
            else:
                out.append(x)
        return out
    return excess(old, new), excess(new, old)


def parse_files(files):
    """files: {name: str or None} as stored -> {lines, links, media, meta}, or None if the page doesn't exist"""
    if not files.get("meta.json"):
        return None
    load = lambda k, d: json.loads(files[k]) if files.get(k) else d
    meta = load("meta.json", {})
    if meta.get("format") != FORMAT:
        return {"lines": [], "links": [], "media": [], "meta": meta}    # older format: only compared by format
    return {"lines": [l for l in (files.get("text.md") or "").splitlines() if l.strip()],
            "links": [(l["text"], l["href"]) for l in load("links.json", [])],
            "media": list(load("media.json", [])), "meta": meta}


def from_page(pg):
    """detect.page() output -> the same shape as parse_files (used by tests and the corpus check)"""
    return {"lines": list(pg["lines"]), "links": [(l["text"], l["href"]) for l in pg["links"]],
            "media": list(pg["media"]), "meta": dict(pg["meta"])}


def diff_pages(old, new):
    """old/new: parse_files() results or None. Returns the content part of a change record, or None when
    there is nothing to record (unchanged, or only rewritten in a new snapshot format)."""
    if old is None and new is None:
        return None
    if any(p and p["meta"].get("format") != FORMAT for p in (old, new)):
        return None                                   # an older snapshot format: rewritten, not compared
    o = old or {"lines": [], "links": [], "media": [], "meta": {}}
    n = new or {"lines": [], "links": [], "media": [], "meta": {}}
    t_rem, t_add = multiset_diff(o["lines"], n["lines"])
    l_rem, l_add = (sorted(set(o["links"]) - set(n["links"])), sorted(set(n["links"]) - set(o["links"])))
    m_rem, m_add = sorted(set(o["media"]) - set(n["media"])), sorted(set(n["media"]) - set(o["media"]))
    meta = {k: {"before": o["meta"].get(k), "after": n["meta"].get(k)}
            for k in META_FIELDS if o["meta"].get(k) != n["meta"].get(k)}
    kind = "added" if old is None else "removed" if new is None else "changed"
    if kind == "changed" and not (t_rem or t_add or l_rem or l_add or m_rem or m_add or meta):
        return None
    lk = lambda xs: [{"text": t, "href": h} for t, h in xs]
    don = sorted({h for _, h in l_rem + l_add if DONATION_HOSTS.search(host(h))})
    return {"kind": kind,
            "url": n["meta"].get("final_url") or o["meta"].get("final_url") or "",
            "text": {"removed": t_rem, "added": t_add},
            "links": {"removed": lk(l_rem), "added": lk(l_add), "donation_links_changed": don},
            "media": {"removed": m_rem, "added": m_add},
            "meta": meta}


SITEWIDE_MIN_PAGES = 3          # the same edit on this many pages of a site is one site-wide change
SITEWIDE = "*"                  # page name of a site-wide record


def _items(c):
    """the individual changed items of a record's content, as hashable keys"""
    out = set()
    for k in ("text", "media"):
        for side in ("removed", "added"):
            out.update((k, side, x) for x in c[k][side])
    for side in ("removed", "added"):
        out.update(("links", side, (l["text"], l["href"])) for l in c["links"][side])
    out.update(("meta", f, json.dumps(v, sort_keys=True)) for f, v in c["meta"].items())
    return out


def _empty(kind, url=""):
    return {"kind": kind, "url": url, "text": {"removed": [], "added": []},
            "links": {"removed": [], "added": [], "donation_links_changed": []}, "media": {"removed": [], "added": []}, "meta": {}}


def _donations(c):
    return sorted({l["href"] for l in c["links"]["removed"] + c["links"]["added"] if DONATION_HOSTS.search(host(l["href"]))})


def group_sitewide(contents):
    """contents: {(site_id, page): content}. Items changed identically on the same SITEWIDE_MIN_PAGES or more
    changed pages of one site (an edited menu or footer, a new post in a sidebar) move into ONE site-wide content
    per site, keyed (site_id, "*"). It lists all pages involved, and "item_pages" gives the pages for each item.
    The items are removed from those pages' contents, and a page left with nothing is dropped. Added and removed
    pages are not folded."""
    out, by_site = {}, {}
    for (sid, page), c in contents.items():
        (by_site.setdefault(sid, {}) if c["kind"] == "changed" else out)[(sid, page)] = c
    for sid, pages in by_site.items():
        where = {}                                    # item -> pages it changed on
        for (_, pg), c in pages.items():
            for it in _items(c):
                where.setdefault(it, set()).add(pg)
        groups = {}                                   # frozenset(pages) -> items changed on exactly those pages
        for it, pgs in where.items():
            if len(pgs) >= SITEWIDE_MIN_PAGES:
                groups.setdefault(frozenset(pgs), set()).add(it)
        if not groups:
            out.update(pages); continue
        common = set().union(*groups.values())
        home_url = next((c["url"] for (_, pg), c in pages.items() if pg == HOME), "") or \
            next((c["url"] for c in pages.values() if c["url"]), "")
        # one site-wide record per site; "item_pages" says which pages each item changed on, so unrelated
        # edits on different pages are not attributed to each other
        sw = _empty("sitewide", home_url)
        sw["pages"] = sorted(set().union(*groups))
        sw["item_pages"] = []
        for pgs in sorted(groups, key=lambda g: (-len(g), sorted(g))):
            first = pages[(sid, sorted(pgs)[0])]          # item order as on the first page
            for k in ("text", "media"):
                for side in ("removed", "added"):
                    for x in dict.fromkeys(x for x in first[k][side] if (k, side, x) in groups[pgs]):
                        sw[k][side].append(x); sw["item_pages"].append({"field": k, "side": side, "value": x, "pages": sorted(pgs)})
            for side in ("removed", "added"):
                for l in first["links"][side]:
                    if ("links", side, (l["text"], l["href"])) in groups[pgs]:
                        sw["links"][side].append(l); sw["item_pages"].append({"field": "links", "side": side, "value": l, "pages": sorted(pgs)})
            for f, v in first["meta"].items():
                if ("meta", f, json.dumps(v, sort_keys=True)) in groups[pgs]:
                    sw["meta"][f] = v; sw["item_pages"].append({"field": "meta", "name": f, "value": v, "pages": sorted(pgs)})
        sw["links"]["donation_links_changed"] = _donations(sw)
        out[(sid, SITEWIDE)] = sw
        for (_, pg), c in pages.items():
            for k in ("text", "media"):
                for side in ("removed", "added"):
                    c[k][side] = [x for x in c[k][side] if (k, side, x) not in common]
            for side in ("removed", "added"):
                c["links"][side] = [l for l in c["links"][side] if ("links", side, (l["text"], l["href"])) not in common]
            c["meta"] = {f: v for f, v in c["meta"].items() if ("meta", f, json.dumps(v, sort_keys=True)) not in common}
            c["links"]["donation_links_changed"] = _donations(c)
            if any(c[k]["removed"] or c[k]["added"] for k in ("text", "links", "media")) or c["meta"]:
                out[(sid, pg)] = c
    return out


def record(day, site_id, page, content, site_info):
    """full change record (spec: Data contracts)"""
    rid = hashlib.sha1(f"{day}|{site_id}|{page}".encode()).hexdigest()[:12]
    info = site_info.get(site_id, {})
    return {"change_id": rid, "date": day, "site_id": site_id, "page": page,
            "candidate_uids": info.get("candidate_uids", ""), "names": info.get("names", ""),
            "office_tier": info.get("office_tier", ""), "state": info.get("state", ""),
            **content,
            "wayback": {"before": None, "after": None},
            "step0": None, "step1": None, "step2": None,
            "review": {"status": "unreviewed", "reviewer": None, "decided_at": None, "correction": None}}


# ------------------------------------------------------------------ reading the Git repository
def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, *args], check=check, capture_output=True, text=True)


def changed_page_dirs(repo, rev_from, rev_to=None, cached=False):
    """page directories (site_id, page) touched between two commits, or between HEAD and the index"""
    args = ["diff", "--name-only", "--no-renames"]
    args += ["--cached", rev_from] if cached else [rev_from, rev_to]
    out = git(repo, *args, "--", "sites").stdout.splitlines()
    pages = set()
    for p in out:
        m = PAGE_DIR.match(p)
        if m:
            pages.add((m.group(1), m.group(2) or HOME))
    return sorted(pages)


def page_path(site_id, page):
    return f"sites/{site_id}" if page == HOME else f"sites/{site_id}/pages/{page}"


def files_at(repo, rev, site_id, page):
    """file contents at a revision; rev ':' means the index (what is about to be committed)"""
    out = {}
    for f in FILES:
        spec = f"{rev}{page_path(site_id, page)}/{f}" if rev == ":" else f"{rev}:{page_path(site_id, page)}/{f}"
        r = git(repo, "show", spec, check=False)
        out[f] = r.stdout if r.returncode == 0 else None
    return out


def records_between(repo, day, site_info, rev_from, rev_to=None):
    """rev_to=None compares HEAD with the index (call after 'git add -A', before committing)"""
    cached = rev_to is None
    contents, n_reformatted = {}, 0
    for site_id, page in changed_page_dirs(repo, rev_from, rev_to, cached=cached):
        old = parse_files(files_at(repo, rev_from, site_id, page))
        new = parse_files(files_at(repo, ":" if cached else rev_to, site_id, page))
        c = diff_pages(old, new)
        if c is None:
            n_reformatted += bool(old and new and old["meta"].get("format") != new["meta"].get("format"))
            continue
        contents[(site_id, page)] = c
    grouped = group_sitewide(contents)
    return [record(day, sid, pg, c, site_info) for (sid, pg), c in sorted(grouped.items())], n_reformatted


def site_info_from(urls_csv):
    if not urls_csv or not os.path.exists(urls_csv):
        return {}
    return {r["site_id"]: r for r in csv.DictReader(open(urls_csv, newline=""))}


def write_records(repo, day, recs):
    os.makedirs(os.path.join(repo, "changes"), exist_ok=True)
    path = os.path.join(repo, "changes", f"{day}.jsonl")
    with open(path, "w") as f:
        for r in sorted(recs, key=lambda r: (r["site_id"], r["page"])):
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo"); ap.add_argument("--from", dest="rev_from", required=True)
    ap.add_argument("--to", dest="rev_to", required=True); ap.add_argument("--day", required=True)
    ap.add_argument("--urls"); ap.add_argument("--out", help="write here instead of REPO/changes/DAY.jsonl")
    a = ap.parse_args()
    recs, n_ref = records_between(a.repo, a.day, site_info_from(a.urls), a.rev_from, a.rev_to)
    import step0                                      # same step-0 rules as the daily run
    rules = step0.load_site_rules(os.path.join(os.path.dirname(os.path.abspath(a.urls)), "site_noise.csv") if a.urls else None)
    for r in recs:
        step0.apply(r, rules)
    if a.out:
        with open(a.out, "w") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    else:
        write_records(a.repo, a.day, recs)
    print(json.dumps({"records": len(recs), "reformatted_skipped": n_ref,
                      "by_kind": dict(Counter(r["kind"] for r in recs)),
                      "kept_after_step0": sum(1 for r in recs if not r["step0"]["discard"]),
                      "step0_reasons": dict(Counter(x for r in recs for x in r["step0"]["reasons"]))}))


if __name__ == "__main__":
    main()
