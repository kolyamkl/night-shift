"""Fetch contract sources C1 to C12 and extract plain text.

Raw downloads and extracted text stay OUTSIDE the repo (default /tmp/raw/contracts),
because filed sources contain real people's data. Only the manifest is written
into the repo: data/sources/contracts/manifest.json.

Usage: python training/sources/contracts/fetch.py [--raw-dir /tmp/raw/contracts] [--only C8,C9]

Each source is fetched from its `fetch` list when given, otherwise from `url`.
Publication pages (gov.uk, gov.wales, National Archives, Acas) link to the document
as an attachment: the best attachment is downloaded and extracted (the source's
`attachment_ext` order when given, otherwise DOCX, then ODT, then PDF); a page
without attachments is extracted as HTML.

Every request, including each redirect hop, must stay on a host named by the
source itself (its `url` and `fetch` list) or on the gov.uk asset host; anything
else is refused, so a redirect cannot pull the build onto another site.

Extraction keeps one paragraph per block, separated by blank lines:
- PDF: lines are re-flowed into paragraphs from the page layout (vertical gaps,
  font changes, whether a line ran to the right margin); page numbers and
  running headers are dropped; superscript footnote numbers become "[n]".
- DOCX: paragraphs and tables in document order, with list numbers and bullets
  rebuilt from numbering.xml.
- ODT: headings, paragraphs, lists, tables and text boxes in document order,
  with spaces, tabs and line breaks kept (list numbers are not rebuilt).
"""

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import SOURCES  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "data" / "sources" / "contracts" / "manifest.json"
UA = "night-shift-hackathon dataset build (github.com/BabyBoss45/night-shift)"
DOC_EXT = (".docx", ".odt", ".pdf")
# gov.uk publication pages serve their attachments from this host.
ATTACHMENT_HOSTS = {"assets.publishing.service.gov.uk"}


def allowed_hosts(src):
    urls = [src["url"]] + list(src.get("fetch") or [])
    return {urlparse(u).hostname for u in urls} | ATTACHMENT_HOSTS


def get(url, allowed):
    """GET with redirects followed by hand, refusing any host outside `allowed`."""
    for _ in range(10):
        host = urlparse(url).hostname
        if host not in allowed:
            raise ValueError(f"refused {host}: not an approved host for this source")
        r = requests.get(url, headers={"User-Agent": UA}, timeout=120, allow_redirects=False)
        if r.is_redirect:
            url = urljoin(url, r.headers["location"])
            continue
        r.raise_for_status()
        return r, url
    raise ValueError(f"too many redirects from {url}")


