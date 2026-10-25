"""Download the real insurance source to a directory OUTSIDE the repo and convert it to
plain text, so the template can be written from it.

INS1: Pre-Action Protocol for Personal Injury Claims, www.justice.gov.uk, Crown copyright.
      Annexes B1 (letter of claim), B2 (letter of response) and D (letter of instruction to
      medical expert) are sections of the protocol page itself (anchors #B and #D), so the
      page is fetched once and the three annexes are cut out of its text.
INS2 (Lloyd's blanket bond, SEC EDGAR) is blocked by decision (24 Oct 2026): sec.gov is
      never fetched, and no INS2 template is built.

Only hosts in ALLOWED_HOSTS are contacted, and a redirect to any other host is refused.

Usage: python3 fetch_real.py [--raw /tmp/raw/financial_insurance]
"""

import argparse
import hashlib
import json
import re
import ssl
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit

from common import REPO

USER_AGENT = "night-shift-hackathon dataset build (github.com/BabyBoss45/night-shift)"
ALLOWED_HOSTS = {"www.justice.gov.uk"}
SOURCES = {
    "INS1": "https://www.justice.gov.uk/courts/procedure-rules/civil/protocol/prot_pic",
}
# Annex sections of the INS1 page text: name, start heading, end heading (first match after start).
INS1_ANNEXES = [
    ("B1", r"^B1 Letter of Claim\s*$", r"^B2 Letter of response\s*$"),
    ("B2", r"^B2 Letter of response\s*$", r"^Annex C\b"),
    ("D", r"^ANNEX D: Letter of instruction to medical expert\s*$", r"^Updated: "),
]
# Linked annex documents (a PDF or Word version, if the page ever links one) for B1, B2 or D.
ANNEX_RE = re.compile(r"annex[\s_-]*(b[\s_-]*1|b[\s_-]*2|d)\b", re.I)
BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "pre", "hr"}


class TextAndLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self._href, self._link_text, self._skip = [], [], None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "td":
            self.parts.append("\t")
        if tag == "a":
            self._href, self._link_text = dict(attrs).get("href"), []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "a" and self._href:
            self.links.append((self._href, "".join(self._link_text).strip()))
            self._href = None

    def handle_data(self, data):
        if self._skip:
            return
        self.parts.append(data)
        if self._href:
            self._link_text.append(data)

    def text(self):
        t = re.sub(r"[ \t\xa0]+", " ", "".join(self.parts))
        t = "\n".join(line.strip() for line in t.split("\n"))
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip() + "\n"


def allowed(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS


def tls_context():
    """Verified TLS. Some Python builds (python.org and uv on macOS) ship without a CA store,
    so use certifi's bundle when it is installed (it comes with requests / huggingface_hub)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def get(url):
    if not allowed(url):
        raise PermissionError(f"host not allowed: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=60, context=tls_context()) as r:
        if not allowed(r.geturl()):
            raise PermissionError(f"redirected to a host that is not allowed: {r.geturl()}")
        return r.read()


def html_text(data):
    p = TextAndLinks()
    p.feed(data.decode("utf-8", errors="replace"))
    return p.text(), p.links


def save(raw, name, data, log, text=None):
    path = raw / name
    path.write_bytes(data)
    if text is None and (name.endswith((".htm", ".html")) or b"<html" in data[:2000].lower()):
        text = html_text(data)[0]
    if text is not None:
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
    log.append(dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), text=text is not None))
    print(f"  saved {path} ({len(data):,} bytes){' + .txt' if text is not None else ' (convert by hand)'}")


def cut_annexes(text):
    """Return {name: section text} for the INS1 annexes, or raise if a heading is missing."""
    out = {}
    for name, start_re, end_re in INS1_ANNEXES:
        start = re.search(start_re, text, re.M)
        if not start:
            raise ValueError(f"annex {name}: start heading not found ({start_re})")
        end = re.compile(end_re, re.M).search(text, start.end())
        if not end:
            raise ValueError(f"annex {name}: end heading not found ({end_re})")
        section = text[start.start():end.start()]
        section = re.sub(r"(?m)^To the top\s*$\n?", "", section)
        out[name] = re.sub(r"\n{3,}", "\n\n", section).strip() + "\n"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("/tmp/raw/financial_insurance"))
    args = ap.parse_args()
    raw = args.raw.resolve()
    if raw.is_relative_to(REPO):
        sys.exit("raw files must be kept outside the repo")
    raw.mkdir(parents=True, exist_ok=True)
    log, failed = [], []
    for sid, url in SOURCES.items():
        print(f"{sid}: {url}")
        try:
            data = get(url)
        except (HTTPError, URLError, OSError, PermissionError) as ex:
            print(f"  FAILED: {ex}")
            failed.append(dict(source=sid, url=url, error=str(ex)))
            continue
        text, links = html_text(data)
        save(raw, f"{sid}.html", data, log, text)
        if sid != "INS1":
            continue
        try:
            for name, section in cut_annexes(text).items():
                path = raw / f"INS1-annex-{name}.txt"
                path.write_text(section, encoding="utf-8")
                print(f"  annex {name}: {path} ({len(section):,} characters)")
        except ValueError as ex:
            print(f"  FAILED: {ex}")
            failed.append(dict(source=sid, url=url, error=str(ex)))
        for href, label in links:
            link = urljoin(url, href)
            if link.split("#")[0] == url or not (ANNEX_RE.search(label) or ANNEX_RE.search(href)):
                continue  # an anchor on the page already fetched, or not one of the three annexes
            if not allowed(link):
                print(f"  skipped (host not allowed): {link}")
                continue
            name = f"INS1-annex-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')[:40]}{Path(urlsplit(link).path).suffix or '.html'}"
            try:
                save(raw, name, get(link), log)
            except (HTTPError, URLError, OSError, PermissionError) as ex:
                failed.append(dict(source=sid, url=link, error=str(ex)))
                print(f"  FAILED {link}: {ex}")
    (raw / "fetch_log.json").write_text(json.dumps(dict(saved=log, failed=failed), indent=2), encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
