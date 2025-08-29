#!/usr/bin/env python3
"""
Check that thumbnails and abstracts exist for all publication entries.

Scans publications.json and reports entries missing thumbnail images
or abstract text files.

Usage:
    python scripts/check_assets.py
    python scripts/check_assets.py --thumbnails-only
    python scripts/check_assets.py --github-output /tmp/missing-assets.md

Exit codes: 0 = all present, 1 = missing assets found
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
PUB_JSON = ROOT / "assets" / "data" / "publications.json"


def _sanitize_key(key: str) -> str:
    """Match the thumb_name sanitizer used by fetch_thumbnails.py."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def check_assets(
    thumbnails: bool = True, abstracts: bool = True
) -> tuple[List[dict], List[dict]]:
    """Return (missing_thumbnails, missing_abstracts) as lists of entry dicts."""
    with open(PUB_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    missing_thumbs: List[dict] = []
    missing_abstracts: List[dict] = []

    for entry in entries:
        arxiv = (entry.get("links") or {}).get("arxiv")
        if not arxiv:
            continue

        fname = _sanitize_key(entry["key"])

        if thumbnails:
            thumb_path = THUMB_DIR / f"{fname}.jpg"
            if not thumb_path.exists():
                missing_thumbs.append(entry)

        if abstracts:
            abstract_path = ABSTRACT_DIR / f"{fname}.txt"
            if not abstract_path.exists():
                missing_abstracts.append(entry)

    return missing_thumbs, missing_abstracts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check for missing thumbnails and abstracts"
    )
    parser.add_argument(
        "--thumbnails-only", action="store_true",
        help="Only check thumbnails (skip abstracts)",
    )
    parser.add_argument(
        "--github-output",
        help="Path to write GitHub-flavored markdown report",
    )
    args = parser.parse_args()

    check_abstracts = not args.thumbnails_only
    missing_thumbs, missing_abstracts = check_assets(
        thumbnails=True, abstracts=check_abstracts
    )

    if missing_thumbs:
        print(f"Missing thumbnails ({len(missing_thumbs)}):")
        for e in missing_thumbs:
            print(f"  - {e['key']} ({e.get('year', '?')})")
    else:
        print("All thumbnails present.")

    if check_abstracts:
        if missing_abstracts:
            print(f"\nMissing abstracts ({len(missing_abstracts)}):")
            for e in missing_abstracts:
                print(f"  - {e['key']} ({e.get('year', '?')})")
        else:
            print("All abstracts present.")

    if args.github_output:
        _write_github_report(args.github_output, missing_thumbs, missing_abstracts)

    has_missing = bool(missing_thumbs) or (check_abstracts and bool(missing_abstracts))
    return 1 if has_missing else 0


def _write_github_report(
    path: str,
    missing_thumbs: List[dict],
    missing_abstracts: List[dict],
) -> None:
    """Write markdown report for GitHub issue body."""
    lines: List[str] = []

    if not missing_thumbs and not missing_abstracts:
        lines.append("All assets are present. No action needed.")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        return

    lines.append("The following entries are missing assets. "
                  "Run `./deploy.sh` to fetch them, then commit the results.")
    lines.append("")

    if missing_thumbs:
        lines.append(f"### Missing thumbnails ({len(missing_thumbs)})")
        lines.append("")
        for e in missing_thumbs:
            arxiv = (e.get("links") or {}).get("arxiv", "")
            lines.append(f"- `{e['key']}` — {e.get('title', '')} ({e.get('year', '?')}) [{arxiv}]")
        lines.append("")

    if missing_abstracts:
        lines.append(f"### Missing abstracts ({len(missing_abstracts)})")
        lines.append("")
        for e in missing_abstracts:
            lines.append(f"- `{e['key']}` ({e.get('year', '?')})")
        lines.append("")

    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
