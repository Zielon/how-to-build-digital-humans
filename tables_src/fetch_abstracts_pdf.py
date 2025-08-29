#!/usr/bin/env python3
"""Fetch missing abstracts by downloading PDFs and extracting the abstract section.

Scans bibliography.bib for papers that still lack an abstract file, finds a
downloadable PDF URL, downloads it to a temp file, extracts text from the first
two pages, and locates the abstract paragraph.

Usage (from repo root):
    python tables_src/fetch_abstracts_pdf.py
"""

from __future__ import annotations

import io
import re
import ssl
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

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

# Relaxed SSL context for sites with cert issues
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _sanitize_filename(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _get_pdf_url(entry: dict) -> str | None:
    """Find a direct-download PDF URL from any metadata field."""
    for field in ("arxiv", "webpage"):
        url = entry.get(field, "")
        if url and url.lower() != "none" and url.lower().endswith(".pdf"):
            return url
    return None


def _download_pdf(url: str) -> bytes | None:
    """Download a PDF, following redirects, returning raw bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; abstract-fetch)",
            "Accept": "application/pdf,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            data = resp.read()
        if not data or len(data) < 1000:
            return None
        return data
    except Exception as e:
        print(f"    [download error] {e}")
        return None


def _extract_text_fitz(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Extract text from first N pages using PyMuPDF (fitz)."""
    import fitz  # type: ignore

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for i in range(min(max_pages, len(doc))):
        pages_text.append(doc[i].get_text())
    doc.close()
    return "\n".join(pages_text)


def _extract_text_pypdf2(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Fallback: extract text using PyPDF2."""
    import PyPDF2  # type: ignore

    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for i in range(min(max_pages, len(reader.pages))):
        pages_text.append(reader.pages[i].extract_text() or "")
    return "\n".join(pages_text)


def _extract_text(pdf_bytes: bytes) -> str:
    """Try PyMuPDF first, then PyPDF2."""
    try:
        return _extract_text_fitz(pdf_bytes)
    except Exception:
        pass
    try:
        return _extract_text_pypdf2(pdf_bytes)
    except Exception:
        pass
    return ""


def _find_abstract(text: str) -> str | None:
    """Locate the abstract section in extracted PDF text."""
    # Normalise whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strategy 1: look for "Abstract" header followed by text, ending at a
    # section header (Introduction, 1., Keywords, etc.)
    m = re.search(
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\-—.]?\s*\n(.*?)(?:\n\s*(?:1[\s.]|I\s|Introduction|INTRODUCTION|Keywords|Index\s[Tt]erms|CCS\s|Categories|1\s+Introduction|ACM\s))",
        text,
        re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    # Strategy 2: "Abstract" on its own line, grab everything until double newline
    # or next section
    m = re.search(
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\-—.]?\s*\n(.+?)(?:\n\n|\n\s*(?:1[\s.]|Introduction|Keywords))",
        text,
        re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    # Strategy 3: "Abstract." or "Abstract—" inline
    m = re.search(
        r"(?:ABSTRACT|Abstract)\s*[.—:\-]\s*(.+?)(?:\n\s*(?:1[\s.]|I\.\s|Introduction|INTRODUCTION|Keywords|Index\s[Tt]erms|CCS))",
        text,
        re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            return _clean_abstract(abstract)

    return None


def _clean_abstract(text: str) -> str:
    """Clean up extracted abstract text."""
    # Join hyphenated line breaks
    text = re.sub(r"-\s*\n\s*", "", text)
    # Join remaining line breaks within paragraphs
    text = re.sub(r"\n(?!\n)", " ", text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def main():
    entries = parse_bibliography_with_metadata(BIB_FILE)
    entries = [
        e
        for e in entries
        if any(
            e.get(f, "") and e.get(f, "").lower() != "none"
            for f in ("webpage", "code", "video", "arxiv")
        )
    ]

    missing = []
    for e in entries:
        if not e["abstract"] and not load_abstract_file(e["key"]):
            pdf_url = _get_pdf_url(e)
            if pdf_url:
                missing.append((e, pdf_url))

    print(f"Found {len(missing)} papers with PDF URLs but no abstract.\n")
    fetched = 0
    failed = 0

    for i, (e, pdf_url) in enumerate(missing):
        key = e["key"]
        fname = _sanitize_filename(key)
        out_path = ABSTRACT_DIR / f"{fname}.txt"

        print(f"[{i+1}/{len(missing)}] {key}")
        print(f"    URL: {pdf_url}")

        pdf_bytes = _download_pdf(pdf_url)
        if not pdf_bytes:
            failed += 1
            print(f"    -> download failed")
            time.sleep(1.0)
            continue

        text = _extract_text(pdf_bytes)
        if not text:
            failed += 1
            print(f"    -> text extraction failed")
            time.sleep(1.0)
            continue

        abstract = _find_abstract(text)
        if abstract and len(abstract) > 80:
            out_path.write_text(abstract, encoding="utf-8")
            fetched += 1
            print(f"    -> saved ({len(abstract)} chars)")
        else:
            failed += 1
            print(f"    -> abstract not found in PDF text")

        time.sleep(1.0)

    print(f"\nDone. Fetched {fetched} abstracts from PDFs, failed {failed}.")


if __name__ == "__main__":
    main()
