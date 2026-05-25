#!/Library/Developer/CommandLineTools/usr/bin/python3
"""Comprehensive fetcher: thumbnails, abstracts, and full text for classification.

For each paper missing a thumbnail:
1. Try arXiv PDF URL (direct or from bib metadata)
2. If no arXiv, scan the project webpage for PDF links
3. Download the PDF, extract:
   - Thumbnail (first page render → JPEG)
   - Abstract (if missing)
   - Full text (for classification, if missing)

Usage (from repo root):
    python tables_src/fetch_all.py
"""

from __future__ import annotations

import html as html_mod
import json
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

THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
ABSTRACT_DIR.mkdir(parents=True, exist_ok=True)

TEXT_DIR = ROOT / "classify" / "texts"
TEXT_DIR.mkdir(parents=True, exist_ok=True)

THUMB_WIDTH = 400
MAX_TEXT_PAGES = 10

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _get_arxiv_pdf_url(entry: dict) -> str | None:
    """Extract arXiv PDF URL from bib entry."""
    for field in ("arxiv", "webpage"):
        url = entry.get(field, "")
        if not url or url.lower() == "none":
            continue
        # Match arxiv.org abs or pdf URLs
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
        if m:
            return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
        # Direct PDF on arxiv
        if "arxiv.org" in url and url.lower().endswith(".pdf"):
            return url
    return None


def _get_direct_pdf_url(entry: dict) -> str | None:
    """Check if any metadata field is a direct PDF link."""
    for field in ("arxiv", "webpage"):
        url = entry.get(field, "")
        if not url or url.lower() == "none":
            continue
        lower = url.lower()
        if lower.endswith(".pdf"):
            return url
        # ACM Digital Library PDF links: dl.acm.org/doi/pdf/...
        if "dl.acm.org/doi/pdf/" in lower:
            return url
        # ACM DOI page: try converting to PDF URL
        m = re.match(r"https?://dl\.acm\.org/doi/(10\.\d+/[\w.]+)", url)
        if m:
            return f"https://dl.acm.org/doi/pdf/{m.group(1)}"
    return None


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _download(url: str, accept: str = "*/*", timeout: int = 20) -> bytes | None:
    """Download URL content."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (academic-survey-tool; fetch)",
        "Accept": accept,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return resp.read()
    except Exception as e:
        print(f"    [download error] {e}")
        return None


def _fetch_page(url: str) -> str | None:
    """Download webpage as string."""
    data = _download(url, accept="text/html,*/*", timeout=15)
    if not data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# ---------------------------------------------------------------------------
# Webpage PDF finder
# ---------------------------------------------------------------------------

def _find_pdf_on_webpage(page_html: str, base_url: str) -> str | None:
    """Scan a project webpage for links to a PDF (paper/preprint)."""
    # Find all href links
    links = re.findall(r'href=["\']([^"\']+)["\']', page_html, re.I)

    candidates = []
    for href in links:
        full_url = urllib.parse.urljoin(base_url, href)
        lower = full_url.lower()

        # Direct PDF links
        if lower.endswith(".pdf"):
            score = 5
            # Boost paper-related PDFs
            if any(kw in lower for kw in ["paper", "main", "final", "preprint", "arxiv"]):
                score += 10
            # Penalize supplemental materials
            if any(kw in lower for kw in ["supp", "appendix", "poster", "slides"]):
                score -= 5
            candidates.append((score, full_url))

        # arXiv abs links (we can convert to PDF)
        m = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", full_url)
        if m:
            pdf_url = f"https://arxiv.org/pdf/{m.group(1)}.pdf"
            candidates.append((15, pdf_url))

    if not candidates:
        return None

    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Webpage abstract extractor
# ---------------------------------------------------------------------------

def _extract_abstract_from_html(page_html: str) -> str | None:
    """Try to find the abstract in HTML content."""
    # Strategy 1: dedicated abstract div/section
    for pattern in [
        r'<(?:div|section|p)[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</(?:div|section|p)>',
        r'<(?:div|section)[^>]*id="[^"]*abstract[^"]*"[^>]*>(.*?)</(?:div|section)>',
    ]:
        m = re.search(pattern, page_html, re.S | re.I)
        if m:
            text = _strip_tags(m.group(1)).strip()
            if len(text) > 80:
                return text

    # Strategy 2: "Abstract" heading
    m = re.search(
        r"<h[1-6][^>]*>\s*Abstract\s*</h[1-6]>\s*(.*?)(?:<h[1-6]|<div\s+class=\"|<section)",
        page_html, re.S | re.I,
    )
    if m:
        text = _strip_tags(m.group(1)).strip()
        if len(text) > 80:
            return text

    # Strategy 3: plain text search
    text = _strip_tags(page_html)
    m = re.search(
        r"(?:^|\n)\s*Abstract\s*\n(.*?)(?:\n\s*(?:1[\s.]|Introduction|Keywords|BibTeX|Citation|Video|Results|Code|Acknowledgment|Reference))",
        text, re.S | re.I,
    )
    if m:
        abstract = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(abstract) > 80:
            return abstract

    # Strategy 4: meta description
    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']{80,})["\']',
        page_html, re.I,
    )
    if m:
        desc = html_mod.unescape(m.group(1)).strip()
        if len(desc) > 100:
            return desc

    return None


def _strip_tags(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

def _render_thumbnail(pdf_bytes: bytes) -> bytes | None:
    """Render PDF first page to JPEG thumbnail."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        scale = THUMB_WIDTH / page.rect.width
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        jpeg = pix.tobytes(output="jpeg", jpg_quality=85)
        doc.close()
        return jpeg
    except Exception as e:
        print(f"    [render error] {e}")
        return None


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract text from first N pages of PDF."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for i in range(min(MAX_TEXT_PAGES, len(doc))):
            pages.append(doc[i].get_text())
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        print(f"    [text extract error] {e}")
        return ""


