#!/usr/bin/env python3
"""
Validate new/changed entries in publications.json.

Checks schema, venues, links, duplicates, and diffs against a base file.

Usage:
    # Validate a single file
    python scripts/validate_new_entries.py assets/data/publications.json

    # Compare base (main) vs PR version
    python scripts/validate_new_entries.py --base main.json --pr pr.json

Exit codes: 0 = pass, 1 = failures found
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_publications import _BIB_STRINGS, _VENUE_OVERRIDES

# ---------------------------------------------------------------------------
# Known venues: union of abbr.bib abbreviations, venue overrides, and
# the dropdown options from add-entry.html
# ---------------------------------------------------------------------------

# Extract short venue names from abbr.bib parenthetical abbreviations
_ABBR_VENUES: Set[str] = set()
for _val in _BIB_STRINGS.values():
    m = re.search(r"\(([^)]+)\)\s*$", _val)
    if m:
        _ABBR_VENUES.add(m.group(1))

# Collect override target values
_OVERRIDE_VENUES: Set[str] = set(_VENUE_OVERRIDES.values())

# Dropdown venues from add-entry.html
_DROPDOWN_VENUES: Set[str] = {
    "CVPR", "ECCV", "ICCV", "TOG (SIGGRAPH)", "SIGGRAPH Asia",
    "NeurIPS", "ICLR", "ICML", "AAAI", "3DV", "WACV", "BMVC", "arXiv",
}

# Additional venues that appear in the current dataset
_DATASET_VENUES: Set[str] = {
    "SIGGRAPH", "SIGGRAPH MIG", "SIGGRAPH Real-Time Live!",
    "SIGGRAPH Posters", "TOG", "TOG (SIGGRAPH Asia)", "PACMCGIT",
    "CGF", "TVCG", "TPAMI", "SCA", "ACM Multimedia", "ACM UIST",
    "ACM I3D", "MIG", "RSS", "ICME", "ICIP", "Computer Science Review",
    "Visual Informatics", "PLOS ONE", "JVCI",
}

KNOWN_VENUES: Set[str] = _ABBR_VENUES | _OVERRIDE_VENUES | _DROPDOWN_VENUES | _DATASET_VENUES
# Remove empty string if present
KNOWN_VENUES.discard("")

REQUIRED_FIELDS = {
    "key", "title", "authors", "year", "venue",
    "entry_type", "links", "classification", "note", "skip_reason",
}
REQUIRED_LINK_KEYS = {"webpage", "code", "video", "arxiv"}

MIN_YEAR = 1990
MAX_YEAR = 2030


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_for_comparison(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class ValidationResult:
    """Collects errors and warnings."""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.ok and not self.warnings:
            lines.append("All checks passed.")
        elif self.ok:
            lines.append("Validation passed with warnings.")
        else:
            lines.append("Validation FAILED.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def validate_schema(entry: dict, result: ValidationResult) -> None:
    """Check required fields, types, and sub-structure."""
    key = entry.get("key", "<unknown>")

    for field in REQUIRED_FIELDS:
        if field not in entry:
            result.error(f"[{key}] Missing required field: {field}")

    # Non-empty string checks for core fields
    for field in ("key", "title", "authors", "year"):
        val = entry.get(field)
        if val is not None and not isinstance(val, str):
            result.error(f"[{key}] '{field}' must be a string, got {type(val).__name__}")
        elif not val or (isinstance(val, str) and not val.strip()):
            result.error(f"[{key}] '{field}' must not be empty")

    # entry_type should be a non-empty string
    entry_type = entry.get("entry_type")
    if entry_type is not None and not isinstance(entry_type, str):
        result.error(f"[{key}] 'entry_type' must be a string, got {type(entry_type).__name__}")
    elif not entry_type or (isinstance(entry_type, str) and not entry_type.strip()):
        result.error(f"[{key}] 'entry_type' must not be empty")

    # links: must be a dict with the 4 required sub-keys
    links = entry.get("links")
    if not isinstance(links, dict):
        result.error(f"[{key}] 'links' must be an object, got {type(links).__name__}")
    else:
        for lk in REQUIRED_LINK_KEYS:
            if lk not in links:
                result.error(f"[{key}] Missing link key: {lk}")
        # At least one link must be non-null
        has_link = any(
            isinstance(links.get(lk), str) and links[lk].strip()
            for lk in REQUIRED_LINK_KEYS
        )
        if not has_link:
            result.error(f"[{key}] At least one link (webpage/code/video/arxiv) must be provided")

    # classification structure
    cls = entry.get("classification")
    if cls is not None:
        if not isinstance(cls, dict):
            result.error(f"[{key}] 'classification' must be an object or null")
        else:
            if "table_type" not in cls:
                result.error(f"[{key}] classification missing 'table_type'")
            elif cls["table_type"] not in ("avatar", "assets"):
                result.error(f"[{key}] classification 'table_type' must be 'avatar' or 'assets', got '{cls['table_type']}'")
            if "fields" not in cls:
                result.error(f"[{key}] classification missing 'fields'")
            elif not isinstance(cls.get("fields"), dict):
                result.error(f"[{key}] classification 'fields' must be an object")

    # year format validation (type errors already caught above)
    year = entry.get("year", "")
    if isinstance(year, str) and year.strip():
        if not re.match(r"^\d{4}$", year):
            result.error(f"[{key}] Year '{year}' is not a 4-digit string")
        else:
            y = int(year)
            if y < MIN_YEAR or y > MAX_YEAR:
                result.error(f"[{key}] Year {y} outside range {MIN_YEAR}-{MAX_YEAR}")


def validate_venue(entry: dict, result: ValidationResult) -> None:
    """Warn on unknown venues."""
    key = entry.get("key", "<unknown>")
    venue = entry.get("venue", "")
    if venue and venue not in KNOWN_VENUES:
        result.warn(f"[{key}] Unknown venue: '{venue}'")


def validate_links(entry: dict, result: ValidationResult, check_http: bool = False) -> None:
    """Validate link URLs format and optionally check reachability."""
    key = entry.get("key", "<unknown>")
    links = entry.get("links")
    if not isinstance(links, dict):
        return

    for lk, lv in links.items():
        if lv is None:
            continue
        if not isinstance(lv, str):
            result.error(f"[{key}] Link '{lk}' should be a string or null")
            continue
        if not lv.startswith("https://") and not lv.startswith("http://"):
            result.warn(f"[{key}] Link '{lk}' does not start with http(s)://: '{lv}'")
            continue

        if check_http:
            _check_url(key, lk, lv, result)


def _check_url(key: str, link_name: str, url: str, result: ValidationResult) -> None:
    """HTTP HEAD check on a URL (warn only, some sites block HEAD)."""
    try:
        import requests
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code >= 400:
            result.warn(f"[{key}] Link '{link_name}' returned HTTP {resp.status_code}: {url}")
    except ImportError:
        result.warn("requests library not available, skipping HTTP link checks")
    except Exception as e:
        result.warn(f"[{key}] Link '{link_name}' unreachable: {e}")


def validate_duplicates(
    entries: List[dict],
    existing_keys: Set[str],
    existing_titles: Dict[str, str],
    result: ValidationResult,
) -> None:
    """Check for duplicate keys and fuzzy-similar titles."""
    for entry in entries:
        key = entry.get("key", "")
        if key in existing_keys:
            result.error(f"[{key}] Duplicate key: already exists in base data")

        title = entry.get("title", "")
        if title:
            norm = _normalize_for_comparison(title)
            for ex_key, ex_norm in existing_titles.items():
                if ex_key == key:
                    continue
                if norm == ex_norm:
                    result.warn(
                        f"[{key}] Very similar title to existing entry '{ex_key}': "
                        f"'{title}'"
                    )


# ---------------------------------------------------------------------------
# Diff detection
# ---------------------------------------------------------------------------

def compute_diff(
    base_entries: List[dict], pr_entries: List[dict]
) -> tuple[List[dict], List[dict], List[dict]]:
    """Compare base vs PR entries. Returns (new, modified, removed)."""
    base_by_key = {e["key"]: e for e in base_entries}
    pr_by_key = {e["key"]: e for e in pr_entries}

    base_keys = set(base_by_key.keys())
    pr_keys = set(pr_by_key.keys())

    new_keys = pr_keys - base_keys
    removed_keys = base_keys - pr_keys
    common_keys = base_keys & pr_keys

    new = [pr_by_key[k] for k in sorted(new_keys)]
    removed = [base_by_key[k] for k in sorted(removed_keys)]

    modified = []
    for k in sorted(common_keys):
        if base_by_key[k] != pr_by_key[k]:
            modified.append(pr_by_key[k])

    return new, modified, removed


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def validate_file(path: Path, check_http: bool = False) -> ValidationResult:
    """Validate a single publications.json file."""
    result = ValidationResult()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.error(f"Invalid JSON: {e}")
        return result
    except FileNotFoundError:
        result.error(f"File not found: {path}")
        return result

    if not isinstance(data, list):
        result.error("Top-level JSON must be an array")
        return result

    # Check all entries
    seen_keys: Set[str] = set()
    all_titles: Dict[str, str] = {}

    for entry in data:
        validate_schema(entry, result)
        validate_venue(entry, result)
        validate_links(entry, result, check_http=check_http)

        key = entry.get("key", "")
        if key:
            if key in seen_keys:
                result.error(f"[{key}] Duplicate key within file")
            seen_keys.add(key)

        title = entry.get("title", "")
        if title:
            all_titles[key] = _normalize_for_comparison(title)

    return result


def validate_pr(
    base_path: Path, pr_path: Path, check_http: bool = False
) -> tuple[ValidationResult, List[dict], List[dict], List[dict]]:
    """Validate PR changes against base."""
    result = ValidationResult()

    # Load base
    try:
        with open(base_path, "r", encoding="utf-8") as f:
            base_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        result.error(f"Cannot load base file: {e}")
        return result, [], [], []

    # Load PR
    try:
        with open(pr_path, "r", encoding="utf-8") as f:
            pr_data = json.load(f)
    except json.JSONDecodeError as e:
        result.error(f"PR file has invalid JSON: {e}")
        return result, [], [], []
    except FileNotFoundError:
        result.error(f"PR file not found: {pr_path}")
        return result, [], [], []

    if not isinstance(pr_data, list):
        result.error("PR JSON top-level must be an array")
        return result, [], [], []

    # Compute diff
    new_entries, modified_entries, removed_entries = compute_diff(base_data, pr_data)

    # Validate all entries in PR file for schema/venue/links
    seen_keys: Set[str] = set()
    for entry in pr_data:
        validate_schema(entry, result)
        validate_venue(entry, result)
        validate_links(entry, result, check_http=check_http)

        key = entry.get("key", "")
        if key:
            if key in seen_keys:
                result.error(f"[{key}] Duplicate key within PR file")
            seen_keys.add(key)

    # Check new entries for duplicates against base
    base_keys = {e.get("key", "") for e in base_data}
    base_titles = {
        e.get("key", ""): _normalize_for_comparison(e.get("title", ""))
        for e in base_data
        if e.get("title")
    }
    validate_duplicates(new_entries, base_keys, base_titles, result)

    return result, new_entries, modified_entries, removed_entries


def format_entry_summary(entry: dict) -> str:
    """One-line summary of an entry."""
    key = entry.get("key", "?")
    title = entry.get("title", "")
    year = entry.get("year", "")
    venue = entry.get("venue", "")
    parts = [f"**{key}**"]
    if title:
        parts.append(f'"{title}"')
    if year:
        parts.append(f"({year})")
    if venue:
        parts.append(f"[{venue}]")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate publications.json entries"
    )
    parser.add_argument(
        "file", nargs="?",
        help="Single file to validate (standalone mode)",
    )
    parser.add_argument("--base", help="Base file (from main branch)")
    parser.add_argument("--pr", help="PR file to validate against base")
    parser.add_argument(
        "--check-http", action="store_true",
        help="Check links via HTTP HEAD requests (slow)",
    )
    parser.add_argument(
        "--github-output", help="Path to write GitHub Actions summary markdown",
    )
    args = parser.parse_args()

    if args.base and args.pr:
        # PR comparison mode
        result, new_entries, modified, removed = validate_pr(
            Path(args.base), Path(args.pr), check_http=args.check_http
        )

        print("=== Diff Summary ===")
        print(f"  New entries:      {len(new_entries)}")
        print(f"  Modified entries: {len(modified)}")
        print(f"  Removed entries:  {len(removed)}")
        print()

        if new_entries:
            print("New entries:")
            for e in new_entries:
                print(f"  + {format_entry_summary(e)}")
            print()

        if modified:
            print("Modified entries:")
            for e in modified:
                print(f"  ~ {format_entry_summary(e)}")
            print()

        if removed:
            print("Removed entries:")
            for e in removed:
                print(f"  - {format_entry_summary(e)}")
            print()

        print(result.summary())

        # Write GitHub Actions output if requested
        if args.github_output:
            _write_github_summary(
                args.github_output, result, new_entries, modified, removed
            )

    elif args.file:
        # Single file validation
        result = validate_file(Path(args.file), check_http=args.check_http)
        print(result.summary())

    else:
        parser.print_help()
        return 1

    return 0 if result.ok else 1


def _write_github_summary(
    path: str,
    result: ValidationResult,
    new_entries: List[dict],
    modified: List[dict],
    removed: List[dict],
) -> None:
    """Write markdown summary for GitHub Actions PR comment."""
    lines: List[str] = []

    if result.ok:
        lines.append("## Validation: PASSED")
    else:
        lines.append("## Validation: FAILED")

    # Diff summary
    lines.append("")
    lines.append("### Changes detected")
    lines.append(f"- **{len(new_entries)}** new entries")
    lines.append(f"- **{len(modified)}** modified entries")
    lines.append(f"- **{len(removed)}** removed entries")

    if new_entries:
        lines.append("")
        lines.append("### New entries")
        for e in new_entries:
            lines.append(f"- {format_entry_summary(e)}")

    if result.errors:
        lines.append("")
        lines.append("### Errors")
        for e in result.errors:
            lines.append(f"- {e}")

    if result.warnings:
        lines.append("")
        lines.append("### Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("---")
    lines.append("## Post-merge steps (for maintainers)")
    lines.append("After merging, run this to fetch thumbnails, abstracts, and rebuild the site:")
    lines.append("```bash")
    lines.append("./deploy.sh")
    lines.append("```")

    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
