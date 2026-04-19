#!/usr/bin/env python3
"""
Fetch first-page thumbnails and abstracts for each BibTeX entry that has an Arxiv link.

Parallelized version using the SAME thumb_name() as the Publications HTML
generator, so thumbnail filenames match.

- Downloads the PDF (if possible)
- Extracts the first page
- Downsamples twice (1/4 width & height overall)
- Saves as JPEG
- Fetches abstract from arXiv API and saves as .txt

Requires:
    pip install requests pdf2image pillow
System:
    poppler must be installed for pdf2image to work.

Usage:
    python scripts/fetch_thumbnails.py
"""

from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
ABSTRACT_DIR.mkdir(parents=True, exist_ok=True)

THUMB_EXT = ".jpg"  # extension produced by pdf2image (converted to .webp afterwards)


def thumb_exists(out_dir, fname):
    """A paper is considered fetched if either .webp (preferred) or .jpg exists."""
    return (out_dir / f"{fname}.webp").exists() or (out_dir / f"{fname}.jpg").exists()

# Make tables_src importable
sys.path.insert(0, str(SRC))

# Import parser AND the filename sanitizer from build_publications.py
# If thumb_name is not available for some reason, fall back to a local one.
try:
    from build_publications import (
        parse_bibliography_with_metadata,
        thumb_name,  # IMPORTANT: use the SAME sanitizer as HTML
    )  # type: ignore
except ImportError:
    from build_publications import parse_bibliography_with_metadata  # type: ignore

    def thumb_name(key: str) -> str:
        """Fallback sanitizer: allow alphanumeric, underscore, hyphen, dot; replace all else."""
        return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def normalize_arxiv_pdf_url(url: str) -> str:
    """
    Normalize various Arxiv URLs to a direct PDF URL.

    Examples:
        https://arxiv.org/abs/1234.5678      -> https://arxiv.org/pdf/1234.5678.pdf
        https://arxiv.org/pdf/1234.5678      -> https://arxiv.org/pdf/1234.5678.pdf
        https://arxiv.org/pdf/1234.5678.pdf  -> unchanged
    """
    url = url.strip()
    if not url:
        return url

    # Already a direct PDF
    if url.lower().endswith(".pdf"):
        return url

    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+(?:v[0-9]+)?)", url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"

    # Fallback: just return the original; might already be some PDF link
    return url


