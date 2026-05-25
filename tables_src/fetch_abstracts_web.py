#!/usr/bin/env python3
"""Fetch missing abstracts from project webpages.

Scans bibliography.bib for papers that still lack an abstract file, visits
their project webpage, and tries to extract the abstract from the HTML.

Usage (from repo root):
    python tables_src/fetch_abstracts_web.py
"""

from __future__ import annotations

import html as html_mod
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

ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
ABSTRACT_DIR.mkdir(parents=True, exist_ok=True)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _sanitize_filename(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _fetch_page(url: str) -> str | None:
    """Download a webpage and return the HTML as a string."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; abstract-fetch)",
            "Accept": "text/html,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return None
            data = resp.read()
            # Try UTF-8, fall back to latin-1
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1")
    except Exception as e:
        print(f"    [fetch error] {e}")
        return None


def _strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_abstract_from_html(page_html: str) -> str | None:
    """Try to find the abstract in HTML content."""
    # Strategy 1: Look for a dedicated abstract section/div
    # Common patterns: <div class="abstract">, <p class="abstract">,
    # <section id="abstract">, <h2>Abstract</h2><p>...
    for pattern in [
        r'<(?:div|section|p)[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</(?:div|section|p)>',
        r'<(?:div|section)[^>]*id="[^"]*abstract[^"]*"[^>]*>(.*?)</(?:div|section)>',
    ]:
        m = re.search(pattern, page_html, re.S | re.I)
        if m:
            text = _strip_tags(m.group(1)).strip()
            if len(text) > 80:
                return text

    # Strategy 2: Look for "Abstract" heading followed by content
    # Find in raw HTML
    m = re.search(
        r"<h[1-6][^>]*>\s*Abstract\s*</h[1-6]>\s*(.*?)(?:<h[1-6]|<div\s+class=\"|<section)",
        page_html,
        re.S | re.I,
    )
    if m:
        text = _strip_tags(m.group(1)).strip()
        if len(text) > 80:
            return text

    # Strategy 3: Look in plain text version
    text = _strip_tags(page_html)

    # Find "Abstract" as a heading followed by text
    m = re.search(
        r"(?:^|\n)\s*Abstract\s*\n(.*?)(?:\n\s*(?:1[\s.]|Introduction|Keywords|BibTeX|Citation|Related|Video|Results|Downloads|Code|Acknowledgment|Reference))",
        text,
        re.S | re.I,
    )
    if m:
        abstract = m.group(1).strip()
        # Clean up
        abstract = re.sub(r"\n(?!\n)", " ", abstract)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        if len(abstract) > 80:
            return abstract

    # Strategy 4: meta description tag (often contains abstract)
    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']{80,})["\']',
        page_html,
        re.I,
    )
    if m:
        desc = html_mod.unescape(m.group(1)).strip()
        if len(desc) > 100:
            return desc

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
        if not e["abstract"] and not load_abstract_file(e["key"]):
            webpage = e.get("webpage", "")
            if webpage and webpage.lower() != "none":
                missing.append((e, webpage))

    print(f"Found {len(missing)} papers with webpage URLs but no abstract.\n")
    fetched = 0
    failed = 0

    for i, (e, url) in enumerate(missing):
        key = e["key"]
        fname = _sanitize_filename(key)
        out_path = ABSTRACT_DIR / f"{fname}.txt"

        print(f"[{i+1}/{len(missing)}] {key}")
        print(f"    URL: {url}")

        page_html = _fetch_page(url)
        if not page_html:
            failed += 1
            print("    -> fetch failed")
            time.sleep(1.0)
            continue

        abstract = _extract_abstract_from_html(page_html)
        if abstract and len(abstract) > 80:
            out_path.write_text(abstract, encoding="utf-8")
            fetched += 1
            print(f"    -> saved ({len(abstract)} chars)")
        else:
            failed += 1
            print("    -> abstract not found on page")

        time.sleep(1.0)

    print(f"\nDone. Fetched {fetched} abstracts from webpages, failed {failed}.")


if __name__ == "__main__":
    main()
