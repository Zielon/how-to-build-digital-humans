#!/usr/bin/env python3
"""Fetch missing thumbnails and abstracts from paper PDFs.

For each paper missing a thumbnail or abstract, finds a PDF URL (from arxiv,
webpage, or other metadata), downloads it, renders the first page as a JPEG
thumbnail, and extracts the abstract from the text.

Usage (from repo root):
    python tables_src/fetch_from_pdf.py
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_publications import (
    BIB_FILE,
    load_abstract_file,
    parse_bibliography_with_metadata,
)

ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
ABSTRACT_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

THUMB_WIDTH = 400

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _sanitize_filename(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _get_all_pdf_urls(entry: dict) -> list[str]:
    """Collect all potential PDF URLs from the entry metadata."""
    urls: list[str] = []
    for field in ("arxiv", "webpage"):
        url = entry.get(field, "")
        if not url or url.lower() == "none":
            continue
        # Direct PDF link
        if url.lower().endswith(".pdf"):
            urls.append(url)
            continue
        # arXiv: convert abs -> pdf if needed
        if "arxiv.org/abs/" in url:
            urls.append(url.replace("/abs/", "/pdf/"))
            continue
        if "arxiv.org/pdf/" in url:
            urls.append(url)
            continue
    return urls


def _find_pdf_on_page(page_url: str) -> str | None:
    """Visit a project page and look for a PDF link."""
    req = urllib.request.Request(
        page_url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; pdf-fetch)",
            "Accept": "text/html,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return None
            data = resp.read()
            try:
                html = data.decode("utf-8")
            except UnicodeDecodeError:
                html = data.decode("latin-1")
    except Exception:
        return None

    # Find links to PDFs
    pdf_links = []
    for m in re.finditer(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.I):
        href = m.group(1)
        full = urllib.parse.urljoin(page_url, href)
        # Score: prefer "paper" links over random PDFs
        score = 0
        lower = href.lower()
        if any(kw in lower for kw in ["paper", "main", "article", "full"]):
            score += 5
        if "supplementary" in lower or "supp" in lower:
            score -= 3
        pdf_links.append((score, full))

    if not pdf_links:
        return None
    pdf_links.sort(key=lambda x: -x[0])
    return pdf_links[0][1]


def _download_pdf(url: str) -> bytes | None:
    """Download a PDF, returning raw bytes. Returns None on failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; pdf-fetch)",
            "Accept": "application/pdf,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25, context=_SSL_CTX) as resp:
            data = resp.read()
        if not data or not data[:5].startswith(b"%PDF"):
            return None
        return data
    except Exception as e:
        print(f"    [download error] {e}")
        return None


def _render_thumbnail(pdf_bytes: bytes, width: int = THUMB_WIDTH) -> bytes | None:
    """Render first page of PDF to a JPEG thumbnail."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        scale = width / page.rect.width
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        jpeg_bytes = pix.tobytes(output="jpeg", jpg_quality=85)
        doc.close()
        return jpeg_bytes
    except Exception as e:
        print(f"    [render error] {e}")
        return None


def _extract_text(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Extract text from first N pages."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text = []
        for i in range(min(max_pages, len(doc))):
            pages_text.append(doc[i].get_text())
        doc.close()
        return "\n".join(pages_text)
    except Exception:
        return ""


def _find_abstract(text: str) -> str | None:
    """Locate the abstract section in extracted PDF text."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strategy 1: "Abstract" header + text until next section
    m = re.search(
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\-—.]?\s*\n(.*?)(?:\n\s*(?:1[\s.]|I\s|Introduction|INTRODUCTION|Keywords|Index\s[Tt]erms|CCS\s|Categories|1\s+Introduction|ACM\s))",
        text, re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    # Strategy 2: "Abstract" + text until double newline
    m = re.search(
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\-—.]?\s*\n(.+?)(?:\n\n|\n\s*(?:1[\s.]|Introduction|Keywords))",
        text, re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    # Strategy 3: "Abstract." or "Abstract—" inline
    m = re.search(
        r"(?:ABSTRACT|Abstract)\s*[.—:\-]\s*(.+?)(?:\n\s*(?:1[\s.]|I\.\s|Introduction|INTRODUCTION|Keywords|Index\s[Tt]erms|CCS))",
        text, re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    return None


def _clean_abstract(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def main():
    entries = parse_bibliography_with_metadata(BIB_FILE)
    entries = [
        e for e in entries
        if any(e.get(f, "") and e.get(f, "").lower() != "none"
               for f in ("webpage", "code", "video", "arxiv"))
    ]

    # Find entries that need either a thumbnail or abstract
    to_process = []
    for e in entries:
        key = e["key"]
        needs_thumb = not (THUMB_DIR / f"{key}.jpg").exists()
        needs_abstract = not e["abstract"] and not load_abstract_file(key)
        if needs_thumb or needs_abstract:
            pdf_urls = _get_all_pdf_urls(e)
            # If no direct PDF URLs, try to find one on the project webpage
            if not pdf_urls:
                webpage = e.get("webpage", "")
                if webpage and webpage.lower() != "none":
                    print(f"  Scanning {key} webpage for PDF links...")
                    found = _find_pdf_on_page(webpage)
                    if found:
                        pdf_urls = [found]
                        print(f"    found: {found[:80]}")
                    time.sleep(0.5)
            if pdf_urls:
                to_process.append((e, pdf_urls, needs_thumb, needs_abstract))

    print(f"\nFound {len(to_process)} papers with PDF URLs needing thumbnail/abstract.\n")
    thumb_ok = 0
    abstract_ok = 0
    failed = 0

    for i, (e, pdf_urls, needs_thumb, needs_abstract) in enumerate(to_process):
        key = e["key"]
        print(f"[{i+1}/{len(to_process)}] {key} (thumb={'Y' if needs_thumb else 'N'}, abstract={'Y' if needs_abstract else 'N'})")

        pdf_bytes = None
        for url in pdf_urls:
            print(f"    trying: {url[:80]}")
            pdf_bytes = _download_pdf(url)
            if pdf_bytes:
                break

        if not pdf_bytes:
            failed += 1
            time.sleep(0.5)
            continue

        # Thumbnail
        if needs_thumb:
            jpeg = _render_thumbnail(pdf_bytes)
            if jpeg:
                (THUMB_DIR / f"{key}.jpg").write_bytes(jpeg)
                thumb_ok += 1
                print(f"    -> thumbnail saved ({len(jpeg)//1024} KB)")
            else:
                print(f"    -> thumbnail render failed")

        # Abstract
        if needs_abstract:
            text = _extract_text(pdf_bytes)
            abstract = _find_abstract(text) if text else None
            if abstract and len(abstract) > 80:
                fname = _sanitize_filename(key)
                (ABSTRACT_DIR / f"{fname}.txt").write_text(abstract, encoding="utf-8")
                abstract_ok += 1
                print(f"    -> abstract saved ({len(abstract)} chars)")
            else:
                print(f"    -> abstract not found in PDF")

        time.sleep(0.5)

    print(f"\nDone.")
    print(f"  Thumbnails saved: {thumb_ok}")
    print(f"  Abstracts saved: {abstract_ok}")
    print(f"  Failed downloads: {failed}")

    total_thumbs = sum(1 for e in entries if (THUMB_DIR / f"{e['key']}.jpg").exists())
    total_abstracts = sum(1 for e in entries if e["abstract"] or load_abstract_file(e["key"]))
    print(f"  Total thumbnails: {total_thumbs}/{len(entries)}")
    print(f"  Total abstracts: {total_abstracts}/{len(entries)}")


if __name__ == "__main__":
    main()
