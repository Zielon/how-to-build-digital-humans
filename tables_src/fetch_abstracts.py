#!/usr/bin/env python3
"""Fetch missing abstracts from the arXiv API.

For papers with a known arXiv ID (extracted from the Arxiv URL in the bib
file), the abstract is fetched directly.  For the rest, the script searches
arXiv by title and picks the best match.

Usage (from repo root):
    python tables_src/fetch_abstracts.py
"""

from __future__ import annotations

import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}


def _sanitize_filename(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _extract_arxiv_id(entry: dict) -> str | None:
    """Try to extract an arXiv paper ID from any URL field."""
    for field in ("arxiv", "webpage", "code", "video"):
        url = entry.get(field, "")
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
        if m:
            return m.group(1)
    return None


def _fetch_abstract_by_id(arxiv_id: str) -> str | None:
    """Fetch abstract from arXiv API by paper ID."""
    url = f"{ARXIV_API}?id_list={arxiv_id}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml = resp.read()
    except Exception as e:
        print(f"    [ERROR] fetch failed: {e}")
        return None
    root = ET.fromstring(xml)
    entry = root.find("atom:entry", NS)
    if entry is None:
        return None
    summary = entry.find("atom:summary", NS)
    if summary is None or not summary.text:
        return None
    return summary.text.strip()


def _search_abstract_by_title(title: str) -> str | None:
    """Search arXiv by title and return the abstract of the best match."""
    # Clean LaTeX artefacts from title
    clean = re.sub(r"[{}\\]", "", title).strip()
    if not clean:
        return None
    q = urllib.parse.quote(f'ti:"{clean}"')
    url = f"{ARXIV_API}?search_query={q}&max_results=1"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml = resp.read()
    except Exception as e:
        print(f"    [ERROR] search failed: {e}")
        return None
    root = ET.fromstring(xml)
    entry = root.find("atom:entry", NS)
    if entry is None:
        return None
    # Verify the title is a close match
    found_title = entry.findtext("atom:title", "", NS).strip()
    found_title_norm = re.sub(r"\s+", " ", found_title).lower()
    clean_norm = re.sub(r"\s+", " ", clean).lower()
    if clean_norm not in found_title_norm and found_title_norm not in clean_norm:
        return None
    summary = entry.find("atom:summary", NS)
    if summary is None or not summary.text:
        return None
    return summary.text.strip()


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
            missing.append(e)

    print(f"Found {len(missing)} papers without abstracts.\n")
    fetched = 0
    failed = 0

    for i, e in enumerate(missing):
        key = e["key"]
        fname = _sanitize_filename(key)
        out_path = ABSTRACT_DIR / f"{fname}.txt"

        arxiv_id = _extract_arxiv_id(e)

        if arxiv_id:
            print(f"[{i+1}/{len(missing)}] {key} — fetching by ID {arxiv_id}")
            abstract = _fetch_abstract_by_id(arxiv_id)
        else:
            title = e.get("title", "")
            print(f"[{i+1}/{len(missing)}] {key} — searching by title")
            abstract = _search_abstract_by_title(title)

        if abstract:
            out_path.write_text(abstract, encoding="utf-8")
            fetched += 1
            print(f"    -> saved ({len(abstract)} chars)")
        else:
            failed += 1
            print(f"    -> not found")

        # Be polite to the API (rate limit: ~1 req/sec)
        time.sleep(1.0)

    print(f"\nDone. Fetched {fetched}, failed {failed}.")


if __name__ == "__main__":
    main()
