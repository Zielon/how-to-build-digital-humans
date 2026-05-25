#!/usr/bin/env python3
"""Fetch missing thumbnails from project webpages.

Visits each paper's project webpage and finds the first large image
(teaser/figure) to use as a thumbnail.

Usage (from repo root):
    python tables_src/fetch_thumbnails_web.py
"""

from __future__ import annotations

import io
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF — also used for image conversion

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

THUMB_WIDTH = 400

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _fetch_page(url: str) -> str | None:
    """Download a webpage as string."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; thumbnail-fetch)",
            "Accept": "text/html,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1")
    except Exception as e:
        print(f"    [page fetch error] {e}")
        return None


def _download_image(url: str) -> bytes | None:
    """Download an image, returning raw bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (academic-survey-tool; thumbnail-fetch)",
            "Accept": "image/*,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read()
    except Exception as e:
        print(f"    [image download error] {e}")
        return None


def _find_teaser_image(html: str, base_url: str) -> str | None:
    """Find the best candidate teaser image URL from the page HTML."""
    # Collect all <img> tags with src
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)

    # Also check og:image meta tag (often the teaser)
    og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not og:
        og = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
    if og:
        imgs.insert(0, og.group(1))

    # Filter and score images
    candidates = []
    for src in imgs:
        # Skip tiny icons, tracking pixels, logos
        lower = src.lower()
        if any(skip in lower for skip in [
            "logo", "icon", "favicon", "badge", "button", "avatar",
            "tracking", "pixel", "analytics", "1x1", "spacer",
            ".svg", "data:image", "github.com/favicon",
        ]):
            continue

        # Resolve relative URLs
        full_url = urllib.parse.urljoin(base_url, src)

        # Prefer teaser/figure images
        score = 0
        if any(kw in lower for kw in ["teaser", "fig1", "figure1", "representative", "overview", "pipeline", "banner", "hero"]):
            score += 10
        if any(ext in lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            score += 1
        if any(kw in lower for kw in ["thumb", "small", "mini"]):
            score -= 5

        candidates.append((score, full_url))

    if not candidates:
        return None

    # Sort by score (descending), take best
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def _image_to_jpeg_thumbnail(img_bytes: bytes, width: int = THUMB_WIDTH) -> bytes | None:
    """Convert image bytes to a JPEG thumbnail at the given width."""
    try:
        # Handle GIFs — extract first frame via a temporary PDF
        if img_bytes[:4] == b"GIF8":
            doc = fitz.open(stream=img_bytes, filetype="gif")
            if len(doc) == 0:
                return None
            page = doc[0]
            scale = width / page.rect.width if page.rect.width > width else 1.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            doc.close()
        else:
            pix = fitz.Pixmap(img_bytes)

        if pix.width < 50 or pix.height < 50:
            return None  # Too small, likely an icon

        # Drop alpha channel
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix, 0)
        elif pix.n != 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)

        # Resize if wider than target
        if pix.width > width:
            scale = width / pix.width
            new_w = int(pix.width * scale)
            new_h = int(pix.height * scale)
            # Create resized via a temp PDF page
            doc = fitz.open()
            page = doc.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, pixmap=pix)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)
            doc.close()

        return pix.tobytes(output="jpeg", jpg_quality=85)
    except Exception as e:
        print(f"    [convert error] {e}")
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
        if thumb_path.exists():
            continue
        webpage = e.get("webpage", "")
        if webpage and webpage.lower() != "none":
            missing.append((e, webpage))

    print(f"Found {len(missing)} papers with webpage but no thumbnail.\n")
    fetched = 0
    failed = 0

    for i, (e, url) in enumerate(missing):
        key = e["key"]
        thumb_path = THUMB_DIR / f"{key}.jpg"

        print(f"[{i+1}/{len(missing)}] {key}")
        print(f"    URL: {url}")

        page_html = _fetch_page(url)
        if not page_html:
            failed += 1
            time.sleep(1.0)
            continue

        img_url = _find_teaser_image(page_html, url)
        if not img_url:
            failed += 1
            print("    -> no suitable image found on page")
            time.sleep(1.0)
            continue

        print(f"    img: {img_url[:80]}")
        img_bytes = _download_image(img_url)
        if not img_bytes or len(img_bytes) < 1000:
            failed += 1
            print("    -> image download failed or too small")
            time.sleep(1.0)
            continue

        jpeg = _image_to_jpeg_thumbnail(img_bytes)
        if not jpeg:
            failed += 1
            print("    -> image conversion failed")
            time.sleep(1.0)
            continue

        thumb_path.write_bytes(jpeg)
        fetched += 1
        print(f"    -> saved ({len(jpeg)//1024} KB)")

        time.sleep(1.0)

    print(f"\nDone. Fetched {fetched} thumbnails, failed {failed}.")
    existing = sum(1 for e in entries if (THUMB_DIR / (e["key"] + ".jpg")).exists())
    print(f"Total with thumbnails now: {existing}/{len(entries)}")


if __name__ == "__main__":
    main()