def _find_abstract_in_text(text: str) -> str | None:
    """Locate abstract in extracted PDF text."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    m = re.search(
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*[:\-—.]?\s*\n(.*?)(?:\n\s*(?:1[\s.]|I\s|Introduction|INTRODUCTION|Keywords|Index\s[Tt]erms|CCS\s|1\s+Introduction|ACM\s))",
        text, re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            # Clean up
            abstract = re.sub(r"-\s*\n\s*", "", abstract)
            abstract = re.sub(r"\n(?!\n)", " ", abstract)
            abstract = re.sub(r"\s+", " ", abstract)
            return abstract.strip()

    m = re.search(
        r"(?:ABSTRACT|Abstract)\s*[.—:\-]\s*(.+?)(?:\n\s*(?:1[\s.]|Introduction|Keywords|Index\s[Tt]erms))",
        text, re.DOTALL,
    )
    if m:
        abstract = m.group(1).strip()
        if len(abstract) > 80:
            abstract = re.sub(r"-\s*\n\s*", "", abstract)
            abstract = re.sub(r"\n(?!\n)", " ", abstract)
            abstract = re.sub(r"\s+", " ", abstract)
            return abstract.strip()

    return None


# ---------------------------------------------------------------------------
# Webpage image fallback (when no PDF is found)
# ---------------------------------------------------------------------------

def _find_teaser_image(html: str, base_url: str) -> str | None:
    """Find the best candidate teaser image from a webpage."""
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)

    # Check og:image
    og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not og:
        og = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
    if og:
        imgs.insert(0, og.group(1))

    candidates = []
    for src in imgs:
        lower = src.lower()
        if any(skip in lower for skip in [
            "logo", "icon", "favicon", "badge", "button",
            "tracking", "pixel", "analytics", "1x1", "spacer",
            ".svg", "data:image", "github.com/favicon",
        ]):
            continue
        full_url = urllib.parse.urljoin(base_url, src)
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
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def _image_to_jpeg(img_bytes: bytes) -> bytes | None:
    """Convert image bytes to JPEG thumbnail via PDF page rendering.

    Renders the image through a PDF page to handle alpha channels, CMYK,
    and other colour-space issues transparently.
    """
    try:
        # Probe dimensions via Pixmap
        try:
            pix = fitz.Pixmap(img_bytes)
            w, h = pix.width, pix.height
        except Exception:
            return None
        if w < 50 or h < 50:
            return None

        # Render image through a temporary PDF page (strips alpha, converts CMYK)
        doc = fitz.open()
        page = doc.new_page(width=w, height=h)
        page.insert_image(fitz.Rect(0, 0, w, h), stream=img_bytes)
        scale = min(THUMB_WIDTH / w, 1.0)
        pix2 = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        jpeg = pix2.tobytes(output="jpeg", jpg_quality=85)
        doc.close()
        return jpeg
    except Exception as e:
        print(f"    [image convert error] {e}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    entries = parse_bibliography_with_metadata(BIB_FILE)
    entries = [
        e for e in entries
        if any(e.get(f, "") and e.get(f, "").lower() != "none"
               for f in ("webpage", "code", "video", "arxiv"))
    ]

    print(f"Total papers: {len(entries)}")

    # Find what's missing
    need_thumb = []
    need_abstract = []
    need_text = []
    for e in entries:
        key = e["key"]
        if not (THUMB_DIR / f"{key}.jpg").exists():
            need_thumb.append(key)
        abstract = e.get("abstract", "") or load_abstract_file(key)
        if not abstract:
            need_abstract.append(key)
        if not (TEXT_DIR / f"{key}.txt").exists():
            need_text.append(key)

    need_thumb_set = set(need_thumb)
    need_abstract_set = set(need_abstract)
    need_text_set = set(need_text)
    need_anything = need_thumb_set | need_abstract_set | need_text_set

    print(f"Missing thumbnails: {len(need_thumb)}")
    print(f"Missing abstracts: {len(need_abstract)}")
    print(f"Missing text: {len(need_text)}")
    print(f"Papers needing any fetch: {len(need_anything)}\n")

    to_process = [e for e in entries if e["key"] in need_anything]

    stats = {"thumb": 0, "abstract": 0, "text": 0, "pdf_found": 0, "web_img": 0}

    for i, e in enumerate(to_process):
        key = e["key"]
        print(f"[{i+1}/{len(to_process)}] {key}")

        thumb_path = THUMB_DIR / f"{key}.jpg"
        abstract_path = ABSTRACT_DIR / f"{key}.txt"
        text_path = TEXT_DIR / f"{key}.txt"

        has_thumb = thumb_path.exists()
        has_abstract = key not in need_abstract_set
        has_text = text_path.exists()

        pdf_bytes = None
        page_html = None
        text = ""

        # --- Strategy 1: Try arXiv PDF ---
        pdf_url = _get_arxiv_pdf_url(e) or _get_direct_pdf_url(e)
        if pdf_url:
            print(f"    PDF: {pdf_url[:80]}")
            pdf_bytes = _download(pdf_url, accept="application/pdf,*/*")
            if pdf_bytes and pdf_bytes[:5].startswith(b"%PDF"):
                stats["pdf_found"] += 1
            else:
                pdf_bytes = None

        # --- Strategy 2: Scan webpage for PDF link ---
        if not pdf_bytes:
            webpage = e.get("webpage", "")
            if webpage and webpage.lower() != "none":
                print(f"    Scanning webpage: {webpage[:80]}")
                page_html = _fetch_page(webpage)
                if page_html:
                    found_pdf_url = _find_pdf_on_webpage(page_html, webpage)
                    if found_pdf_url:
                        print(f"    Found PDF: {found_pdf_url[:80]}")
                        pdf_bytes = _download(found_pdf_url, accept="application/pdf,*/*")
                        if pdf_bytes and pdf_bytes[:5].startswith(b"%PDF"):
                            stats["pdf_found"] += 1
                        else:
                            pdf_bytes = None

        # --- Process PDF if we got one ---
        if pdf_bytes:
            # Thumbnail
            if not has_thumb:
                jpeg = _render_thumbnail(pdf_bytes)
                if jpeg:
                    thumb_path.write_bytes(jpeg)
                    stats["thumb"] += 1
                    has_thumb = True
                    print(f"    -> thumbnail saved ({len(jpeg)//1024} KB)")

            # Abstract
            if not has_abstract:
                text = _extract_text(pdf_bytes)
                abstract = _find_abstract_in_text(text) if text else None
                if abstract:
                    abstract_path.write_text(abstract, encoding="utf-8")
                    stats["abstract"] += 1
                    has_abstract = True
                    print(f"    -> abstract saved ({len(abstract)} chars)")

            # Full text for classification
            if not has_text:
                if not text:
                    text = _extract_text(pdf_bytes)
                if text and len(text) > 200:
                    full = f"Title: {e['title']}\n\n{text}"
                    text_path.write_text(full, encoding="utf-8")
                    stats["text"] += 1
                    has_text = True
                    print(f"    -> full text saved ({len(text)} chars)")

        # --- Fallback: webpage image for thumbnail ---
        if not has_thumb:
            webpage = e.get("webpage", "")
            if webpage and webpage.lower() != "none":
                if not page_html:
                    page_html = _fetch_page(webpage)
                if page_html:
                    # Try to get abstract from webpage too
                    if not has_abstract:
                        abstract = _extract_abstract_from_html(page_html)
                        if abstract:
                            abstract_path.write_text(abstract, encoding="utf-8")
                            stats["abstract"] += 1
                            has_abstract = True
                            print(f"    -> abstract from webpage ({len(abstract)} chars)")

                    # Try teaser image
                    img_url = _find_teaser_image(page_html, webpage)
                    if img_url:
                        print(f"    Teaser: {img_url[:80]}")
                        img_data = _download(img_url, accept="image/*,*/*")
                        if img_data and len(img_data) > 1000:
                            jpeg = _image_to_jpeg(img_data)
                            if jpeg:
                                thumb_path.write_bytes(jpeg)
                                stats["web_img"] += 1
                                has_thumb = True
                                print(f"    -> teaser thumbnail saved ({len(jpeg)//1024} KB)")

        if not has_thumb and not has_abstract and not has_text:
            print("    -> nothing found")

        # Rate limit
        time.sleep(1.0)

    print(f"\n{'='*60}")
    print(f"Done!")
    print(f"  PDFs found: {stats['pdf_found']}")
    print(f"  Thumbnails from PDFs: {stats['thumb']}")
    print(f"  Thumbnails from webpage images: {stats['web_img']}")
    print(f"  Abstracts saved: {stats['abstract']}")
    print(f"  Full texts saved: {stats['text']}")

    # Final counts
    total_thumbs = sum(1 for e in entries if (THUMB_DIR / f"{e['key']}.jpg").exists())
    total_abstracts = sum(1 for e in entries
                         if e.get("abstract") or load_abstract_file(e["key"]))
    print(f"\nTotal thumbnails: {total_thumbs}/{len(entries)}")
    print(f"Total abstracts: {total_abstracts}/{len(entries)}")


if __name__ == "__main__":
    main()