def tidy(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("­", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def md_to_text(md):
    out = []
    for ln in md.split("\n"):
        ln = re.sub(r"</?(label|span)[^>]*>", "", ln)
        ln = ln.replace("**", "")
        ln = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", ln)
        ln = re.sub(r"^#+\s*", "", ln)
        ln = re.sub(r"^- (\[[ x]\])\s+", r"\1 ", ln)
        if ln.startswith("|"):
            if re.fullmatch(r"[|:\- ]+", ln):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            ln = " | ".join(cells)
        out.append(ln)
    return tidy("\n".join(out))


def html_to_text(raw):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    for br in root.find_all("br"):
        br.replace_with("\n")
    blocks = []
    for el in root.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li", "tr", "pre", "div"]):
        if el.name == "div" and el.find(["p", "div", "table", "li", "h1", "h2", "h3"]):
            continue
        if el.name in ("p", "li") and el.find_parent(["li", "tr"]) is not None:
            continue
        if el.name == "tr":
            txt = " | ".join(c.get_text(" ", strip=True) for c in el.find_all(["td", "th"]))
        else:
            txt = el.get_text(" ", strip=el.name != "pre")
        if txt.strip():
            blocks.append(txt)
    return tidy("\n\n".join(blocks) if blocks else root.get_text("\n"))


# ----------------------------------------------------------------------- PDF
# A line that starts a list item stays on its own line, even after a full-width line.
LIST_START = re.compile(r"^(?:[•●▪◦\-–]\s|\[ ?[xX]? ?\]|\(?[a-z]{1,4}\)\s|\(\d{1,2}\)\s|\d{1,2}(?:\.\d{1,2})*[.)]\s"
                        r"|\d{1,2}\.\d{1,2}\s|[A-Z]\.\s)")


def _pdf_line_text(ln):
    """Line text with superscript footnote numbers written as "[n]"."""
    text, chars = ln["text"], [c for c in ln["chars"] if c["text"] != " "]
    if not chars:
        return text
    size = collections.Counter(round(c["size"], 1) for c in chars).most_common(1)[0][0]
    small = [c["size"] < 0.8 * size and c["bottom"] < ln["bottom"] - 1 for c in chars]
    if not any(small):
        return text
    out, i = [], 0
    marks = []  # per output char: True if superscript
    for c, sup in zip(chars, small):
        while i < len(text) and text[i] == " " and c["text"] != " ":
            out.append(" ")
            marks.append(False)
            i += 1
        if i >= len(text) or not text.startswith(c["text"], i):
            return text  # could not align chars with the text; leave the line as it is
        out.append(c["text"])
        marks.append(sup)
        i += len(c["text"])
    res, j = [], 0
    while j < len(out):
        if marks[j]:
            k = j
            while k < len(out) and marks[k]:
                k += 1
            run = "".join(out[j:k])
            digits = run.strip("() ")
            res.append(f"[{digits}]" if digits.isdigit() else run)
            j = k
        else:
            res.append(out[j])
            j += 1
    return "".join(res)


def pdf_to_text(data):
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [(p.height, p.extract_text_lines(strip=True, return_chars=True)) for p in pdf.pages]
    # Running headers: the same text in the top band of three or more pages.
    tops = collections.Counter(ln["text"] for h, lines in pages for ln in lines if ln["top"] < 0.08 * h)
    running = {t for t, n in tops.items() if n >= 3}

    def size_of(ln):
        cs = [c for c in ln["chars"] if c["text"] != " "]
        return collections.Counter(round(c["size"]) for c in cs).most_common(1)[0][0] if cs else 0

    body_size = collections.Counter(round(c["size"]) for h, lines in pages for ln in lines
                                    for c in ln["chars"] if c["text"] != " ").most_common(1)[0][0]

    def first_word_width(ln):
        cs = ln["chars"]
        end = next((c for c in cs[1:] if c["text"] == " "), None)
        stop = [c for c in cs if end is None or c["x0"] < end["x0"]]
        return (stop[-1]["x1"] - cs[0]["x0"]) if stop else 0

    def flow(lines, paras, right, footnotes=False, next_line=None):
        """Append the lines to paras, starting a new paragraph at gaps and font changes."""
        left = min(ln["x0"] for ln in lines)
        for i, ln in enumerate(lines):
            text, size = _pdf_line_text(ln), size_of(ln)
            if footnotes:
                join = bool(paras) and i > 0 and not (re.match(r"\d{1,3}\s", text) and ln["x0"] <= left + 1)
            elif i == 0:
                last = paras[-1] if paras else None
                join = (last is not None and last["size"] == size and last["wrapped"]
                        and not re.search(r"[.:;!?]$", last["text"]))
            else:
                prev = lines[i - 1]
                gap = ln["top"] - prev["bottom"]
                height = min(ln["bottom"] - ln["top"], prev["bottom"] - prev["top"])
                join = gap <= 0.45 * height and size == paras[-1]["size"]
            if not join:
                paras.append({"text": text, "size": size})
            else:
                cur = paras[-1]
                if footnotes or (cur["wrapped"] and not LIST_START.match(text)):
                    sep = "" if re.search(r"\w-$", cur["text"]) else " "
                else:
                    sep = "\n"
                cur["text"] += sep + text
            # Did this line run to the right margin, so that the next line continues it?
            # (the last line of a page is compared with the first word of the next page)
            nxt = lines[i + 1] if i + 1 < len(lines) else next_line
            nxt_w = first_word_width(nxt) if nxt else 0
            paras[-1]["wrapped"] = ln["x1"] + 4 + nxt_w > right - 6

    split = []  # per page: (body lines, footnote lines)
    for h, lines in pages:
        body = [ln for ln in lines
                if not (ln["top"] < 0.08 * h and ln["text"] in running)
                and not (ln["top"] > 0.85 * h and re.fullmatch(r"\d{1,3}", ln["text"]))]
        # Footnotes: the run of small-type lines at the bottom of the page.
        k = len(body)
        while k > 0 and size_of(body[k - 1]) <= 0.8 * body_size and body[k - 1]["top"] > 0.6 * h:
            k -= 1
        split.append((body[:k], body[k:]))
    paras, pending = [], []  # pending: footnotes of the last page, emitted after its last paragraph
    for n, (body, notes) in enumerate(split):
        if not body and not notes:
            continue
        right = max(ln["x1"] for ln in (body or notes))
        if body:
            nxt = next((b[0] for b, _ in split[n + 1:] if b), None)
            n_before = len(paras)
            flow(body, paras, right, next_line=nxt)
            # The previous page's footnotes go after the paragraph that page ended with,
            # which this page's first line may have continued.
            paras[n_before:n_before] = pending
            pending = []
        if notes:
            fn = []
            flow(notes, fn, right, footnotes=True)
            pending += fn
    paras += pending
    return tidy("\n\n".join(p["text"] for p in paras))


# ---------------------------------------------------------------------- DOCX
def _roman(n):
    out = ""
    for v, s in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                 (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= v:
            out, n = out + s, n - v
    return out


def _fmt_num(n, fmt):
    if fmt == "decimal":
        return str(n)
    if fmt == "lowerLetter":
        return chr(ord("a") + (n - 1) % 26)
    if fmt == "upperLetter":
        return chr(ord("A") + (n - 1) % 26)
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    return str(n)


class _DocxNumbering:
    """List labels from numbering.xml. Counters are kept per abstract list, as Word does,
    and restarted by a num's startOverride on its first use."""

    def __init__(self, doc):
        from docx.oxml.ns import qn

        self.qn = qn
        self.levels, self.num_abs, self.overrides = {}, {}, {}
        self.counters, self.started = {}, set()
        try:
            root = doc.part.numbering_part.element
        except (KeyError, NotImplementedError, AttributeError):
            return
        for an in root.findall(qn("w:abstractNum")):
            aid = an.get(qn("w:abstractNumId"))
            for lvl in an.findall(qn("w:lvl")):
                self.levels[(aid, int(lvl.get(qn("w:ilvl"))))] = self._level(lvl)
        for num in root.findall(qn("w:num")):
            nid = num.get(qn("w:numId"))
            self.num_abs[nid] = num.find(qn("w:abstractNumId")).get(qn("w:val"))
            for ov in num.findall(qn("w:lvlOverride")):
                so = ov.find(qn("w:startOverride"))
                if so is not None:
                    self.overrides[(nid, int(ov.get(qn("w:ilvl"))))] = int(so.get(qn("w:val")))

    def _level(self, lvl):
        qn = self.qn

        def val(tag, default):
            el = lvl.find(qn(tag))
            return el.get(qn("w:val")) if el is not None else default

        return {"start": int(val("w:start", "1")), "fmt": val("w:numFmt", "decimal"),
                "text": val("w:lvlText", "")}

    def label(self, numid, ilvl):
        aid = self.num_abs.get(numid)
        if aid is None or numid == "0":
            return ""
        lv = self.levels.get((aid, ilvl))
        if lv is None:
            return ""
        cnt = self.counters.setdefault(aid, {})
        if (numid, ilvl) in self.overrides and (numid, ilvl) not in self.started:
            cnt[ilvl] = self.overrides[(numid, ilvl)] - 1
        self.started.add((numid, ilvl))
        cnt[ilvl] = cnt.get(ilvl, lv["start"] - 1) + 1
        for deeper in [k for k in cnt if k > ilvl]:
            del cnt[deeper]
        if lv["fmt"] == "bullet":
            return "•"
        if lv["fmt"] == "none":
            return lv["text"]

        def sub(m):
            k = int(m.group(1)) - 1
            lk = self.levels.get((aid, k), {"fmt": "decimal", "start": 1})
            return _fmt_num(cnt.get(k, lk["start"]), lk["fmt"])

        return re.sub(r"%(\d)", sub, lv["text"])


def docx_to_text(data):
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(data))
    qn = docx.oxml.ns.qn
    numbering = _DocxNumbering(d)

    def num_props(p):
        for ppr in (p._p.pPr, getattr(p.style.element, "pPr", None) if p.style is not None else None):
            if ppr is not None and ppr.numPr is not None:
                nid = ppr.numPr.numId.val if ppr.numPr.numId is not None else None
                ilvl = ppr.numPr.ilvl.val if ppr.numPr.ilvl is not None else 0
                if nid is not None:
                    return str(nid), int(ilvl)
        return None

    def para_text(p):
        props = num_props(p)
        label = numbering.label(*props) if props else ""
        text = p.text
        return f"{label} {text}" if label and text.strip() else text

    parts = []
    for child in d.element.body.iterchildren():
        if child.tag == qn("w:p"):
            parts.append(para_text(Paragraph(child, d)))
        elif child.tag == qn("w:tbl"):
            for row in Table(child, d).rows:
                cells, seen = [], set()
                for c in row.cells:
                    if id(c._tc) in seen:
                        continue  # a merged cell is returned once per grid column
                    seen.add(id(c._tc))
                    cells.append(" ".join(para_text(p) for p in c.paragraphs).strip())
                parts.append(" | ".join(cells))
    return tidy("\n\n".join(parts))


# ----------------------------------------------------------------------- ODT
def odt_to_text(data):
    from lxml import etree

    xml = zipfile.ZipFile(io.BytesIO(data)).read("content.xml")
    T = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    TB = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    D = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"
    O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    root = etree.fromstring(xml)
    body = root.find(f"{O}body/{O}text")
    blocks = []

    def inline(el, out, frames):
        if el.text:
            out.append(el.text)
        for ch in el:
            tag = ch.tag
            if tag == f"{T}s":
                out.append(" " * int(ch.get(f"{T}c", "1")))
            elif tag == f"{T}tab":
                out.append("\t")
            elif tag == f"{T}line-break":
                out.append("\n")
            elif tag in (f"{T}note", f"{T}tracked-changes"):
                pass
            elif tag == f"{D}frame":
                frames.append(ch)  # text boxes are emitted as blocks after this paragraph
            elif tag in (f"{T}bookmark-start", f"{T}bookmark-end", f"{T}bookmark", f"{T}soft-page-break"):
                pass
            else:
                inline(ch, out, frames)
            if ch.tail:
                out.append(ch.tail)

    def walk(el):
        for ch in el:
            tag = ch.tag
            if tag in (f"{T}p", f"{T}h"):
                out, frames = [], []
                inline(ch, out, frames)
                blocks.append("".join(out))
                for fr in frames:
                    walk(fr)
            elif tag == f"{D}frame" or tag == f"{D}text-box":
                walk(ch)
            elif tag == f"{TB}table":
                for row in ch.iter(f"{TB}table-row"):
                    cells = []
                    for cell in row.findall(f"{TB}table-cell"):
                        texts = []
                        for p in cell.iter(f"{T}p", f"{T}h"):
                            out = []
                            inline(p, out, [])
                            texts.append("".join(out))
                        cells.append(" ".join(t.strip() for t in texts if t.strip()))
                    blocks.append(" | ".join(cells))
            elif tag in (f"{T}list", f"{T}list-item", f"{T}list-header", f"{T}section",
                         f"{T}index-body", f"{T}table-of-content"):
                walk(ch)

    walk(body)
    return tidy("\n\n".join(blocks))


def sec_txt_to_text(raw):
    # EDGAR .txt exhibits may wrap the text in SGML tags such as <DOCUMENT>, <TEXT>.
    return tidy(re.sub(r"^<[^>\n]+>$", "", raw, flags=re.M))


def extract(url, resp):
    path = urlparse(url).path.lower()
    ctype = resp.headers.get("content-type", "")
    if path.endswith(".md"):
        return md_to_text(resp.text)
    if path.endswith(".pdf") or "pdf" in ctype:
        return pdf_to_text(resp.content)
    if path.endswith(".docx") or "wordprocessingml" in ctype:
        return docx_to_text(resp.content)
    if path.endswith(".odt") or "opendocument.text" in ctype:
        return odt_to_text(resp.content)
    if path.endswith(".txt"):
        return sec_txt_to_text(resp.text)
    return html_to_text(resp.text)


def pick_attachment(page_url, html, hint, order=DOC_EXT):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    found = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        p = urlparse(href).path.lower()
        ext = Path(p).suffix
        if ext in order:
            label = (a.get_text(" ", strip=True) + " " + p).lower()
            if hint and hint.lower() not in label:
                continue
            found.add((order.index(ext), href))
    return sorted(found)[0][1] if found else None


def fetch_source(src, raw_dir):
    allowed = allowed_hosts(src)
    urls = src.get("fetch")
    notes = []
    if not urls:
        page, page_url = get(src["url"], allowed)
        att = None
        if "html" in page.headers.get("content-type", ""):
            att = pick_attachment(page_url, page.text, src.get("attachment_hint"),
                                  tuple(src.get("attachment_ext", DOC_EXT)))
        urls = [att] if att else [src["url"]]
        if att:
            notes.append(f"attachment: {att}")
    texts = []
    for i, u in enumerate(urls):
        r, final = get(u, allowed)
        name = f"{src['source_id']}-{i}{Path(urlparse(final).path).suffix or '.html'}"
        (raw_dir / name).write_bytes(r.content)
        texts.append(extract(final, r))
    return "\n".join(texts), urls, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="/tmp/raw/contracts")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    raw_dir = Path(args.raw_dir)
    (raw_dir / "text").mkdir(parents=True, exist_ok=True)
    only = set(filter(None, args.only.split(",")))

    old = {}
    if MANIFEST.exists():
        old = {e["source_id"]: e for e in json.loads(MANIFEST.read_text())["sources"]}
    entries = []
    for src in SOURCES:
        sid = src["source_id"]
        if only and sid not in only:
            entries.append(old.get(sid, {"source_id": sid}))
            continue
        entry = {
            "source_id": sid,
            "title": src["title"],
            "url": src["url"],
            "licence": src["licence"],
            "kind": src["kind"],
            "subtype": src["subtype"],
        }
        try:
            text, used, notes = fetch_source(src, raw_dir)
        except Exception as e:  # record and continue with the other sources
            prev = old.get(sid, {})
            host = urlparse((src.get("fetch") or [src["url"]])[0]).hostname
            if isinstance(e, requests.exceptions.ProxyError):
                why = f"blocked: the build sandbox's egress proxy refused CONNECT to {host} (403)"
            else:
                why = f"fetch failed for {host}: {type(e).__name__}: {str(e)[:160]}"
            entry.update(
                fetched=prev.get("fetched", False),
                fetched_at=prev.get("fetched_at"),
                fetched_from=prev.get("fetched_from"),
                sha256=prev.get("sha256"),
                notes=why,
            )
            print(f"{sid}: FAILED {entry['notes']}", file=sys.stderr)
            entries.append(entry)
            continue
        (raw_dir / "text" / f"{sid}.txt").write_text(text, encoding="utf-8")
        entry.update(
            fetched=True,
            fetched_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            fetched_from=used,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            notes="; ".join(filter(None, [src.get("note", "")] + notes)),
        )
        print(f"{sid}: ok, {len(text)} chars -> {raw_dir / 'text' / (sid + '.txt')}")
        entries.append(entry)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"sources": entries}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
