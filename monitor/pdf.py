"""PDFs on a candidate's own site (issue #7): text extracted with poppler's pdftotext and stored like a page.

page(raw, final_url) returns the same dict shape as detect.page, so snapshot.py writes, fingerprints and
compares a PDF exactly like an HTML page (text.md one sentence per line; links and media empty). A PDF
with pages but no text layer (a scan) is recorded with "scanned": true; its fingerprint uses the file's
bytes, since there is no text to compare.
"""
import hashlib, json, os, re, shutil, subprocess, tempfile, threading

import detect

PDFTOTEXT, PDFINFO = shutil.which("pdftotext"), shutil.which("pdfinfo")
TIMEOUT_S = 60
SLOTS = threading.BoundedSemaphore(2)
SCANNED_MAX_CHARS = 20          # fewer extracted characters than this on a PDF with pages = no text layer


class PdfFailed(Exception):
    pass


def is_pdf(content_type, raw):
    return "pdf" in (content_type or "").lower() or raw[:5] == b"%PDF-"


def _run(args):
    try:
        r = subprocess.run(args, capture_output=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise PdfFailed("pdf_timeout")
    if r.returncode != 0:
        raise PdfFailed("pdf_failed")
    return r.stdout.decode("utf-8", errors="replace")


def page(raw, final_url):
    if not (PDFTOTEXT and PDFINFO):
        raise PdfFailed("pdf_tools_missing")
    with SLOTS, tempfile.TemporaryDirectory(prefix="pdf-") as d:
        path = os.path.join(d, "doc.pdf")
        with open(path, "wb") as f:
            f.write(raw)
        text = detect.collapse(_run([PDFTOTEXT, "-q", "-enc", "UTF-8", "-nopgbrk", path, "-"]))
        try:
            info = _run([PDFINFO, path]) if PDFINFO else ""
        except PdfFailed:
            info = ""                            # metadata only; the extracted text still counts
    n_pages = int(m.group(1)) if (m := re.search(r"^Pages:\s+(\d+)", info, re.M)) else 0
    title = m.group(1).strip() if (m := re.search(r"^Title:\s+(.*)$", info, re.M)) else ""
    # no text layer: pdfinfo found pages, or (without page info) the file is non-trivial but yields no text
    scanned = len(text) < SCANNED_MAX_CHARS and (n_pages > 0 or len(raw) > 1000)
    content = {"text": text, "links": [], "media": [], "title": title, "description": "",
               **({"bytes_sha1": hashlib.sha1(raw).hexdigest()} if scanned else {})}
    fp = hashlib.sha1(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    m = detect.PAID_FOR.search(text)
    return {"text": text, "lines": detect.as_lines(text), "links": [], "media": [],
            "meta": {"format": detect.FORMAT, "final_url": final_url, "title": title, "description": "",
                     "paid_for_by": detect.collapse(m.group(0)).rstrip(" .") if m else "",
                     "years_mentioned": sorted(set(detect.YEARS.findall(text))),
                     "pdf": True, "pages": n_pages, "scanned": scanned, "fingerprint": fp},
            "hrefs": []}
