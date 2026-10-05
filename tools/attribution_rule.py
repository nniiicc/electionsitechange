"""The rule-based first screen used on 5 Oct (see tools/attribution_method.md)."""
import re
import pandas as pd

def surnames(names):
    out = set()
    for n in str(names).split(";"):
        toks = [t for t in re.sub(r"[^a-z\s\-']", " ", n.lower()).split() if t not in ("jr", "sr", "ii", "iii", "iv")]
        if toks: out.add(toks[-1])
    return out


def screen_current_or_none(r):
    """'current' when the rule alone settles it, else None (the site goes to the model)."""
    head = " ".join(str(r[c]) for c in ("snap_title", "snap_description", "snap_paid_for_by", "snap_final_url") if pd.notna(r[c])).lower()
    yrs = [int(y) for y in str(r["snap_years"]).split(";") if y.isdigit()]
    named = any(s and len(s) > 2 and s in head for s in surnames(r["names"]))
    if named and (not yrs or 2026 in yrs or max(yrs) >= 2025): return "current"
    return None
