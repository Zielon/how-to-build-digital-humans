#!/usr/bin/env python3
"""
Build publications.html from bibliography.bib.

- Reads tables_src/bibliography.bib
- Parses standard BibTeX fields
- Parses metadata comments:

  % Webpage: https://project
  % Code:    https://github.com/...
  % Video:   https://youtu.be/...
  % Arxiv:   https://arxiv.org/pdf/....

- Loads abstracts from assets/data/abstracts/*.txt (fetched from arXiv)
- Writes tables/publications.html with filter controls and pagination
"""

from __future__ import annotations
from pathlib import Path
import html
import json
import re
from typing import Dict, List

import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from normalize_fields import normalize_fields
TABLES_DIR = ROOT / "tables"
TABLES_DIR.mkdir(exist_ok=True)

BIB_FILE = SRC / "bibliography.bib"
THUMB_DIR = ROOT / "assets" / "img" / "thumbnails"
ABSTRACT_DIR = ROOT / "assets" / "data" / "abstracts"
JSON_FILE = ROOT / "classify" / "final_results.json"
ITEMS_PER_PAGE = 50


def load_classifications() -> tuple:
    """Load JSON classifications and return (classified, skipped, notes) dicts.

    classified: key -> {table_type, category, fields}
    skipped:    key -> reason
    notes:      key -> note string
    """
    classified: Dict[str, Dict[str, str]] = {}
    skipped: Dict[str, str] = {}
    notes: Dict[str, str] = {}
    if not JSON_FILE.exists():
        return classified, skipped, notes
    with JSON_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("avatar_classifications", []):
        key = item["key"]
        fields = normalize_fields(item["fields"])
        contents = fields.get("Contents", "")
        classified[key] = {"table_type": "avatar", "category": _primary_category(contents), "fields": fields}
        if item.get("note"):
            notes[key] = item["note"]
    for item in data.get("assets_classifications", []):
        key = item["key"]
        fields = normalize_fields(item["fields"])
        contents = fields.get("Contents", "")
        classified[key] = {"table_type": "assets", "category": _primary_category(contents), "fields": fields}
        if item.get("note"):
            notes[key] = item["note"]
    for item in data.get("skipped", []):
        skipped[item["key"]] = item.get("reason", "")
    return classified, skipped, notes


def _normalize_single_part(s: str) -> str:
    lower = s.lower().strip()
    if not lower:
        return ""
    if lower in ("head", "head only", "portrait") or lower.startswith("head "):
        return "Face"
    if lower in (
        "full body", "full-body", "body", "upper body",
        "full body (clothed)", "full-body (clothed)",
    ):
        return "Full-body"
    if lower == "face":
        return "Face"
    if lower in ("hands", "hand"):
        return "Hands"
    if lower == "hair":
        return "Hair"
    if lower in ("garment", "garments", "clothing"):
        return "Garment"
    if lower == "teeth":
        return "Teeth"
    if lower == "tongue":
        return "Tongue"
    return ""


def _primary_category(raw: str) -> str:
    """Extract primary category from Contents for filtering."""
    if not raw:
        return ""
    s = re.sub(r"\([^)]*\)", "", raw).strip()
    parts = re.split(r"[,/;]|\s\+\s", s)
    for part in parts:
        mapped = _normalize_single_part(part)
        if mapped:
            return mapped
    return ""



_LATEX_ACCENTS: Dict[str, Dict[str, str]] = {
    '"': {"a": "ä", "e": "ë", "i": "ï", "o": "ö", "u": "ü",
          "A": "Ä", "E": "Ë", "I": "Ï", "O": "Ö", "U": "Ü",
          "ı": "ï"},
    "'": {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "y": "ý",
          "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú", "Y": "Ý"},
    "`": {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
          "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù"},
    "~": {"a": "ã", "n": "ñ", "o": "õ", "A": "Ã", "N": "Ñ", "O": "Õ"},
    "^": {"a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û",
          "A": "Â", "E": "Ê", "I": "Î", "O": "Ô", "U": "Û"},
    "v": {"c": "č", "s": "š", "z": "ž", "r": "ř", "e": "ě",
          "C": "Č", "S": "Š", "Z": "Ž", "R": "Ř", "E": "Ě"},
    "c": {"c": "ç", "s": "ş", "C": "Ç", "S": "Ş"},
    "k": {"a": "ą", "e": "ę", "A": "Ą", "E": "Ę"},
    "H": {"o": "ő", "u": "ű", "O": "Ő", "U": "Ű"},
    "u": {"a": "ă", "A": "Ă"},
}
_LATEX_SPECIAL: Dict[str, str] = {
    "\\ss": "ß",
    "\\l": "ł",
    "\\L": "Ł",
    "\\i": "ı",
    "\\o": "ø",
    "\\O": "Ø",
    "\\aa": "å",
    "\\AA": "Å",
    "\\ae": "æ",
    "\\AE": "Æ",
}


_SUPERSCRIPTS: Dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
}
_SUBSCRIPTS: Dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
}