def extract_arxiv_id(url: str) -> str:
    """Extract arXiv ID from a URL."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+(?:v[0-9]+)?)", url)
    return m.group(1) if m else ""


def fetch_abstracts_batch(tasks: list, out_dir: Path, batch_size: int = 20) -> None:
    """Fetch abstracts from arXiv API in batches (up to batch_size IDs per request)."""
    import requests
    import xml.etree.ElementTree as ET
    import time

    # Build mapping: arxiv_id -> (key, out_path)
    id_to_info = {}
    for key, arxiv_url in tasks:
        arxiv_id = extract_arxiv_id(arxiv_url)
        if arxiv_id:
            fname = thumb_name(key)
            id_to_info[arxiv_id] = (key, out_dir / f"{fname}.txt")

    ids = list(id_to_info.keys())
    total = len(ids)
    saved = 0

    for i in range(0, total, batch_size):
        batch = ids[i : i + batch_size]
        id_list = ",".join(batch)

        try:
            api_url = f"https://export.arxiv.org/api/query?id_list={id_list}&max_results={len(batch)}"
            resp = requests.get(api_url, timeout=30)
            resp.raise_for_status()

            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                # Extract arXiv ID from the entry's <id> tag
                entry_id_el = entry.find("atom:id", ns)
                if entry_id_el is None or not entry_id_el.text:
                    continue
                m = re.search(r"(\d+\.\d+)", entry_id_el.text)
                if not m:
                    continue
                arxiv_id = m.group(1)

                if arxiv_id not in id_to_info:
                    continue

                key, out_path = id_to_info[arxiv_id]
                summary = entry.find("atom:summary", ns)
                if summary is not None and summary.text:
                    abstract = summary.text.strip()
                    abstract = re.sub(r"\s+", " ", abstract)
                    out_path.write_text(abstract, encoding="utf-8")
                    saved += 1

            print(f"📝 Batch {i // batch_size + 1}: fetched {min(i + batch_size, total)}/{total} abstracts")
        except Exception as e:
            print(f"⚠️ Batch {i // batch_size + 1} error: {e}")

        # Be nice to arXiv API - they recommend 3s between requests
        if i + batch_size < total:
            time.sleep(5)

    print(f"📝 Saved {saved} abstracts total")


def ensure_thumbnail(key: str, arxiv_url: str, out_dir: Path) -> None:
    """
    Fetch PDF from arxiv_url, extract the first page as JPEG thumbnail,
    downsample twice, and save it to:

        assets/img/thumbnails/<thumb_name(key)>.jpg
    """
    if not arxiv_url or arxiv_url.lower() == "none":
        return

    # Use sanitized filename (MUST match Publications HTML)
    fname = thumb_name(key)  # e.g. "MyPaper_2024"
    out_path = out_dir / f"{fname}{THUMB_EXT}"

    if thumb_exists(out_dir, fname):
        # Thumbnail (.jpg or .webp) already exists
        return

    try:
        import requests
        from pdf2image import convert_from_bytes
        from PIL import Image
    except Exception:
        print("⚠️ Install `requests`, `pdf2image` and `Pillow` (and poppler) to enable thumbnails.")
        return

    pdf_url = normalize_arxiv_pdf_url(arxiv_url)

    try:
        print(f"📄 [{key}] Downloading PDF from {pdf_url}")
        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        data = resp.content

        # Basic sanity checks: is this actually a PDF?
        looks_like_pdf = data.lstrip().startswith(b"%PDF")
        if content_type and content_type not in (
            "application/pdf",
            "application/x-pdf",
            "application/octet-stream",
        ):
            if not looks_like_pdf:
                print(
                    f"⚠️ [{key}] URL does not look like a PDF "
                    f"(Content-Type: {content_type!r}); skipping thumbnail."
                )
                return
        else:
            # Even if content-type claims to be PDF, verify header
            if not looks_like_pdf:
                print(
                    f"⚠️ [{key}] Response is not a valid PDF (missing %PDF header); skipping thumbnail."
                )
                return

        pages = convert_from_bytes(data, first_page=1, last_page=1)
        if not pages:
            print(f"⚠️ [{key}] No pages returned from PDF")
            return

        img = pages[0]

        # Ensure we are in RGB for JPEG
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Downsample twice (each time by factor 2 → overall 1/4 size)
        for _ in range(1):
            w, h = img.size
            if w <= 1 or h <= 1:
                break
            img = img.resize(
                (max(1, w // 2), max(1, h // 2)),
                resample=Image.LANCZOS,
            )

        # Save as compressed JPEG
        img.save(out_path, format="JPEG", quality=85, optimize=True, progressive=True)
        print(f"✅ [{key}] Saved thumbnail as {out_path.name}")
    except Exception as e:
        print(f"⚠️ [{key}] Thumbnail error: {e}")


def main() -> None:
    entries = parse_bibliography_with_metadata(SRC / "bibliography.bib")

    # Collect keys with Arxiv links that are missing thumbnails or abstracts
    thumb_tasks = []
    abstract_tasks = []
    for e in entries:
        key = e["key"]
        arxiv = (e.get("arxiv", "") or "").strip()
        if not arxiv or arxiv.lower() == "none":
            continue

        fname = thumb_name(key)
        if not thumb_exists(THUMB_DIR, fname):
            thumb_tasks.append((key, arxiv))
        if not (ABSTRACT_DIR / f"{fname}.txt").exists():
            abstract_tasks.append((key, arxiv))

    if not thumb_tasks and not abstract_tasks:
        print("Nothing to do. All thumbnails and abstracts present or no Arxiv links.")
        return

    print(f"🔧 Thumbnails to fetch: {len(thumb_tasks)}, Abstracts to fetch: {len(abstract_tasks)}")

    # Fetch abstracts in batches (arXiv API supports multiple IDs per request)
    if abstract_tasks:
        fetch_abstracts_batch(abstract_tasks, ABSTRACT_DIR)

    # Parallel thumbnail download + conversion
    if thumb_tasks:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {
                ex.submit(ensure_thumbnail, key, arxiv, THUMB_DIR): key
                for key, arxiv in thumb_tasks
            }
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"⚠️ Unexpected worker error for {key}: {e}")

    print("🎉 All thumbnails and abstracts processed.")


if __name__ == "__main__":
    main()
