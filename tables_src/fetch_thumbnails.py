#!/usr/bin/env python3
"""Fetch missing paper thumbnails by rendering the first page of each PDF.

For papers with an arXiv or other direct PDF URL, downloads the PDF,
renders the first page to a JPEG thumbnail, and saves it under
assets/img/thumbnails/<key>.jpg.

Usage (from repo root):
    python tables_src/fetch_thumbnails.py
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_publications import (
    BIB_FILE,
    parse_bibliography_with_metadata,
)

THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

THUMB_WIDTH = 400  # px — reasonable card thumbnail width

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _get_pdf_url(entry: dict) -> str | None:
    """Find a downloadable PDF URL from the entry metadata."""
    # Prefer arxiv (usually a direct PDF link)
    arxiv = entry.get("arxiv", "")
    if arxiv and arxiv.lower() != "none":
        # Convert arxiv abs URL to pdf URL if needed
        if "arxiv.org/abs/" in arxiv:
            arxiv = arxiv.replace("/abs/", "/pdf/")
        if arxiv.lower().endswith(".pdf") or "arxiv.org/pdf/" in arxiv:
            return arxiv

    # Try webpage if it's a direct PDF
    webpage = entry.get("webpage", "")
    if webpage and webpage.lower().endswith(".pdf"):
        return webpage

    return None


def _download_pdf(url: str) -> bytes | None:
    """Download a PDF, returning raw bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; thumbnail-fetch)",
            "Accept": "application/pdf,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            data = resp.read()
        # Verify it's actually a PDF
        if not data or not data[:5].startswith(b"%PDF"):
            return None
        return data
    except Exception as e:
        print(f"    [download error] {e}")
        return None


def _render_thumbnail(pdf_bytes: bytes, width: int = THUMB_WIDTH) -> bytes | None:
    """Render the first page of a PDF to a JPEG thumbnail."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        # Scale to desired width
        scale = width / page.rect.width
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        jpeg_bytes = pix.tobytes(output="jpeg", jpg_quality=85)
        doc.close()
        return jpeg_bytes
    except Exception as e:
        print(f"    [render error] {e}")
        return None


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
        key = e["key"]
        thumb_path = THUMB_DIR / f"{key}.jpg"
        if not thumb_path.exists():
            pdf_url = _get_pdf_url(e)
            if pdf_url:
                missing.append((e, pdf_url))

    print(f"Found {len(missing)} papers with PDF URLs but no thumbnail.\n")
    fetched = 0
    failed = 0

    for i, (e, pdf_url) in enumerate(missing):
        key = e["key"]
        thumb_path = THUMB_DIR / f"{key}.jpg"

        print(f"[{i+1}/{len(missing)}] {key}")

        pdf_bytes = _download_pdf(pdf_url)
        if not pdf_bytes:
            failed += 1
            time.sleep(0.5)
            continue

        jpeg_bytes = _render_thumbnail(pdf_bytes)
        if not jpeg_bytes:
            failed += 1
            time.sleep(0.5)
            continue

        thumb_path.write_bytes(jpeg_bytes)
        fetched += 1
        print(f"    -> saved ({len(jpeg_bytes)//1024} KB)")

        # Rate limit — be polite to servers
        time.sleep(0.5)

    print(f"\nDone. Fetched {fetched} thumbnails, failed {failed}.")
    existing = sum(1 for e in entries if (THUMB_DIR / (e["key"] + ".jpg")).exists())
    print(f"Total with thumbnails now: {existing}/{len(entries)}")


if __name__ == "__main__":
    main()