def _clean_latex(s: str) -> str:
    """Convert LaTeX accent commands to Unicode characters."""
    # {\cmd{X}} patterns  e.g. {\v{s}} -> š, {\"{u}} -> ü
    def _replace_braced(m: re.Match) -> str:
        cmd = m.group(1)
        char = m.group(2)
        return _LATEX_ACCENTS.get(cmd, {}).get(char, char)
    s = re.sub(r"\{\\([\"'`~^vckHu])\{(\w)\}\}", _replace_braced, s)

    # {\"X} patterns  e.g. {\"o} -> ö
    def _replace_short(m: re.Match) -> str:
        cmd = m.group(1)
        char = m.group(2)
        return _LATEX_ACCENTS.get(cmd, {}).get(char, char)
    s = re.sub(r"\{\\([\"'`~^])([\w])\}", _replace_short, s)

    # Accent + \i (dotless i) patterns:  {\"\i} -> ï,  {\'\i} -> í, etc.
    def _replace_accent_dotless_i(m: re.Match) -> str:
        cmd = m.group(1)
        return _LATEX_ACCENTS.get(cmd, {}).get("i", "i")
    s = re.sub(r"\{\\([\"'`~^])\\i\}", _replace_accent_dotless_i, s)

    # Special commands: {\ss} -> ß, {\l} -> ł, etc.
    def _replace_special(m: re.Match) -> str:
        return _LATEX_SPECIAL.get(m.group(1), m.group(1))
    s = re.sub(r"\{(\\(?:ss|l|L|i|o|O|aa|AA|ae|AE))\}", _replace_special, s)

    # Bare accent commands without braces:  \"o -> ö,  \'a -> á,  \v{s} -> š
    def _replace_bare_accent_braced(m: re.Match) -> str:
        cmd = m.group(1)
        char = m.group(2)
        return _LATEX_ACCENTS.get(cmd, {}).get(char, char)
    s = re.sub(r"\\([\"'`~^vckHu])\{(\w)\}", _replace_bare_accent_braced, s)

    def _replace_bare_accent(m: re.Match) -> str:
        cmd = m.group(1)
        char = m.group(2)
        return _LATEX_ACCENTS.get(cmd, {}).get(char, char)
    s = re.sub(r"\\([\"'`~^])(\w)", _replace_bare_accent, s)

    # Bare special commands without braces:  \ss -> ß, etc.
    def _replace_bare_special(m: re.Match) -> str:
        return _LATEX_SPECIAL.get(m.group(0), m.group(0))
    s = re.sub(r"\\(?:ss|l|L|i|o|O|aa|AA|ae|AE)\b", _replace_bare_special, s)

    # Formatting commands: \emph{X} -> X, \textbf{X} -> X, \mbox{X} -> X, etc.
    s = re.sub(r"\\(?:emph|textbf|textit|texttt|textrm|textsc|mbox|mathrm|mathbf|mathcal)\{([^}]*)\}", r"\1", s)

    # Escaped special characters: \& -> &, \% -> %, \# -> #, \_ -> _, \^ -> ^
    s = re.sub(r"\\([&%#_^])", r"\1", s)

    # Math-mode superscripts: ^{3} -> ³, ^3 -> ³
    def _replace_super(m: re.Match) -> str:
        content = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        return "".join(_SUPERSCRIPTS.get(c, c) for c in content) if content else "^"
    s = re.sub(r"\^\{([^}]*)\}|\^(\w)", _replace_super, s)

    # Math-mode subscripts: _{3} -> ₃, _3 -> ₃ (only when preceded by word char)
    def _replace_sub(m: re.Match) -> str:
        content = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        return "".join(_SUBSCRIPTS.get(c, c) for c in content)
    s = re.sub(r"_\{([^}]*)\}|(?<=\w)_(\d)", _replace_sub, s)

    # Inline math delimiters: \( ... \) and $ ... $ -> just the content
    s = re.sub(r"\\\((.+?)\\\)", r"\1", s)
    s = re.sub(r"\$([^$]+)\$", r"\1", s)

    # Strip remaining braces
    s = s.replace("{", "").replace("}", "")
    # Collapse runs of whitespace (from multi-line BibTeX values)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def parse_bibliography_with_metadata(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    entries: List[Dict[str, str]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    i = 0

    def parse_fields(block: str) -> Dict[str, str]:
        body = block.split("\n", 1)[1] if "\n" in block else ""
        fields: Dict[str, str] = {}
        # Match field name and '='
        for m in re.finditer(r"(\w+)\s*=\s*", body):
            name = m.group(1).strip().lower()
            rest = body[m.end():]
            if not rest:
                continue
            delim = rest[0]
            if delim == "{":
                # Brace-delimited: find matching closing brace
                depth = 0
                end = 0
                for j, ch in enumerate(rest):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = j
                            break
                value = rest[1:end]
            elif delim == '"':
                # Quote-delimited: find next unescaped quote
                close = rest.find('"', 1)
                value = rest[1:close] if close > 0 else ""
            else:
                # Bare identifier (BibTeX macro): read until comma or newline
                end_bare = re.search(r"[,\s\n}]", rest)
                if end_bare:
                    value = rest[:end_bare.start()].strip()
                else:
                    continue
            value = value.strip().replace("\n", " ")
            fields[name] = _clean_latex(value)
        return fields

    # Metadata collected from preceding % lines,
    # applied to the *next* BibTeX entry we see.
    webpage = code = video = arxiv = ""

    while i < n:
        line = lines[i]
        stripped = line.lstrip()

        # 1) Metadata comments (apply to the NEXT entry)
        if stripped.startswith("%"):
            meta_line = stripped[1:].strip()
            for label, var in [
                ("Webpage:", "webpage"),
                ("Code:", "code"),
                ("Video:", "video"),
                ("Arxiv:", "arxiv"),
            ]:
                if meta_line.startswith(label):
                    value = meta_line[len(label):].strip()
                    if var == "webpage":
                        webpage = value
                    elif var == "code":
                        code = value
                    elif var == "video":
                        video = value
                    elif var == "arxiv":
                        arxiv = value
            i += 1
            continue

        # 2) BibTeX entry
        if stripped.startswith("@"):
            entry_lines = [line]
            brace_depth = line.count("{") - line.count("}")
            i += 1
            while i < n and brace_depth > 0:
                entry_lines.append(lines[i])
                brace_depth += lines[i].count("{") - lines[i].count("}")
                i += 1

            entry_text = "\n".join(entry_lines)
            m = re.match(r"@(\w+)\{([^,]+),", entry_lines[0])
            entry_type = m.group(1) if m else ""
            key = m.group(2).strip() if m else ""

            fields = parse_fields(entry_text)
            title = fields.get("title", "")
            authors = fields.get("author", "")
            year = fields.get("year", "")
            venue = fields.get("booktitle") or fields.get("journal") or ""
            abstract = clean_latex_abstract(fields.get("abstract", ""))

            entries.append(
                {
                    "key": key,
                    "entry_type": entry_type,
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "venue": venue,
                    "abstract": abstract,
                    "bibtex": entry_text,
                    "webpage": webpage,
                    "code": code,
                    "video": video,
                    "arxiv": arxiv,
                }
            )

            # Reset metadata so it doesn't leak into the next entry
            webpage = code = video = arxiv = ""
            continue

        # 3) Any other line (blank, etc.)
        i += 1

    return entries


