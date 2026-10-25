#!/usr/bin/env python3
"""Fetch the correspondence sources (design section 4, R1 to R11) and write the manifest.

Usage (from the repo root):
    python training/sources/correspondence/fetch.py [--raw /tmp/raw/correspondence]
    python training/sources/correspondence/fetch.py --only R6 R7 R8 R9 R11

Raw files and extracted text go to --raw, which must be outside the repo: they
contain real people's data and are never committed. The script updates
data/sources/correspondence/manifest.json: sources fetched in this run get a new
entry (also when the fetch failed: fetched false, with the error); entries of
sources not in --only are kept as they are.

R1 to R5 are Enron messages. The CMU archive (1.7 GB) and the Hugging Face
mirrors were not reachable from the build sandbox, so the messages come from the
copy of the same corpus inside the HPI Quagga repository on GitHub, pinned to a
commit, with a blobless sparse clone (only the five message files are read).

R6 to R9 are single pages or files on ALLOWED_HOSTS. R11 is a committee
publication page on api.parliament.uk; the letters themselves are the files it
links to on committees.parliament.uk, fetched one by one (R11_<document id>.*).
R10 (sec.gov) is never fetched, by decision. Redirects to a host outside
ALLOWED_HOSTS are refused, and a bot-challenge page is reported as a failure,
never worked around.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "data" / "sources" / "correspondence" / "manifest.json"
UA = "night-shift-hackathon dataset build (github.com/BabyBoss45/night-shift)"
ENRON_URL = "https://www.cs.cmu.edu/~enron/"
ENRON_LICENCE = "Enron email corpus, research release of the FERC public record"
QUAGGA = "https://github.com/HPI-Information-Systems/Quagga"
QUAGGA_COMMIT = "4ba5be0fd4a0a5954527ea93cf6592f54f4fc3f0"
QUAGGA_DIR = "Datasets/Enron/annotated_all"
ENRON_FILES = {
    "R1": "train/shackleton-s_inbox_343.txt",
    "R2": "train/dasovich-j_interconnection_12.txt",
    "R3": "eval/heard-m_inbox_master_netting_185.txt",
    "R4": "train/hernandez-j_inbox_297.txt",
    "R5": "test/kaminski-v_all_documents_1882.txt",
}
WEB_SOURCES = {
    "R6": ("https://www.justice.gov.uk/courts/procedure-rules/civil/protocol/prot_hou",
           "Crown copyright, Open Government Licence", "template",
           "Housing disrepair pre-action protocol, annex letter templates"),
    "R7": ("https://ico.org.uk/media2/migrated/4028636/sar-complaint-letter-or-email-template-v10.docx",
           "Open Government Licence", "template", "ICO subject access request complaint template"),
    "R8": ("https://www.acas.org.uk/job-offer-templates/job-offer-letter-template-with-written-statement",
           "Open Government Licence", "template", "Acas job offer letter template"),
    "R9": ("https://www.acas.org.uk/disciplinary-outcome-letter-templates/"
           "notice-of-disciplinary-outcome-letter-template-dismissal-disciplinary-action-or-no-action",
           "Open Government Licence", "template", "Acas disciplinary outcome letter template"),
    "R10": ("https://www.sec.gov/Archives/edgar/data/858446/000095010309002490/filename1.htm",
            "Public filing, SEC EDGAR", "filled_real", "IHG letter to the SEC"),
    "R11": ("https://api.parliament.uk/committees/publications/7750",
            "Open Parliament Licence", "filled_real",
            "Parliament committee correspondence listing; letters to pick by hand"),
}
# Sources never fetched, with the reason (written to their manifest entries on every run).
BLOCKED = {"R10": "sec.gov is not used, by decision"}
ALLOWED_HOSTS = {"www.justice.gov.uk", "ico.org.uk", "www.acas.org.uk", "api.parliament.uk",
                 "committees.parliament.uk", "publications.parliament.uk"}
# Letter files linked from an R11 publication page.
R11_FILE_RE = re.compile(
    r'<a href="(https://committees\.parliament\.uk/publications/\d+/documents/(\d+)/default/)">([^<]*)</a>')
ALL_IDS = list(ENRON_FILES) + list(WEB_SOURCES)


class TextExtractor(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def kind_of(data, ctype=""):
    """File kind from the bytes (URLs such as .../default/ carry no extension)."""
    if data[:5] == b"%PDF-" or "pdf" in ctype:
        return "pdf"
    if data[:2] == b"PK" or "wordprocessingml" in ctype:
        return "docx"
    return "html"


def docx_text(data):
    """Paragraphs and table cells in document order (python-docx .paragraphs skips tables)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = docx.Document(io.BytesIO(data))
    out = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            out.append(Paragraph(child, doc).text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                seen = []
                for cell in row.cells:  # merged cells repeat; keep each once
                    if cell.text not in seen:
                        seen.append(cell.text)
                out.append(" | ".join(seen))
    return "\n".join(out).strip() + "\n"


def extract_text(data, kind):
    """Plain text from an HTML, DOCX or PDF download."""
    if kind == "docx":
        return docx_text(data)
    if kind == "pdf":
        import pypdf
        return "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(data)).pages)
    parser = TextExtractor()
    parser.feed(data.decode("utf-8", errors="replace"))
    lines = [ln.rstrip() for ln in "".join(parser.parts).splitlines()]
    out = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip() + "\n"


def sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class AllowedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def tls_context():
    """Verify certificates against certifi's CA bundle when installed: python.org builds
    on macOS ship without system CA certificates, so the default context fails there."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


OPENER = urllib.request.build_opener(AllowedRedirects, urllib.request.HTTPSHandler(context=tls_context()))


def check_host(url):
    host = urllib.parse.urlsplit(url).hostname
    if host not in ALLOWED_HOSTS:
        raise RuntimeError(f"host {host} is not in ALLOWED_HOSTS")


def get(url):
    """(bytes, content type) of url; a bot-challenge page raises instead of being returned."""
    check_host(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with OPENER.open(req, timeout=30) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read(4000)
        if b"Just a moment" in body or b"challenge-platform" in body or b"challenges.cloudflare" in body:
            raise RuntimeError(f"HTTP {exc.code} with a Cloudflare bot challenge (not bypassed)") from None
        raise


def fetch_enron(raw, ids):
    clone = raw / "quagga"
    if not (clone / ".git").exists():
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", QUAGGA, str(clone)],
                       check=True)
    subprocess.run(["git", "-C", str(clone), "sparse-checkout", "set", "--no-cone", QUAGGA_DIR + "/*"],
                   check=True)
    subprocess.run(["git", "-C", str(clone), "checkout", QUAGGA_COMMIT], check=True)
    entries = []
    for sid, rel in ENRON_FILES.items():
        if sid not in ids:
            continue
        text = (clone / QUAGGA_DIR / rel).read_text(encoding="latin-1").replace("\r", "")
        (raw / f"{sid}.txt").write_text(text, encoding="utf-8")
        entries.append({
            "source_id": sid, "url": ENRON_URL, "licence": ENRON_LICENCE, "kind": "filled_real",
            "fetched": True, "fetched_at": now(), "sha256": sha(text),
            "notes": f"Enron message from the copy in {QUAGGA} at commit {QUAGGA_COMMIT}, "
                     f"file {QUAGGA_DIR}/{rel}; sha256 is of the message text with CR removed",
        })
    return entries


def save(raw, name, data, kind):
    """Write the raw bytes and the extracted text; return the text."""
    ext = {"pdf": "pdf", "docx": "docx", "html": "html"}[kind]
    (raw / f"{name}.{ext}").write_bytes(data)
    text = extract_text(data, kind)
    (raw / f"{name}.txt").write_text(text, encoding="utf-8")
    return text


def fetch_r11_files(raw, listing_html):
    """Fetch every letter file linked from the R11 publication page.

    committees.parliament.uk answers scripts with a Cloudflare bot challenge. A letter
    saved by hand from a browser as <raw>/R11_<document id>.pdf is used instead of a
    download (and recorded as such in the manifest)."""
    files = []
    for url, doc_id, name in R11_FILE_RE.findall(listing_html):
        item = {"url": url, "name": name.strip(), "fetched": False, "sha256": None}
        by_hand = raw / f"R11_{doc_id}.pdf"
        try:
            if by_hand.exists():
                data, ctype = by_hand.read_bytes(), "application/pdf"
                item["saved_by_hand"] = True
            else:
                data, ctype = get(url)
            kind = kind_of(data, ctype)
            if kind != "pdf":
                raise RuntimeError(f"expected a PDF, got {ctype or 'unknown type'}")
            save(raw, f"R11_{doc_id}", data, kind)
            item.update(fetched=True, sha256=sha(data))
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        files.append(item)
    return files


def fetch_web(raw, ids):
    entries = []
    for sid, (url, licence, kind, what) in WEB_SOURCES.items():
        if sid not in ids:
            continue
        entry = {"source_id": sid, "url": url, "licence": licence, "kind": kind, "fetched": False,
                 "fetched_at": now(), "sha256": None, "notes": what}
        try:
            data, ctype = get(url)
            text = save(raw, sid, data, kind_of(data, ctype))
            entry["sha256"] = sha(text)
            entry["notes"] += "; sha256 is of the extracted text"
            if sid == "R11":
                entry["files"] = fetch_r11_files(raw, data.decode("utf-8", errors="replace"))
                got = [f for f in entry["files"] if f["fetched"]]
                entry["notes"] += ("; sha256 of each letter file is of the raw PDF" if got else
                                   "; the publication page was fetched but none of its letter files")
                entry["fetched"] = bool(got)
            else:
                entry["fetched"] = True
        except Exception as exc:  # record the failure and carry on with the other sources
            entry["notes"] += f"; NOT FETCHED: {type(exc).__name__}: {exc}"
        entries.append(entry)
    return entries


def merge_manifest(new_entries):
    old = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    by_id = {e["source_id"]: e for e in old}
    by_id.update({e["source_id"]: e for e in new_entries})
    order = {sid: i for i, sid in enumerate(ALL_IDS)}
    return sorted(by_id.values(), key=lambda e: order.get(e["source_id"], len(order)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="/tmp/raw/correspondence")
    ap.add_argument("--only", nargs="+", metavar="ID", choices=ALL_IDS,
                    help="fetch only these sources (default: all except BLOCKED)")
    args = ap.parse_args()
    raw = Path(args.raw).resolve()
    if ROOT in raw.parents or raw == ROOT:
        raise SystemExit("--raw must be outside the repository")
    ids = set(args.only or ALL_IDS) - set(BLOCKED)
    raw.mkdir(parents=True, exist_ok=True)
    entries = []
    for sid, why in BLOCKED.items():  # no request is made; the entry records the decision
        url, licence, kind, what = WEB_SOURCES[sid]
        entries.append({"source_id": sid, "url": url, "licence": licence, "kind": kind, "fetched": False,
                        "fetched_at": None, "sha256": None, "notes": f"{what}; NOT FETCHED: {why}"})
    if ids & set(ENRON_FILES):
        if not shutil.which("git"):
            raise SystemExit("git is required")
        entries += fetch_enron(raw, ids)
    entries += fetch_web(raw, ids)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(merge_manifest(entries), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for e in entries:
        print(e["source_id"], "fetched" if e["fetched"] else "NOT fetched", "" if e["fetched"] else e["notes"])
        for f in e.get("files", []):
            print("   ", f["name"], "fetched" if f["fetched"] else f"NOT fetched: {f.get('error')}")


if __name__ == "__main__":
    main()
