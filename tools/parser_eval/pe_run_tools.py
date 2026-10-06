"""Parser evaluation, step 3a: run EDGI web-monitoring-diff, changedetection.io's HTML-to-text and the
image-and-embed list on every pair. Run with the evaluation venv (~/eval/venv).
For each method and pair, records whether a change was reported and the reported added/removed content.
Writes results_tools.jsonl.
"""
import json, re, signal, sys
from concurrent.futures import ProcessPoolExecutor
from html import unescape

CAP = 20000
TIMEOUT = 60


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def edgi_text(a, b):
    from web_monitoring_diff import html_text_diff
    r = html_text_diff(a, b)
    return {"detected": r["change_count"] > 0,
            "ins": "".join(t for op, t in r["diff"] if op == 1), "del": "".join(t for op, t in r["diff"] if op == -1)}


def edgi_links(a, b):
    from web_monitoring_diff import links_diff
    r = links_diff(a, b)
    cc = r["change_count"]["change_count"] if isinstance(r["change_count"], dict) else r["change_count"]
    ins = [json.dumps(x[1]) for x in r["diff"] if x[0] in (1, 100)]
    dele = [json.dumps(x[1]) for x in r["diff"] if x[0] in (-1, 100)]
    return {"detected": cc > 0, "ins": " ".join(ins), "del": " ".join(dele)}


TAGTXT = re.compile(r"<[^>]+>")


def edgi_render(a, b):
    from web_monitoring_diff import html_diff_render
    r = html_diff_render(a, b, include="combined")
    d = r.get("combined") or ""      # html_diff_render returns {"change_count", "combined"}
    def grab(tag):
        parts = re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", d, re.S | re.I)
        return " ".join(unescape(TAGTXT.sub(" ", p)) + " " + " ".join(re.findall(r'(?:src|alt)="([^"]*)"', p)) for p in parts)
    return {"detected": r["change_count"] > 0, "ins": grab("ins"), "del": grab("del")}


def cdio(a, b):
    from changedetectionio.html_tools import html_to_text
    ta, tb = html_to_text(a), html_to_text(b)
    ws = lambda t: re.sub(r"\s", "", t)            # application default: ignore_whitespace = True
    ins, dele = line_diff(ta, tb)
    return {"detected": ws(ta) != ws(tb), "ins": ins, "del": dele}


def line_diff(ta, tb):
    """added and removed lines in sequence order (a line repeated elsewhere on the page still counts)"""
    import difflib
    la = [l.strip() for l in ta.splitlines() if l.strip()]
    lb = [l.strip() for l in tb.splitlines() if l.strip()]
    d = list(difflib.ndiff(la, lb))
    return "\n".join(x[2:] for x in d if x[:2] == "+ "), "\n".join(x[2:] for x in d if x[:2] == "- ")


def media(a, b):
    sys.path.insert(0, ".")
    from pe_imglist import media_list
    ma, mb = media_list(a), media_list(b)
    return {"detected": ma != mb, "ins": "\n".join(sorted(mb - ma)), "del": "\n".join(sorted(ma - mb))}


METHODS = {"edgi_text": edgi_text, "edgi_links": edgi_links, "edgi_render": edgi_render, "cdio": cdio, "media": media}


def run(pair_id):
    a = open(f"pairs/{pair_id}/a.html").read(); b = open(f"pairs/{pair_id}/b.html").read()
    out = {"pair_id": pair_id}
    signal.signal(signal.SIGALRM, _alarm)
    for name, fn in METHODS.items():
        signal.alarm(TIMEOUT)
        try:
            r = fn(a, b)
            out[name] = {"detected": bool(r["detected"]), "ins": r["ins"][:CAP], "del": r["del"][:CAP]}
        except Timeout:
            out[name] = {"error": "timeout"}
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"[:300]}
        finally:
            signal.alarm(0)
    return out


if __name__ == "__main__":
    # optional: pe_run_tools.py METHOD[,METHOD] TYPE[,TYPE] OUTFILE  -> rerun some methods on some pair types
    if len(sys.argv) > 3:
        METHODS = {k: METHODS[k] for k in sys.argv[1].split(",")}
        types = set(sys.argv[2].split(","))
        ids = [json.loads(l)["pair_id"] for l in open("pairs.jsonl") if json.loads(l)["type"] in types]
        outfile = sys.argv[3]
    else:
        ids = [json.loads(l)["pair_id"] for l in open("pairs.jsonl")]
        outfile = "results_tools.jsonl"
    with ProcessPoolExecutor(2) as ex, open(outfile, "w") as f:
        for i, r in enumerate(ex.map(run, ids, chunksize=4), 1):
            f.write(json.dumps(r) + "\n")
            if i % 250 == 0:
                print(f"{i}/{len(ids)}", flush=True)
    print("done", len(ids))