def clean_latex_abstract(text: str) -> str:
    """Strip LaTeX formatting from abstract text, keeping inner content."""
    # \href{url}{text} -> text (url)
    text = re.sub(r"\\href\{([^}]*)\}\{([^}]*)\}", r"\2 (\1)", text)
    # \href{url} (no display text) -> url
    text = re.sub(r"\\href\{([^}]*)\}", r"\1", text)
    # \url{...} -> the URL
    text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)
    # \textbf{...}, \textit{...}, \emph{...}, \texttt{...} -> content
    text = re.sub(r"\\(?:textbf|textit|emph|texttt|moniker)\{([^}]*)\}", r"\1", text)
    # $\textbf{...}$ -> content
    text = re.sub(r"\$\\(?:textbf|textit|emph)\{([^}]*)\}\$", r"\1", text)
    # {\small ...} or {\normalsize ...} -> content
    text = re.sub(r"\{\\(?:small|normalsize|large|footnotesize)\s*([^}]*)\}", r"\1", text)
    # $\geq$, $\leq$, $\times$ etc.
    text = text.replace(r"$\geq$", ">=").replace(r"$\leq$", "<=")
    text = text.replace(r"$\times$", "x")
    # Remaining $...$ math mode -> content without $
    text = re.sub(r"\$([^$]*)\$", r"\1", text)
    # Remove stray braces and backslashes from LaTeX
    text = re.sub(r"\\(?:ss|ae|oe|ue)", lambda m: {"\\ss": "ss", "\\ae": "ae", "\\oe": "oe", "\\ue": "ue"}.get(m.group(), m.group()), text)
    # Remove remaining \command (no braces)
    text = re.sub(r"\\[a-zA-Z]+(?=\s|$)", "", text)
    # Clean stray braces
    text = text.replace("{", "").replace("}", "")
    return text.strip()


def load_abstract_file(key: str) -> str:
    """Load abstract from .txt file fetched from arXiv API."""
    if not ABSTRACT_DIR.exists():
        return ""
    # Use same sanitization as thumb_name
    fname = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    path = ABSTRACT_DIR / f"{fname}.txt"
    if path.exists():
        raw = path.read_text(encoding="utf-8").strip()
        return clean_latex_abstract(raw)
    return ""


ABBR_FILE = ROOT / "abbr.bib"


def _load_bibtex_strings(path: Path) -> Dict[str, str]:
    """Parse @STRING definitions from a .bib file into a macro->value dict."""
    macros: Dict[str, str] = {}
    if not path.exists():
        return macros
    text = path.read_text(encoding="utf-8")
    for m in re.finditer(
        r"@STRING\s*\(\s*(\w+)\s*=\s*\"([^\"]*)\"\s*\)", text, re.IGNORECASE
    ):
        macros[m.group(1).lower()] = m.group(2)
    return macros


_BIB_STRINGS = _load_bibtex_strings(ABBR_FILE)

