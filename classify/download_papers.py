#!/Library/Developer/CommandLineTools/usr/bin/python3
"""Download PDFs and extract full text for unclassified papers.

For each unclassified paper, finds the arXiv or other PDF URL,
downloads the PDF, extracts text from all pages, and saves to
classify/texts/<key>.txt.
"""

from __future__ import annotations

import json
import re
import ssl
import sys
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

JSON_FILE = ROOT / "classify" / "final_results.json"
TEXT_DIR = ROOT / "classify" / "texts"
TEXT_DIR.mkdir(parents=True, exist_ok=True)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _get_pdf_url(entry: dict) -> str | None:
    """Find a PDF download URL from bib entry fields."""
    # Try arXiv first — convert abs/ to pdf/
    for field in ("arxiv", "webpage", "code", "video"):
        url = entry.get(field, "")
        if not url or url.lower() == "none":
            continue
        # arXiv abs -> pdf
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
        if m:
            return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
        # Direct PDF link
        if url.lower().endswith(".pdf"):
            return url
    return None


def _download_pdf(url: str) -> bytes | None:
    """Download a PDF, returning raw bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; paper-fetch)",
            "Accept": "application/pdf,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            data = resp.read()
        if not data or len(data) < 1000:
            return None
        return data
    except Exception as e:
        print(f"    [download error] {e}")
        return None


def _extract_text(pdf_bytes: bytes, max_pages: int = 10) -> str:
    """Extract text from PDF using PyMuPDF."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for i in range(min(max_pages, len(doc))):
        pages_text.append(doc[i].get_text())
    doc.close()
    return "\n\n".join(pages_text)


def main():
    # Load existing classifications
    with JSON_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    classified_keys = {item["key"] for item in data.get("avatar_classifications", [])}
    classified_keys |= {item["key"] for item in data.get("assets_classifications", [])}
    skipped_keys = {item["key"] for item in data.get("skipped", [])}
    all_known = classified_keys | skipped_keys

    # Load all bib entries with metadata
    entries = parse_bibliography_with_metadata(BIB_FILE)

    def has_meta(e):
        for field in ("webpage", "code", "video", "arxiv"):
            v = e.get(field, "")
            if v and v.lower() != "none":
                return True
        return False

    entries = [e for e in entries if has_meta(e)]
    unclassified = [e for e in entries if e["key"] not in all_known]

    print(f"Found {len(unclassified)} unclassified papers")

    # Check which already have text extracted
    already_have = 0
    to_download = []
    for e in unclassified:
        text_file = TEXT_DIR / f"{e['key']}.txt"
        if text_file.exists() and text_file.stat().st_size > 200:
            already_have += 1
        else:
            to_download.append(e)

    print(f"Already have text for {already_have} papers")
    print(f"Need to download {len(to_download)} papers\n")

    fetched = 0
    failed = 0
    no_url = 0

    for i, e in enumerate(to_download):
        key = e["key"]
        text_file = TEXT_DIR / f"{key}.txt"

        pdf_url = _get_pdf_url(e)
        if not pdf_url:
            # Fall back to abstract if we have it
            abstract = e.get("abstract", "") or load_abstract_file(key)
            if abstract:
                text_file.write_text(
                    f"Title: {e['title']}\n\nAbstract:\n{abstract}",
                    encoding="utf-8",
                )
                fetched += 1
                print(f"[{i+1}/{len(to_download)}] {key} — used abstract (no PDF URL)")
            else:
                no_url += 1
                print(f"[{i+1}/{len(to_download)}] {key} — NO PDF URL or abstract")
            continue

        print(f"[{i+1}/{len(to_download)}] {key} — downloading {pdf_url}")

        pdf_bytes = _download_pdf(pdf_url)
        if not pdf_bytes:
            # Fall back to abstract
            abstract = e.get("abstract", "") or load_abstract_file(key)
            if abstract:
                text_file.write_text(
                    f"Title: {e['title']}\n\nAbstract:\n{abstract}",
                    encoding="utf-8",
                )
                fetched += 1
                print(f"    -> download failed, used abstract instead")
            else:
                failed += 1
                print(f"    -> download failed, no abstract available")
            time.sleep(1.0)
            continue

        text = _extract_text(pdf_bytes)
        if text and len(text) > 200:
            # Prepend title for context
            full_text = f"Title: {e['title']}\n\n{text}"
            text_file.write_text(full_text, encoding="utf-8")
            fetched += 1
            print(f"    -> saved ({len(text)} chars)")
        else:
            # Fall back to abstract
            abstract = e.get("abstract", "") or load_abstract_file(key)
            if abstract:
                text_file.write_text(
                    f"Title: {e['title']}\n\nAbstract:\n{abstract}",
                    encoding="utf-8",
                )
                fetched += 1
                print(f"    -> text extraction failed, used abstract")
            else:
                failed += 1
                print(f"    -> text extraction failed, no abstract")

        time.sleep(1.5)  # Be polite to arXiv

    print(f"\nDone. Fetched {fetched}, failed {failed}, no URL {no_url}")
    print(f"Total texts available: {already_have + fetched}/{len(unclassified)}")


if __name__ == "__main__":
    main()