# Additional venue normalization for values not covered by abbr.bib
_VENUE_OVERRIDES: Dict[str, str] = {
    # Normalize brace-delimited venues
    "corr": "arXiv",
    "arxiv": "arXiv",
    "3dv": "3DV",
    # abbr.bib resolved values that need further shortening
    "transactions on graphics, (proc. siggraph)": "TOG (SIGGRAPH)",
    "transactions on graphics, (proc. siggraph asia)": "TOG (SIGGRAPH Asia)",
    "siggraph conference papers (sa)": "SIGGRAPH",
    "siggraph asia conference papers (sa)": "SIGGRAPH Asia",
    "transactions on graphics (tog)": "TOG",
    "transactions on visualization and computer graphics (tvcg)": "TVCG",
    "transactions on pattern analysis and machine intelligence (tpami)": "TPAMI",
    "computer graphics forum (cgf)": "CGF",
    "computer graphics and interactive techniques (pacmcgit)": "PACMCGIT",
    "advances in neural information processing systems (neurips)": "NeurIPS",
    "advances in neural information processing systems (nips)": "NeurIPS",
    "symposium on computer animation (sca)": "SCA",
    "visual informatics (vi)": "Visual Informatics",
    "robotics: science and systems (rss)": "RSS",
    # Verbose ACM proceedings -> short names
    "proceedings of the 30th acm international conference on multimedia": "ACM Multimedia",
    "proceedings of the 32nd annual acm symposium on user interface software and technology": "ACM UIST",
    "proceedings of the 17th acm siggraph conference on motion, interaction, and games": "SIGGRAPH MIG",
    "proceedings of the 9th international conference on motion in games (mig)": "MIG",
    "proceedings of the acm on computer graphics and interactive techniques": "PACMCGIT",
    "acm siggraph symposium on interactive 3d graphics and games (i3d 2016)": "ACM I3D",
    "acm siggraph 2006 research posters": "SIGGRAPH Posters",
    "international conference on multimedia, mm": "ACM Multimedia",
    "siggraph '23 real-time live!": "SIGGRAPH Real-Time Live!",
    # Full journal names -> abbreviations
    "advances in neural information processing systems": "NeurIPS",
    "computer science review": "Computer Science Review",
    "plos one": "PLOS ONE",
    "journal of visual communication and image representation": "JVCI",
    "image and vision computing": "Image and Vision Computing",
    "image vision comput.": "Image and Vision Computing",
    "digital investigation": "Digital Investigation",
    "ieee transactions on information forensics and security": "IEEE TIFS",
}


def _normalize_venue(venue: str) -> str:
    """Clean up and normalize venue names."""
    if not venue:
        return ""
    # Strip URLs that ended up as venue
    if venue.strip().startswith("URL:") or venue.strip().startswith("http"):
        return ""
    # Strip trailing/leading whitespace and braces
    venue = venue.strip().strip("{}")
    key = venue.lower().strip()
    # 1) Try abbr.bib macro resolution (bare identifiers like CVPR, SIGGRAPH_TOG)
    if key in _BIB_STRINGS:
        venue = _BIB_STRINGS[key]
    # 2) Try manual overrides
    key2 = venue.lower().strip()
    if key2 in _VENUE_OVERRIDES:
        return _VENUE_OVERRIDES[key2]
    # 3) Extract short abbreviation from parentheses if present
    #    e.g. "Conference on Computer Vision and Pattern Recognition (CVPR)" -> "CVPR"
    m = re.search(r"\(([^)]+)\)\s*$", venue)
    if m:
        return m.group(1)
    return venue


def build_publications_page():
    entries = parse_bibliography_with_metadata(BIB_FILE)

    def has_meta(e: Dict[str, str]) -> bool:
        for field in ("webpage", "code", "video", "arxiv"):
            v = e.get(field, "")
            if v and v.lower() != "none":
                return True
        return False

    entries = [e for e in entries if has_meta(e)]

    # Load abstracts from file if not in BibTeX
    for e in entries:
        if not e["abstract"]:
            e["abstract"] = load_abstract_file(e["key"])

    # Normalize venue names
    for e in entries:
        e["venue"] = _normalize_venue(e["venue"])

    # Load classification data
    classified, skipped, notes = load_classifications()

    def year_key(e):
        y = e.get("year", "")
        try:
            return -int(y)
        except Exception:
            return 0

    entries.sort(key=lambda e: (year_key(e), e.get("title", "").lower()))

    # Collect all unique years and venues for filter controls
    years = sorted(set(e["year"] for e in entries if e["year"]), reverse=True)
    venues = sorted(set(e["venue"] for e in entries if e["venue"]))

    total = len(entries)
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    lines: List[str] = []

    # --- Embedded legend table (interactive filtering) ---
    legend_path = TABLES_DIR / "legend.html"
    if legend_path.exists():
        lines.append('<div class="pub-legend-section">')
        lines.append('<h3 class="pub-legend-heading"><span class="pub-legend-hint">'
                     '&#x26A0;&#xFE0F; Click icons to filter publications. '
                     'Select multiple to combine filters (AND). '
                     'Click again to deselect.</span></h3>')
        lines.append(legend_path.read_text(encoding="utf-8"))
        lines.append('</div>')

    # --- Filter controls (single row) ---
    lines.append('<div class="pub-controls">')
    lines.append('  <div class="pub-search-wrap">')
    lines.append('    <svg class="pub-search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">'
                 '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>')
    lines.append('    <input type="text" id="pub-search" class="pub-search" '
                 'placeholder="Search by title, author, or BibTeX key..." />')
    lines.append('  </div>')
    lines.append('  <button type="button" class="pub-filter-toggle" id="pub-filter-toggle" aria-label="Toggle filters"'
                 ' aria-expanded="false">'
                 '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
                 '<path d="M1 2h14M3 5.5h10M5 9h6M6.5 12.5h3"/></svg>'
                 '<span>Filters</span></button>')
    lines.append('  <select id="pub-year-filter" class="pub-filter-select pub-filter-collapsible">')
    lines.append('    <option value="">All years</option>')
    for y in years:
        lines.append(f'    <option value="{html.escape(y)}">{html.escape(y)}</option>')
    lines.append('  </select>')
    lines.append('  <select id="pub-venue-filter" class="pub-filter-select pub-filter-collapsible">')
    lines.append('    <option value="">All venues</option>')
    for v in venues:
        label = v if len(v) <= 60 else v[:57] + "..."
        lines.append(f'    <option value="{html.escape(v)}">{html.escape(label)}</option>')
    lines.append('  </select>')

    # Table type filter (custom multi-select dropdown)
    lines.append('  <div class="pub-multiselect pub-filter-collapsible" id="pub-type-multi">')
    lines.append('    <button class="pub-multiselect-btn pub-filter-select" type="button" id="pub-type-btn">All types</button>')
    lines.append('    <div class="pub-multiselect-menu" id="pub-type-menu">')
    for val, label in [("avatar", "Avatar"), ("assets", "Assets"), ("skipped", "Not classified"), ("has_notes", "Has notes")]:
        lines.append(f'      <label class="pub-multiselect-item"><input type="checkbox" value="{val}"><span>{label}</span></label>')
    lines.append('    </div>')
    lines.append('  </div>')

    # Category filter
    categories = sorted({
        info["category"] for info in classified.values() if info.get("category")
    })
    lines.append('  <select id="pub-category-filter" class="pub-filter-select pub-filter-collapsible">')
    lines.append('    <option value="">All categories</option>')
    for cat in categories:
        lines.append(f'    <option value="{html.escape(cat)}">{html.escape(cat)}</option>')
    lines.append('  </select>')

    lines.append(f'  <span class="pub-result-count" id="pub-result-count">{total} papers</span>')
    lines.append('  <label class="pub-show-notes-toggle pub-filter-collapsible"><input type="checkbox" id="pub-show-notes"> Show notes</label>')
    lines.append('</div>')

    # --- Legend filter pills container ---
    lines.append('<div class="legend-filter-pills" id="legend-filter-pills"></div>')

    # --- Publication cards ---
    lines.append(f'<div class="publications-list" id="pub-list" data-per-page="{ITEMS_PER_PAGE}">')

    for idx, e in enumerate(entries, start=1):
        key = e["key"]
        title = e["title"] or key
        authors = e["authors"]
        year = e["year"]
        venue = e["venue"]
        abstract = e["abstract"]

        webpage = e["webpage"]
        code_url = e["code"]
        video = e["video"]
        arxiv = e["arxiv"]

        thumb_src = f"assets/img/thumbnails/{html.escape(key)}.jpg"

        # Determine PDF URL for thumbnail click-through
        pdf_url = ""
        if arxiv and arxiv.lower() != "none":
            pdf_url = arxiv
        elif webpage and webpage.lower() != "none":
            pdf_url = webpage

        # Determine classification info
        cls_info = classified.get(key)
        skip_reason = skipped.get(key, "")
        note = notes.get(key, "")
        if cls_info:
            table_type = cls_info["table_type"]
            category = cls_info["category"]
        elif skip_reason:
            table_type = "skipped"
            category = ""
        else:
            table_type = "unclassified"
            category = ""

        # Data attributes for client-side filtering
        fields_json = html.escape(json.dumps(cls_info.get("fields", {}))) if cls_info else ""
        has_notes = "1" if note else ""
        data_attrs = (
            f'data-bibkey="{html.escape(key)}" '
            f'data-title="{html.escape(title.lower())}" '
            f'data-authors="{html.escape(authors.lower())}" '
            f'data-year="{html.escape(year)}" '
            f'data-venue="{html.escape(venue)}" '
            f'data-table-type="{html.escape(table_type)}" '
            f'data-category="{html.escape(category)}" '
            f'data-fields="{fields_json}" '
            f'data-has-notes="{has_notes}" '
            f'data-idx="{idx}"'
        )

        lines.append(f'<article class="pub-card" {data_attrs}>')
        lines.append(f'  <div class="pub-rank">{idx}</div>')
        thumb_class = "pub-thumb" + (" pub-thumb-linked" if pdf_url else "")
        lines.append(f'  <div class="{thumb_class}">')
        if pdf_url:
            lines.append(f'    <a href="{html.escape(pdf_url)}" target="_blank" rel="noopener" class="pub-thumb-link" title="View PDF">')
        lines.append(
            f'    <img src="{thumb_src}" alt="Thumbnail for {html.escape(title)}" '
            "loading=\"lazy\" onerror=\"this.classList.add('no-thumb');"
            "this.parentElement.classList.add('has-placeholder');"
            "var s=document.createElement('div');s.className='thumb-placeholder';"
            "s.innerHTML='<svg width=\\'48\\' height=\\'48\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'currentColor\\' stroke-width=\\'1.5\\'>"
            "<path d=\\'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z\\'/>"
            "<polyline points=\\'14 2 14 8 20 8\\'/>"
            "<line x1=\\'16\\' y1=\\'13\\' x2=\\'8\\' y2=\\'13\\'/>"
            "<line x1=\\'16\\' y1=\\'17\\' x2=\\'8\\' y2=\\'17\\'/>"
            "</svg>';"
            "this.parentElement.appendChild(s);\" />"
        )
        if pdf_url:
            lines.append('    </a>')
        lines.append("  </div>")
        lines.append('  <div class="pub-main">')
        title_line = html.escape(title)
        if year:
            title_line += f" ({html.escape(year)})"
        lines.append(f'    <h3 class="pub-title">{title_line}</h3>')
        if authors:
            lines.append(f'    <div class="pub-authors">{html.escape(authors)}</div>')
        tags = []
        if venue:
            tags.append(venue)
        if e["entry_type"]:
            tags.append(e["entry_type"])
        if tags:
            lines.append('    <div class="pub-tags">')
            for t in tags:
                lines.append(f'      <span class="pub-tag">{html.escape(t)}</span>')
            # Taxonomy tag
            if cls_info:
                tag_label = f"{cls_info['table_type'].capitalize()}: {category}" if category else cls_info["table_type"].capitalize()
                lines.append(f'      <span class="pub-taxonomy-tag pub-taxonomy-{html.escape(table_type)}">{html.escape(tag_label)}</span>')
            elif skip_reason:
                lines.append('      <span class="pub-taxonomy-tag pub-taxonomy-skipped">Not classified</span>')
            lines.append("    </div>")
        lines.append('    <div class="pub-links">')
        if arxiv and arxiv.lower() != "none":
            lines.append(
                f'      <a class="pub-link" href="{html.escape(arxiv)}" target="_blank" rel="noopener">Paper</a>'
            )
        if webpage and webpage.lower() != "none":
            lines.append(
                f'      <a class="pub-link" href="{html.escape(webpage)}" target="_blank" rel="noopener">Project</a>'
            )
        if code_url and code_url.lower() != "none":
            lines.append(
                f'      <a class="pub-link" href="{html.escape(code_url)}" target="_blank" rel="noopener">Code</a>'
            )
        if video and video.lower() != "none":
            lines.append(
                f'      <a class="pub-link" href="{html.escape(video)}" target="_blank" rel="noopener">Video</a>'
            )
        bibtex_raw = e.get("bibtex", "")
        if bibtex_raw:
            lines.append(
                f'      <button class="pub-link pub-bib-copy" '
                f'data-bibtex="{html.escape(bibtex_raw)}">BibTeX</button>'
            )
        lines.append("    </div>")
        if abstract:
            safe_abs = html.escape(abstract)
            # Make URLs clickable
            safe_abs = re.sub(
                r'(https?://[^\s,;)<>]+)',
                r'<a href="\1" target="_blank" rel="noopener">\1</a>',
                safe_abs,
            )
            lines.append(f'    <div class="pub-abstract">{safe_abs}</div>')
        if skip_reason:
            lines.append(f'    <div class="pub-skip-reason">Skip reason: {html.escape(skip_reason)}</div>')
        if note:
            lines.append(f'    <div class="pub-note">Note: {html.escape(note)}</div>')
        lines.append("  </div>")
        lines.append("</article>")

    lines.append("</div>")

    # --- Inline JS for filtering (no pagination) ---
    lines.append('<script>')
    lines.append('(function() {')
    lines.append('  var allCards = Array.prototype.slice.call(document.querySelectorAll("#pub-list .pub-card"));')
    lines.append('  var searchEl = document.getElementById("pub-search");')
    lines.append('  var yearEl   = document.getElementById("pub-year-filter");')
    lines.append('  var venueEl  = document.getElementById("pub-venue-filter");')
    lines.append('  var typeMulti = document.getElementById("pub-type-multi");')
    lines.append('  var typeBtn   = document.getElementById("pub-type-btn");')
    lines.append('  var typeMenu  = document.getElementById("pub-type-menu");')
    lines.append('  var catEl    = document.getElementById("pub-category-filter");')
    lines.append('  var countEl  = document.getElementById("pub-result-count");')
    lines.append('  var pillsEl  = document.getElementById("legend-filter-pills");')
    lines.append('')
    lines.append('  if (!window.__legendFilters) window.__legendFilters = [];')
    lines.append('')
    lines.append('  function removeFilter(field, value) {')
    lines.append('    var arr = window.__legendFilters;')
    lines.append('    for (var i = arr.length - 1; i >= 0; i--) {')
    lines.append('      if (arr[i].field === field && arr[i].value === value) arr.splice(i, 1);')
    lines.append('    }')
    lines.append('    // Remove is-active class from the legend item')
    lines.append('    var btns = document.querySelectorAll(".legend-filter-btn");')
    lines.append('    for (var j = 0; j < btns.length; j++) {')
    lines.append('      if (btns[j].getAttribute("data-filter-field") === field && btns[j].getAttribute("data-filter-value") === value) {')
    lines.append('        btns[j].classList.remove("is-active");')
    lines.append('      }')
    lines.append('    }')
    lines.append('    doFilter();')
    lines.append('  }')
    lines.append('')
    lines.append('  function clearAllFilters() {')
    lines.append('    window.__legendFilters = [];')
    lines.append('    var btns = document.querySelectorAll(".legend-filter-btn.is-active");')
    lines.append('    for (var j = 0; j < btns.length; j++) btns[j].classList.remove("is-active");')
    lines.append('    doFilter();')
    lines.append('  }')
    lines.append('')
    lines.append('  function renderPills() {')
    lines.append('    if (!pillsEl) return;')
    lines.append('    pillsEl.innerHTML = "";')
    lines.append('    var filters = window.__legendFilters || [];')
    lines.append('    if (filters.length === 0) return;')
    lines.append('    for (var i = 0; i < filters.length; i++) {')
    lines.append('      var pill = document.createElement("span");')
    lines.append('      pill.className = "legend-filter-pill";')
    lines.append('      var txt = document.createElement("span");')
    lines.append('      txt.textContent = filters[i].field + ": " + filters[i].value;')
    lines.append('      pill.appendChild(txt);')
    lines.append('      var closeBtn = document.createElement("button");')
    lines.append('      closeBtn.innerHTML = "&times;";')
    lines.append('      closeBtn.setAttribute("data-field", filters[i].field);')
    lines.append('      closeBtn.setAttribute("data-value", filters[i].value);')
    lines.append('      closeBtn.addEventListener("click", function() {')
    lines.append('        removeFilter(this.getAttribute("data-field"), this.getAttribute("data-value"));')
    lines.append('      });')
    lines.append('      pill.appendChild(closeBtn);')
    lines.append('      pillsEl.appendChild(pill);')
    lines.append('    }')
    lines.append('    if (filters.length > 1) {')
    lines.append('      var clearAll = document.createElement("button");')
    lines.append('      clearAll.className = "legend-filter-clear-all";')
    lines.append('      clearAll.textContent = "Clear all";')
    lines.append('      clearAll.addEventListener("click", clearAllFilters);')
    lines.append('      pillsEl.appendChild(clearAll);')
    lines.append('    }')
    lines.append('  }')
    lines.append('')
    lines.append('  function stripDiacritics(s) {')
    lines.append('    return s.replace(/\u00df/g, "ss").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "");')
    lines.append('  }')
    lines.append('  function doFilter() {')
    lines.append('    var q = searchEl ? stripDiacritics(searchEl.value.toLowerCase().trim()) : "";')
    lines.append('    var y = yearEl ? yearEl.value : "";')
    lines.append('    var v = venueEl ? venueEl.value : "";')
    lines.append('    var ttSelected = [];')
    lines.append('    if (typeMenu) { var cbs = typeMenu.querySelectorAll("input[type=checkbox]:checked"); for (var ci = 0; ci < cbs.length; ci++) ttSelected.push(cbs[ci].value); }')
    lines.append('    var cat = catEl ? catEl.value : "";')
    lines.append('    var lfs = window.__legendFilters || [];')
    lines.append('    renderPills();')
    lines.append('    var rank = 0;')
    lines.append('    for (var i = 0; i < allCards.length; i++) {')
    lines.append('      var c = allCards[i];')
    lines.append('      var show = true;')
    lines.append('      if (q) {')
    lines.append('        var t = stripDiacritics(c.getAttribute("data-title") || "");')
    lines.append('        var a = stripDiacritics(c.getAttribute("data-authors") || "");')
    lines.append('        var yr = c.getAttribute("data-year") || "";')
    lines.append('        var bk = (c.getAttribute("data-bibkey") || "").toLowerCase();')
    lines.append('        var hay = t + " " + a + " " + yr + " " + bk;')
    lines.append('        var words = q.replace(/[()\\[\\]{}]/g, "").split(/\\s+/);')
    lines.append('        for (var wi = 0; wi < words.length; wi++) {')
    lines.append('          if (words[wi] && hay.indexOf(words[wi]) < 0) { show = false; break; }')
    lines.append('        }')
    lines.append('      }')
    lines.append('      if (show && y && c.getAttribute("data-year") !== y) show = false;')
    lines.append('      if (show && v && c.getAttribute("data-venue") !== v) show = false;')
    lines.append('      if (show && ttSelected.length > 0) {')
    lines.append('        var cardType = c.getAttribute("data-table-type") || "";')
    lines.append('        var hasNotes = !!c.getAttribute("data-has-notes");')
    lines.append('        var typeMatch = false;')
    lines.append('        for (var ti = 0; ti < ttSelected.length; ti++) {')
    lines.append('          if (ttSelected[ti] === "has_notes") { if (hasNotes) typeMatch = true; }')
    lines.append('          else { if (cardType === ttSelected[ti]) typeMatch = true; }')
    lines.append('        }')
    lines.append('        if (!typeMatch) show = false;')
    lines.append('      }')
    lines.append('      if (show && cat && c.getAttribute("data-category") !== cat) show = false;')
    lines.append('      if (show && lfs.length > 0) {')
    lines.append('        var raw = c.getAttribute("data-fields");')
    lines.append('        if (raw) {')
    lines.append('          try {')
    lines.append('            var fields = JSON.parse(raw);')
    lines.append('            for (var fi = 0; fi < lfs.length; fi++) {')
    lines.append('              var fv = (fields[lfs[fi].field] || "").toLowerCase();')
    lines.append('              if (fv.indexOf(lfs[fi].value.toLowerCase()) < 0) { show = false; break; }')
    lines.append('            }')
    lines.append('          } catch(e) { show = false; }')
    lines.append('        } else { show = false; }')
    lines.append('      }')
    lines.append('      if (show) {')
    lines.append('        c.style.display = "";')
    lines.append('        rank++;')
    lines.append('        var r = c.querySelector(".pub-rank");')
    lines.append('        if (r) r.textContent = rank;')
    lines.append('      } else {')
    lines.append('        c.style.display = "none";')
    lines.append('      }')
    lines.append('    }')
    lines.append('    if (countEl) countEl.textContent = rank + (rank === 1 ? " paper" : " papers");')
    lines.append('    // Sync notes visibility with filters and checkbox')
    lines.append('    var notesRelevant = false;')
    lines.append('    for (var ni = 0; ni < ttSelected.length; ni++) {')
    lines.append('      if (ttSelected[ni] === "has_notes" || ttSelected[ni] === "skipped") { notesRelevant = true; break; }')
    lines.append('    }')
    lines.append('    var pubList = document.getElementById("pub-list");')
    lines.append('    var showNotesCheck = document.getElementById("pub-show-notes");')
    lines.append('    if (showNotesCheck) {')
    lines.append('      if (notesRelevant && !showNotesCheck._wasAuto) {')
    lines.append('        showNotesCheck._manualBefore = showNotesCheck.checked;')
    lines.append('        showNotesCheck.checked = true;')
    lines.append('        showNotesCheck._wasAuto = true;')
    lines.append('      } else if (!notesRelevant && showNotesCheck._wasAuto) {')
    lines.append('        showNotesCheck.checked = !!showNotesCheck._manualBefore;')
    lines.append('        showNotesCheck._wasAuto = false;')
    lines.append('      }')
    lines.append('      pubList.classList.toggle("show-notes", showNotesCheck.checked);')
    lines.append('    }')
    lines.append('  }')
    lines.append('')
    lines.append('  window.__pubDoFilter = doFilter;')
    lines.append('')
    lines.append('  var timer;')
    lines.append('  if (searchEl) searchEl.addEventListener("input", function() {')
    lines.append('    clearTimeout(timer); timer = setTimeout(doFilter, 200);')
    lines.append('  });')
    lines.append('  if (yearEl) yearEl.addEventListener("change", doFilter);')
    lines.append('  if (venueEl) venueEl.addEventListener("change", doFilter);')
    lines.append('  if (catEl) catEl.addEventListener("change", doFilter);')
    lines.append('')
    lines.append('  // Custom multi-select dropdown for type filter')
    lines.append('  if (typeBtn) typeBtn.addEventListener("click", function(e) {')
    lines.append('    e.stopPropagation();')
    lines.append('    typeMulti.classList.toggle("is-open");')
    lines.append('  });')
    lines.append('  if (typeMenu) typeMenu.addEventListener("change", function() {')
    lines.append('    var cbs = typeMenu.querySelectorAll("input[type=checkbox]:checked");')
    lines.append('    if (cbs.length === 0) { typeBtn.textContent = "All types"; }')
    lines.append('    else {')
    lines.append('      var labels = [];')
    lines.append('      for (var ci = 0; ci < cbs.length; ci++) labels.push(cbs[ci].parentElement.querySelector("span").textContent);')
    lines.append('      typeBtn.textContent = labels.join(", ");')
    lines.append('    }')
    lines.append('    doFilter();')
    lines.append('  });')
    lines.append('  document.addEventListener("click", function(e) {')
    lines.append('    if (typeMulti && !typeMulti.contains(e.target)) typeMulti.classList.remove("is-open");')
    lines.append('  });')
    lines.append('')
    lines.append('  // Mobile filter toggle')
    lines.append('  var filterToggle = document.getElementById("pub-filter-toggle");')
    lines.append('  if (filterToggle) filterToggle.addEventListener("click", function() {')
    lines.append('    var controls = this.closest(".pub-controls");')
    lines.append('    var isOpen = controls.classList.toggle("filters-open");')
    lines.append('    this.setAttribute("aria-expanded", isOpen ? "true" : "false");')
    lines.append('  });')
    lines.append('')
    lines.append('  // Show notes toggle')
    lines.append('  var showNotesEl = document.getElementById("pub-show-notes");')
    lines.append('  if (showNotesEl) showNotesEl.addEventListener("change", function() {')
    lines.append('    document.getElementById("pub-list").classList.toggle("show-notes", this.checked);')
    lines.append('  });')
    lines.append('')
    lines.append('  // Apply pending legend filters on load')
    lines.append('  if (window.__legendFilters && window.__legendFilters.length > 0) doFilter();')
    lines.append('')
    lines.append('  // BibTeX copy-to-clipboard')
    lines.append('  document.getElementById("pub-list").addEventListener("click", function(e) {')
    lines.append('    var btn = e.target.closest(".pub-bib-copy");')
    lines.append('    if (!btn) return;')
    lines.append('    var bib = btn.getAttribute("data-bibtex");')
    lines.append('    if (!bib) return;')
    lines.append('    navigator.clipboard.writeText(bib).then(function() {')
    lines.append('      btn.textContent = "Copied!";')
    lines.append('      btn.classList.add("pub-bib-copied");')
    lines.append('      setTimeout(function() {')
    lines.append('        btn.textContent = "BibTeX";')
    lines.append('        btn.classList.remove("pub-bib-copied");')
    lines.append('      }, 1000);')
    lines.append('    }).catch(function() {});')
    lines.append('  });')
    lines.append('})();')
    lines.append('</script>')

    (TABLES_DIR / "publications.html").write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Wrote tables/publications.html ({total} entries, {total_pages} pages)")

    # --- Write consolidated JSON ---
    json_out_dir = ROOT / "assets" / "data"
    json_out_dir.mkdir(parents=True, exist_ok=True)

    def _link_or_null(val: str):
        if val and val.lower() != "none":
            return val
        return None

    json_entries = []
    for e in entries:
        key = e["key"]
        cls_info = classified.get(key)
        classification = None
        if cls_info:
            classification = {
                "table_type": cls_info["table_type"],
                "fields": cls_info["fields"],
            }

        json_entries.append({
            "key": key,
            "title": e["title"],
            "authors": e["authors"],
            "year": e["year"],
            "venue": e["venue"],
            "entry_type": e["entry_type"],
            "links": {
                "webpage": _link_or_null(e["webpage"]),
                "code": _link_or_null(e["code"]),
                "video": _link_or_null(e["video"]),
                "arxiv": _link_or_null(e["arxiv"]),
            },
            "classification": classification,
            "note": notes.get(key) or None,
            "skip_reason": skipped.get(key) or None,
        })

    json_out = json_out_dir / "publications.json"
    json_out.write_text(json.dumps(json_entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Wrote {json_out.relative_to(ROOT)} ({len(json_entries)} entries)")


def main():
    build_publications_page()


if __name__ == "__main__":
    main()
