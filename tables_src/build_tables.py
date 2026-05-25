#!/usr/bin/env python3
"""
Generate HTML tables for the website directly from the CSV taxonomy files.

- STAR - Digital Humans Taxonomy - Avatar.csv   -> tables/taxonomy.html
- STAR - Digital Humans Taxonomy - Datasets.csv -> tables/datasets.html
- Legend is generated from LEGEND_MAPPING in table.py

Icons and legend semantics are taken from the same LaTeX sources as the paper:
- tables_src/table.py   (LEGEND_MAPPING)
- tables_src/macros.tex (macro -> icon path)
- tables_src/bibliography.bib (BibTeX entries)

Usage (from repo root):
    python tables_src/build_tables.py
"""

from __future__ import annotations
import html
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tables_src"
TABLES_DIR = ROOT / "tables"
TABLES_DIR.mkdir(exist_ok=True)

CSV_AVATAR = SRC / "STAR - Digital Humans Taxonomy - Avatar.csv"
CSV_DATASETS = SRC / "STAR - Digital Humans Taxonomy - Datasets.csv"
BIB_FILE = SRC / "bibliography.bib"
MACROS_TEX = SRC / "macros.tex"
TABLE_PY = SRC / "table.py"
PAPERS_TXT = SRC / "papers.txt"
ASSETS_TXT = SRC / "assets.txt"
CSV_ASSETS = SRC / "STAR - Digital Humans Taxonomy - Assets.csv"
JSON_FILE = ROOT / "classify" / "final_results.json"

# --- Compatibility patch for pandas.DataFrame.map used in table.py ---
if not hasattr(pd.DataFrame, "map"):
    pd.DataFrame.map = pd.DataFrame.applymap  # type: ignore

import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
import table as latex_table  # type: ignore
from normalize_fields import normalize_fields

LEGEND_MAPPING: Dict[str, str] = latex_table.LEGEND_MAPPING
COLUMNS_TO_REMOVE: List[str] = latex_table.COLUMNS_TO_REMOVE
LETTERBOX_COLUMNS: List[str] = latex_table.LETTERBOX_COLUMNS


def parse_macros(tex_path: Path) -> Dict[str, str]:
    """Return mapping macro_name -> icon_relative_path."""
    text = tex_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\\newcommand\{\\(ico[A-Za-z0-9]+)\}\{\\icon\{([^}]+)\}\}")
    mapping: Dict[str, str] = {}
    for line in text.splitlines():
        # Skip TeX comment lines
        if line.lstrip().startswith("%"):
            continue
        for macro, icon_path in pattern.findall(line):
            # later definitions override earlier ones (custom icons override emoji)
            mapping[macro] = icon_path
    return mapping


MACRO_TO_ICON = parse_macros(MACROS_TEX)


def parse_colors(tex_path: Path) -> Dict[str, str]:
    """Return mapping color_name -> 'r,g,b' string."""
    text = tex_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\\definecolor\{(\w+)\}\{RGB\}\{(\d+),(\d+),(\d+)\}")
    colors: Dict[str, str] = {}
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        for name, r, g, b in pattern.findall(line):
            colors[name] = f"{r},{g},{b}"
    return colors


TEX_COLORS = parse_colors(MACROS_TEX)


def parse_crbox_macros(tex_path: Path) -> Dict[str, tuple]:
    """Return mapping macro_name -> (color_name, letter, is_bold)."""
    text = tex_path.read_text(encoding="utf-8")
    boxes: Dict[str, tuple] = {}
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        for match in re.finditer(
            r"\\newcommand\{\\(crbox[A-Za-z0-9]+)\}\{\\crbox(bold|reg)\{(\w+)\}\{([^}]*)\}\}",
            line,
        ):
            macro_name = match.group(1)
            style = match.group(2)  # "bold" or "reg"
            color_name = match.group(3)
            letter = match.group(4)
            boxes[macro_name] = (color_name, letter, style == "bold")
    return boxes


CRBOX_MACROS = parse_crbox_macros(MACROS_TEX)


def render_crbox(macro_name: str, tooltip: str = "") -> str:
    """Render a crbox macro as an HTML colored badge with optional tooltip."""
    info = CRBOX_MACROS.get(macro_name)
    if not info:
        return ""
    color_name, letter, is_bold = info
    rgb = TEX_COLORS.get(color_name, "128,128,128")
    text_color = "#fff" if is_bold else "#000"
    weight = "700" if is_bold else "600"
    title_attr = f' title="{html.escape(tooltip)}"' if tooltip else ""
    return (
        f'<span class="crbox"{title_attr} style="background:rgb({rgb});color:{text_color};'
        f'font-weight:{weight}">{html.escape(letter)}</span>'
    )

# Build mapping: legend text (CSV value) -> icon file path (under assets/img/icons)
TEXT_TO_ICON: Dict[str, str] = {}
# Also build mapping: legend text -> crbox macro name (for colored badges)
TEXT_TO_CRBOX: Dict[str, str] = {}
# Reverse mapping: crbox macro name -> legend label (for tooltips)
CRBOX_TO_LABEL: Dict[str, str] = {}
for label, macro in LEGEND_MAPPING.items():
    macro_name = macro.lstrip("\\")
    icon = MACRO_TO_ICON.get(macro_name)
    if icon:
        TEXT_TO_ICON[label] = icon
    elif macro_name in CRBOX_MACROS:
        TEXT_TO_CRBOX[label] = macro_name
        CRBOX_TO_LABEL[macro_name] = label


def load_bibtex(path: Path) -> Dict[str, str]:
    """Parse BibTeX into key -> full entry string."""
    if not path.exists():
        return {}
    bib: Dict[str, str] = {}
    current_key = None
    current_lines: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("@"):
                # flush previous
                if current_key is not None and current_lines:
                    bib[current_key] = "".join(current_lines).strip()
                current_lines = [line]
                m = re.match(r"@\w+\{([^,]+),", line)
                current_key = m.group(1).strip() if m else None
            else:
                if current_key is not None and not line.lstrip().startswith("%"):
                    current_lines.append(line)
        # last
        if current_key is not None and current_lines:
            bib[current_key] = "".join(current_lines).strip()
    return bib


BIBTEX = load_bibtex(BIB_FILE)


def _normalize_single_part(s: str) -> str:
    """Map a single body-part token to its canonical section name."""
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


def normalize_contents(raw) -> str:
    """Extract primary body-part section from a Contents field value."""
    if raw is None:
        return "Other"
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "null", "-"):
        return "Other"
    # Remove parenthetical content
    s = re.sub(r"\([^)]*\)", "", s).strip()
    # Split on comma, slash, semicolon, or " + " and take the first recognized part
    parts = re.split(r"[,/;]|\s\+\s", s)
    for part in parts:
        mapped = _normalize_single_part(part)
        if mapped:
            return mapped
    return "Other"


def load_json_classifications(path: Path):
    """Load classifications from final_results.json.

    Returns (avatar_list, assets_list, skipped_list).
    """
    if not path.exists():
        return [], [], []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return (
        data.get("avatar_classifications", []),
        data.get("assets_classifications", []),
        data.get("skipped", []),
    )


def is_empty(val) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "-"}


def format_plain(val) -> str:
    if is_empty(val):
        return ""
    return html.escape(str(val).strip())


def split_legend_values(raw) -> List[str]:
    """Split a CSV cell into values using the same separators as LaTeX."""
    if is_empty(raw):
        return []
    t = str(raw).strip()
    # reuse latex_table.get_legend_values to normalize parentheses etc.
    vals = latex_table.get_legend_values(t)
    if isinstance(vals, str):
        vals = [vals] if vals else []
    return [v for v in vals if v]


def _derive_crbox_name(value: str) -> str:
    """Derive the crbox macro name from a value, matching LaTeX display_single_letterbox."""
    return "crbox" + "".join(ch for ch in value if ch.isalpha())


def render_single_value(v: str, column_name: str = "") -> str:
    """Render a single legend value as icon image, crbox badge, or plain text."""
    # For LETTERBOX columns, always try crbox rendering first (matching LaTeX behavior)
    if column_name in LETTERBOX_COLUMNS:
        crbox_name = _derive_crbox_name(v)
        if crbox_name in CRBOX_MACROS:
            tooltip = CRBOX_TO_LABEL.get(crbox_name, v)
            return render_crbox(crbox_name, tooltip=tooltip)

    icon_rel = TEXT_TO_ICON.get(v)
    if icon_rel:
        src = f"assets/img/icons/{icon_rel}"
        return (
            f'<span class="icon-cell" title="{html.escape(v)}">'
            f'<img src="{src}" alt="{html.escape(v)}" loading="lazy" />'
            f"</span>"
        )
    crbox_name = TEXT_TO_CRBOX.get(v)
    if crbox_name:
        tooltip = CRBOX_TO_LABEL.get(crbox_name, v)
        return render_crbox(crbox_name, tooltip=tooltip)
    return html.escape(v)


def render_icon_cell(raw, column_name: str = "") -> str:
    vals = split_legend_values(raw)
    if not vals:
        return ""
    rendered = [render_single_value(v, column_name) for v in vals]
    # Icons/crboxes (contain HTML tags) get space separator; plain text gets ", "
    parts: List[str] = []
    for r in rendered:
        if parts and ("<" in parts[-1] or "<" in r):
            parts.append(" ")
        elif parts:
            parts.append(", ")
        parts.append(r)
    return "".join(parts)


def build_taxonomy_table():
    df_raw = pd.read_csv(CSV_AVATAR, encoding="utf-8-sig")
    subhdr = df_raw.iloc[0].tolist()
    cols_keep = []
    subhdr_keep = []
    for i, c in enumerate(df_raw.columns):
        label = str(subhdr[i])
        if not any(label.strip().lower() == r.lower() for r in COLUMNS_TO_REMOVE):
            cols_keep.append(c)
            subhdr_keep.append(label)
    df = df_raw.loc[1:, cols_keep].copy()  # skip header row
    df.columns = subhdr_keep

    # Reorder rows according to papers.txt (same as LaTeX)
    order_dict, key_list, name_list = latex_table.load_order_from_papers(PAPERS_TXT)
    order_set = set(key_list)
    df = df[df["Bib ref"].astype(str).str.strip().isin(order_set)].copy()
    idx_map = {k: i for i, k in enumerate(key_list)}
    df["__rank__"] = df["Bib ref"].astype(str).str.strip().map(idx_map)
    df = df.sort_values("__rank__", kind="stable").drop(columns="__rank__")

    # Map each bib key to body part section and short method name
    body_part_by_key: Dict[str, str] = {}
    for section, keys in order_dict.items():
        for k in keys:
            body_part_by_key[k] = section

    shortname_by_key = {k: n for k, n in zip(key_list, name_list)}

    df["__BodyPart__"] = df["Bib ref"].astype(str).str.strip().map(body_part_by_key)
    df["__MethodName__"] = df["Bib ref"].astype(str).str.strip().map(shortname_by_key)

    # Group sizes (for potential grouping rendering)
    groups = {"Avatar Prior": 4, "Avatar Creation": 5, "Avatar Animation": 6}

    # Build HTML
    out = []
    out.append('<div class="latex-table-wrapper">')
    out.append('<table class="taxonomy-table latex-table">')
    # Header
    out.append("<thead>")
    # Group row
    out.append("<tr>")
    out.append('<th class="th-group th-metadata">Digital Human Avatars</th>')
    out.append(f'<th class="th-group th-prior" colspan="{groups["Avatar Prior"]}">Avatar Prior</th>')
    out.append(f'<th class="th-group th-creation" colspan="{groups["Avatar Creation"]}">Avatar Creation</th>')
    out.append(f'<th class="th-group th-animation" colspan="{groups["Avatar Animation"]}">Avatar Animation</th>')
    out.append("</tr>")
    # Subheader row
    headers = [
        "Digital Human Avatars",
        "Prior Dataset Size",
        "Datasets",
        "Data Type",
        "Data Modality",
        "Needed Assets",
        "Input",
        "Additional Priors",
        "Req. Optimization",
        "Creation Speed",
        "Animation Signal",
        "Lighting Control",
        "Animation Speed",
        "Image Synthesis",
        "Image Refinement",
        "Contents",
    ]
    out.append("<tr>")
    for h in headers:
        out.append(f'<th class="th-sub" scope="col">{html.escape(h)}</th>')
    out.append("</tr>")
    out.append("</thead>")

    # Body
    out.append("<tbody>")
    ICON_COLUMNS = {
        "Datasets",
        "Data Type",
        "Data Modality",
        "Needed Assets",
        "Input",
        "Additional Priors",
        "Req. Optimization",
        "Creation Speed",
        "Animation Signal",
        "Lighting Control",
        "Animation Speed",
        "Image Synthesis",
        "Image Refinement",
        "Contents",
    }

    last_body_part = None
    for _, row in df.iterrows():
        body_part = row["__BodyPart__"]
        if body_part != last_body_part:
            # Section separator row
            out.append(
                f'<tr class="section-row"><td colspan="{len(headers)}">'
                f"{html.escape(str(body_part))}"
                "</td></tr>"
            )
            last_body_part = body_part

        cells = []
        bib_key = str(row["Bib ref"]).strip()
        method = row["__MethodName__"] or bib_key
        # Method name cell — clickable to show BibTeX popup
        bibtex = BIBTEX.get(bib_key, "")
        if bibtex:
            cells.append(
                '<button class="bib-btn" '
                f'data-bibkey="{html.escape(bib_key)}" '
                f'data-bibtex="{html.escape(bibtex)}">'
                f"{html.escape(method)}"
                "</button>"
            )
        else:
            cells.append(format_plain(method))

        # Remaining columns according to headers list
        for col in headers[1:]:
            val = row.get(col, "")
            if col in ICON_COLUMNS:
                cells.append(render_icon_cell(val, col))
            else:
                cells.append(format_plain(val))

        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    out.append("</tbody></table></div>")

    (TABLES_DIR / "taxonomy.html").write_text("\n".join(out), encoding="utf-8")
    print("✅ Wrote tables/taxonomy.html")


def build_datasets_table():
    """Build datasets HTML table matching the LaTeX datasets.tex structure."""
    df_raw = pd.read_csv(CSV_DATASETS, encoding="utf-8-sig")
    subhdr = [str(x).strip() for x in df_raw.iloc[0].tolist()]
    df = df_raw.loc[1:, :].copy()
    df.columns = subhdr

    # Columns matching LaTeX: Dataset (Name+Bib), Body Parts, Data Type, Data Modality, Size, # Cameras, Is Calibrated
    display_cols = ["Body Parts", "Data Type", "Data Modality", "Size", "# Cameras", "Is Calibrated"]
    display_cols = [c for c in display_cols if c in df.columns]

    ICON_COLUMNS = {"Body Parts", "Data Type", "Data Modality", "Is Calibrated"}

    # Parse datasets.tex to get the dataset crbox macro names and order
    datasets_tex = SRC / "datasets.tex"
    dataset_order: List[str] = []  # bib keys in LaTeX order
    if datasets_tex.exists():
        tex_text = datasets_tex.read_text(encoding="utf-8")
        for m in re.finditer(r"\\cite\{([^}]+)\}", tex_text):
            dataset_order.append(m.group(1).strip())

    # Reorder df to match LaTeX order if available
    if dataset_order:
        bib_col = "Bib ref"
        idx_map = {k: i for i, k in enumerate(dataset_order)}
        df = df[df[bib_col].astype(str).str.strip().isin(set(dataset_order))].copy()
        df["__rank__"] = df[bib_col].astype(str).str.strip().map(idx_map)
        df = df.sort_values("__rank__", kind="stable").drop(columns="__rank__")

    out = []
    out.append('<div class="latex-table-wrapper">')
    out.append('<table class="datasets-table latex-table">')
    # Header - matching LaTeX column headers
    out.append("<thead>")
    out.append("<tr>")
    out.append('<th class="th-sub" scope="col">Dataset</th>')
    for h in display_cols:
        out.append(f'<th class="th-sub th-prior" scope="col">{html.escape(h)}</th>')
    out.append("</tr>")
    out.append("</thead>")

    out.append("<tbody>")
    for row_idx, (_, row) in enumerate(df.iterrows()):
        bib_key = str(row["Bib ref"]).strip()
        name = str(row.get("Name", bib_key)).strip()

        # Build dataset name cell: crbox badge + name with BibTeX button
        # Try to find crbox macro for this dataset
        # The macro name pattern: crbox + sanitized name from datasets.tex
        crbox_badge = ""
        # Search for matching crbox by looking at the datasets.tex content
        crbox_key = name.replace(" ", "").replace("-", "").replace(".", "")
        # Try common patterns
        for candidate in [f"crbox{crbox_key}", f"crbox{name.replace(' ', '')}"]:
            if candidate in CRBOX_MACROS:
                crbox_badge = render_crbox(candidate, tooltip=name)
                break

        bibtex = BIBTEX.get(bib_key, "")
        if bibtex:
            name_html = (
                f'{crbox_badge} '
                f'<button class="bib-btn" '
                f'data-bibkey="{html.escape(bib_key)}" '
                f'data-bibtex="{html.escape(bibtex)}">'
                f"{html.escape(name)}"
                f"</button>"
            )
        else:
            name_html = f"{crbox_badge} {html.escape(name)}"

        # Alternating row color like LaTeX (blue!04 on even rows)
        row_class = ' class="row-alt"' if row_idx % 2 == 1 else ""

        cells = [name_html]
        for col in display_cols:
            val = row.get(col, "")
            if col in ICON_COLUMNS:
                cells.append(render_icon_cell(val, col))
            else:
                cells.append(format_plain(val))

        out.append(f"<tr{row_class}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    out.append("</tbody></table></div>")

    (TABLES_DIR / "datasets.html").write_text("\n".join(out), encoding="utf-8")
    print("✅ Wrote tables/datasets.html")


def build_legend_table():
    """Build legend HTML table matching LaTeX legend.tex with 3 stages and grouped rows."""
    LEGEND_CONFIG: Dict = latex_table.LEGEND_CONFIG

    # Stage colors matching LaTeX
    STAGE_COLORS = {
        "Prior Stage": ("#e5f4ea", "ForestGreen"),
        "Creation Stage": ("#e3efff", "RoyalBlue"),
        "Animation Stage": ("#ffe9d8", "BurntOrange"),
    }

    # Category row background colors (matching LaTeX \rowcolor)
    CATEGORY_ROW_BG = {
        "Prior Stage": {1: "rgba(0,128,0,0.04)"},      # green!04 on even rows
        "Creation Stage": {1: "rgba(0,0,255,0.04)"},    # blue!04 on even rows
        "Animation Stage": {1: "rgba(255,165,0,0.04)"}, # orange!04 on even rows
    }

    out = []
    out.append('<div class="latex-table-wrapper">')
    out.append('<table class="legend-table latex-table">')
    out.append("<thead><tr>"
               '<th class="th-sub">Category</th>'
               '<th class="th-sub">Icons</th>'
               "</tr></thead>")
    out.append("<tbody>")

    for stage_name, categories in LEGEND_CONFIG.items():
        bg_color, _ = STAGE_COLORS.get(stage_name, ("#f0f0f0", "gray"))

        # Stage header row
        out.append(
            f'<tr class="section-row">'
            f'<td colspan="2" style="background:{bg_color};font-weight:700;text-align:center;">'
            f"{html.escape(stage_name)}</td></tr>"
        )

        alt_bg = CATEGORY_ROW_BG.get(stage_name, {})
        for cat_idx, category in enumerate(categories):
            # Parse category config: can be string or tuple
            if isinstance(category, tuple):
                cat_name, items_list = category
            else:
                cat_name = category
                items_list = None

            # Build icon entries for this category row
            icon_parts: List[str] = []

            if items_list:
                # Explicit item order
                for item in items_list:
                    if isinstance(item, tuple):
                        key, display_label = item
                    else:
                        key = item
                        display_label = item

                    rendered = render_single_value(key)
                    if rendered == html.escape(key):
                        # Wasn't found in icon/crbox mappings; try the display label
                        rendered = render_single_value(display_label)
                    icon_parts.append(
                        f'<span class="legend-item legend-filter-btn" '
                        f'data-filter-field="{html.escape(cat_name)}" '
                        f'data-filter-value="{html.escape(key)}">'
                        f'{rendered}'
                        f'<span class="legend-label">{html.escape(display_label)}</span></span>'
                    )
            else:
                # Auto-collect from legend.tex by matching category
                items_for_cat = _get_items_for_category(cat_name)
                for label, macro_name in items_for_cat:
                    rendered = _render_macro(macro_name)
                    icon_parts.append(
                        f'<span class="legend-item legend-filter-btn" '
                        f'data-filter-field="{html.escape(cat_name)}" '
                        f'data-filter-value="{html.escape(label)}">'
                        f'{rendered}'
                        f'<span class="legend-label">{html.escape(label)}</span></span>'
                    )

            row_bg = ""
            if cat_idx % 2 == 1 and 1 in alt_bg:
                row_bg = f' style="background:{alt_bg[1]}"'

            out.append(
                f"<tr{row_bg}><td>{html.escape(cat_name)}</td>"
                f'<td class="legend-icons-cell">{"".join(icon_parts)}</td></tr>'
            )

    out.append("</tbody></table></div>")

    (TABLES_DIR / "legend.html").write_text("\n".join(out), encoding="utf-8")
    print("✅ Wrote tables/legend.html")


def _render_macro(macro_name: str) -> str:
    """Render a LaTeX macro name (ico* or crbox*) to HTML."""
    # Try as icon image first
    icon_path = MACRO_TO_ICON.get(macro_name)
    if icon_path:
        src = f"assets/img/icons/{icon_path}"
        return (
            f'<span class="icon-cell">'
            f'<img src="{src}" alt="{html.escape(macro_name)}" loading="lazy" />'
            f"</span>"
        )
    # Try as crbox badge
    if macro_name in CRBOX_MACROS:
        tooltip = CRBOX_TO_LABEL.get(macro_name, "")
        return render_crbox(macro_name, tooltip=tooltip)
    return html.escape(macro_name)


def _get_items_for_category(cat_name: str) -> List[tuple]:
    """Get legend items for a category by parsing legend.tex.

    Returns list of (label, macro_name) tuples.
    """
    legend_tex = SRC / "legend.tex"
    if not legend_tex.exists():
        return []
    text = legend_tex.read_text(encoding="utf-8")
    escaped = re.escape(cat_name)
    pattern = re.compile(
        rf"^\s*{escaped}\s*&\s*\n?(.*?)\\\\",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return []
    val_text = m.group(1)
    # Extract \val{label}{\scalebox{0.9}{\macroName}} entries
    # The macro is always the last \word before the closing braces
    items = re.findall(r"\\val\{([^}]*)\}\{\\scalebox\{[^}]*\}\{\\(\w+)\}\}", val_text)
    return items  # list of (label, macro_name)


def _render_combined_table_html(
    table_css_class: str,
    title: str,
    groups: Dict[str, int],
    headers: List[str],
    icon_columns: set,
    sections: List[tuple],
    search_id: str = "",
) -> str:
    """Render an HTML table from structured section data.

    Each entry in *sections* is ``(section_name, [row_dict, ...])``.
    A *row_dict* has keys ``method_name``, ``bib_key``, ``fields``.
    """
    total_cols = len(headers)
    out: List[str] = []

    # --- Sticky search bar ---
    if search_id:
        out.append(f'<div class="table-find-bar" id="{search_id}-bar">')
        out.append(f'  <div class="table-find-input-wrap">')
        out.append(f'    <svg class="pub-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>')
        out.append(f'    <input type="text" id="{search_id}" class="pub-search" placeholder="Search {title.lower()}\u2026" />')
        out.append(f'    <span class="table-find-count" id="{search_id}-count"></span>')
        out.append(f'    <button class="table-find-nav" id="{search_id}-prev" title="Previous match">')
        out.append(f'      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>')
        out.append(f'    </button>')
        out.append(f'    <button class="table-find-nav" id="{search_id}-next" title="Next match">')
        out.append(f'      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>')
        out.append(f'    </button>')
        out.append(f'  </div>')
        out.append(f'</div>')

    out.append('<div class="latex-table-wrapper">')
    out.append(f'<table class="{table_css_class} latex-table">')

    # --- Header ---
    group_classes = ["th-prior", "th-creation", "th-animation"]
    out.append("<thead>")
    out.append("<tr>")
    out.append('<th class="th-group th-metadata"></th>')
    for i, (gname, gspan) in enumerate(groups.items()):
        cls = group_classes[i] if i < len(group_classes) else "th-prior"
        out.append(f'<th class="th-group {cls}" colspan="{gspan}">{html.escape(gname)}</th>')
    out.append("</tr>")

    out.append("<tr>")
    for idx, h in enumerate(headers):
        label = "Reference" if idx == 0 else h
        out.append(f'<th class="th-sub" scope="col">{html.escape(label)}</th>')
    out.append("</tr>")
    out.append("</thead>")

    # --- Body ---
    out.append("<tbody>")
    for section_name, rows in sections:
        if not rows:
            continue
        out.append(
            f'<tr class="section-row"><td colspan="{total_cols}">'
            f"{html.escape(str(section_name))}</td></tr>"
        )
        for row in rows:
            cells: List[str] = []

            # Method name cell — clickable to show BibTeX popup
            bib_key = row["bib_key"]
            method = row["method_name"]
            bibtex = BIBTEX.get(bib_key, "")
            if bibtex:
                cells.append(
                    '<button class="bib-btn" '
                    f'data-bibkey="{html.escape(bib_key)}" '
                    f'data-bibtex="{html.escape(bibtex)}">'
                    f"{html.escape(method)}</button>"
                )
            else:
                cells.append(format_plain(method))

            for col in headers[1:]:
                val = row["fields"].get(col, "")
                if col in icon_columns:
                    cells.append(render_icon_cell(val, col))
                else:
                    cells.append(format_plain(val))
            out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")

    # --- Scroll-to-match search script ---
    if search_id:
        out.append("<script>")
        out.append("(function() {")
        out.append(f'  var searchEl = document.getElementById("{search_id}");')
        out.append(f'  var countEl = document.getElementById("{search_id}-count");')
        out.append(f'  var prevBtn = document.getElementById("{search_id}-prev");')
        out.append(f'  var nextBtn = document.getElementById("{search_id}-next");')
        out.append('  if (!searchEl) return;')
        out.append(f'  var table = document.querySelector("#{search_id}-bar ~ .latex-table-wrapper .latex-table");')
        out.append('  if (!table) return;')
        out.append('  var allRows = Array.from(table.querySelectorAll("tbody tr:not(.section-row)"));')
        # Build search index: for each row, combine method name + bibtex authors + bibtex title
        out.append('  function stripDiacritics(s) {')
        out.append('    return s.replace(/\u00df/g, "ss").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "");')
        out.append('  }')
        out.append('  var rowTexts = allRows.map(function(row) {')
        out.append('    var btn = row.querySelector(".bib-btn");')
        out.append('    var parts = [];')
        out.append('    var firstCell = row.querySelector("td");')
        out.append('    if (firstCell) parts.push(firstCell.textContent);')
        out.append('    if (btn) {')
        out.append('      var bib = (btn.getAttribute("data-bibtex") || "").replace(/[{}\\\\]/g, "");')
        out.append('      parts.push(bib);')
        out.append('      parts.push(btn.getAttribute("data-bibkey") || "");')
        out.append('    }')
        out.append('    return stripDiacritics(parts.join(" ").toLowerCase());')
        out.append('  });')
        # Match state
        out.append('  var matches = [], curIdx = -1;')
        out.append('  function clearHighlights() {')
        out.append('    for (var i = 0; i < allRows.length; i++) allRows[i].classList.remove("find-match", "find-current");')
        out.append('  }')
        out.append('  function doSearch() {')
        out.append('    clearHighlights();')
        out.append('    var q = stripDiacritics(searchEl.value.toLowerCase().trim());')
        out.append('    matches = []; curIdx = -1;')
        out.append('    if (!q) { countEl.textContent = ""; return; }')
        out.append('    var words = q.replace(/[()\\[\\]{}]/g, "").split(/\\s+/).filter(Boolean);')
        out.append('    for (var i = 0; i < allRows.length; i++) {')
        out.append('      var ok = true;')
        out.append('      for (var wi = 0; wi < words.length; wi++) {')
        out.append('        if (rowTexts[i].indexOf(words[wi]) < 0) { ok = false; break; }')
        out.append('      }')
        out.append('      if (ok) { matches.push(i); allRows[i].classList.add("find-match"); }')
        out.append('    }')
        out.append('    if (matches.length > 0) { curIdx = 0; goTo(0); }')
        out.append('    else { countEl.textContent = "0 results"; }')
        out.append('  }')
        out.append('  function goTo(idx) {')
        out.append('    if (matches.length === 0) return;')
        out.append('    if (curIdx >= 0 && curIdx < matches.length) allRows[matches[curIdx]].classList.remove("find-current");')
        out.append('    curIdx = ((idx % matches.length) + matches.length) % matches.length;')
        out.append('    var row = allRows[matches[curIdx]];')
        out.append('    row.classList.add("find-current");')
        out.append('    row.scrollIntoView({ behavior: "smooth", block: "center" });')
        out.append('    countEl.textContent = (curIdx + 1) + " / " + matches.length;')
        out.append('  }')
        out.append('  searchEl.addEventListener("input", doSearch);')
        out.append('  searchEl.addEventListener("keydown", function(e) {')
        out.append('    if (e.key === "Enter") { e.preventDefault(); if (e.shiftKey) goTo(curIdx - 1); else goTo(curIdx + 1); }')
        out.append('  });')
        out.append('  prevBtn.addEventListener("click", function() { goTo(curIdx - 1); });')
        out.append('  nextBtn.addEventListener("click", function() { goTo(curIdx + 1); });')
        out.append("})();")
        out.append("</script>")

    return "\n".join(out)


def _load_curated_rows(csv_path: Path, order_path: Path) -> tuple:
    """Load curated rows from a CSV + ordering file (papers.txt or assets.txt).

    Returns ``(sections_dict, curated_keys_set)`` where *sections_dict*
    maps section name to list of row dicts.
    """
    curated_sections: Dict[str, List[dict]] = defaultdict(list)
    curated_keys: set = set()
    if not csv_path.exists() or not order_path.exists():
        return curated_sections, curated_keys

    df_raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    subhdr = df_raw.iloc[0].tolist()
    cols_keep: List = []
    subhdr_keep: List[str] = []
    for i, c in enumerate(df_raw.columns):
        label = str(subhdr[i])
        if not any(label.strip().lower() == r.lower() for r in COLUMNS_TO_REMOVE):
            cols_keep.append(c)
            subhdr_keep.append(label)
    df = df_raw.loc[1:, cols_keep].copy()
    df.columns = subhdr_keep

    order_dict, key_list, name_list = latex_table.load_order_from_papers(order_path)
    shortname_by_key = dict(zip(key_list, name_list))

    for section, keys in order_dict.items():
        for key in keys:
            match = df[df["Bib ref"].astype(str).str.strip() == key]
            if match.empty:
                continue
            row = match.iloc[0]
            fields: Dict[str, str] = {}
            for col in subhdr_keep:
                if col == subhdr_keep[0]:
                    continue  # skip first col (Author / method)
                val = row.get(col, "")
                fields[col] = "" if is_empty(val) else str(val).strip()
            curated_sections[section].append(
                {
                    "method_name": shortname_by_key.get(key, key),
                    "bib_key": key,
                    "fields": fields,
                }
            )
            curated_keys.add(key)
    return curated_sections, curated_keys


# ---------------------------------------------------------------------------
# Combined table builders (CSV curated + JSON auto-classified)
# ---------------------------------------------------------------------------

AVATAR_SECTION_ORDER = ["Face", "Full-body", "Hands", "Hair", "Garment", "Teeth", "Tongue"]
ASSETS_SECTION_ORDER = ["Hair", "Garment", "Face", "Full-body", "Hands", "Teeth", "Tongue"]

AVATAR_GROUPS = {"Avatar Prior": 4, "Avatar Creation": 5, "Avatar Animation": 6}
AVATAR_HEADERS = [
    "Digital Human Avatars",
    "Prior Dataset Size", "Datasets", "Data Type", "Data Modality",
    "Needed Assets", "Input", "Additional Priors", "Req. Optimization", "Creation Speed",
    "Animation Signal", "Lighting Control", "Animation Speed",
    "Image Synthesis", "Image Refinement", "Contents",
]
AVATAR_ICON_COLS = {
    "Datasets", "Data Type", "Data Modality", "Needed Assets", "Input",
    "Additional Priors", "Req. Optimization", "Creation Speed",
    "Animation Signal", "Lighting Control", "Animation Speed",
    "Image Synthesis", "Image Refinement", "Contents",
}

ASSETS_GROUPS = {"Assets Prior": 4, "Assets Creation": 8}
ASSETS_HEADERS = [
    "Digital Human Assets",
    "Prior Dataset Size", "Datasets", "Data Type", "Data Modality",
    "Needed Assets", "Input", "Additional Priors", "Creation Speed",
    "Representation", "Simulation Ready", "Lighting Control", "Contents",
]
ASSETS_ICON_COLS = {
    "Datasets", "Data Type", "Data Modality", "Needed Assets", "Input",
    "Additional Priors", "Creation Speed", "Representation",
    "Simulation Ready", "Lighting Control", "Contents",
}


def _merge_sections(
    section_order: List[str],
    curated: Dict[str, List[dict]],
    extras: Dict[str, List[dict]],
) -> List[tuple]:
    """Merge curated and extra rows into an ordered list of (section, rows)."""
    merged: List[tuple] = []
    seen: set = set()
    for section in section_order:
        rows = list(curated.get(section, []))
        rows.extend(sorted(extras.pop(section, []), key=lambda r: r["bib_key"].lower()))
        if rows:
            merged.append((section, rows))
        seen.add(section)
    for section in sorted(extras.keys()):
        if section in seen:
            continue
        rows = sorted(extras[section], key=lambda r: r["bib_key"].lower())
        if rows:
            merged.append((section, rows))
    return merged


def build_combined_taxonomy_table():
    """Build tables/taxonomy.html merging curated CSV with JSON classifications."""
    curated, curated_keys = _load_curated_rows(CSV_AVATAR, PAPERS_TXT)

    extras: Dict[str, List[dict]] = defaultdict(list)
    if JSON_FILE.exists():
        avatars, _, _ = load_json_classifications(JSON_FILE)
        for item in avatars:
            key = item["key"]
            if key in curated_keys:
                continue
            item["fields"] = normalize_fields(item["fields"])
            section = normalize_contents(item["fields"].get("Contents", ""))
            extras[section].append(
                {"method_name": key[:1].upper() + key[1:] if key else key, "bib_key": key, "fields": item["fields"]}
            )

    all_sections = _merge_sections(AVATAR_SECTION_ORDER, curated, extras)
    table_html = _render_combined_table_html(
        "taxonomy-table", "Digital Human Avatars",
        AVATAR_GROUPS, AVATAR_HEADERS, AVATAR_ICON_COLS, all_sections,
        search_id="taxonomy-search",
    )

    total = sum(len(rows) for _, rows in all_sections)
    (TABLES_DIR / "taxonomy.html").write_text(table_html, encoding="utf-8")
    print(
        f"✅ Wrote tables/taxonomy.html "
        f"({len(curated_keys)} curated + {total - len(curated_keys)} auto-classified)"
    )


def build_combined_assets_table():
    """Build tables/assets.html merging curated CSV with JSON classifications."""
    curated, curated_keys = _load_curated_rows(CSV_ASSETS, ASSETS_TXT)

    extras: Dict[str, List[dict]] = defaultdict(list)
    if JSON_FILE.exists():
        _, assets, _ = load_json_classifications(JSON_FILE)
        for item in assets:
            key = item["key"]
            if key in curated_keys:
                continue
            item["fields"] = normalize_fields(item["fields"])
            section = normalize_contents(item["fields"].get("Contents", ""))
            extras[section].append(
                {"method_name": key[:1].upper() + key[1:] if key else key, "bib_key": key, "fields": item["fields"]}
            )

    all_sections = _merge_sections(ASSETS_SECTION_ORDER, curated, extras)
    table_html = _render_combined_table_html(
        "assets-table", "Digital Human Assets",
        ASSETS_GROUPS, ASSETS_HEADERS, ASSETS_ICON_COLS, all_sections,
        search_id="assets-search",
    )

    total = sum(len(rows) for _, rows in all_sections)
    (TABLES_DIR / "assets.html").write_text(table_html, encoding="utf-8")
    print(
        f"✅ Wrote tables/assets.html "
        f"({len(curated_keys)} curated + {total - len(curated_keys)} auto-classified)"
    )


def main():
    build_combined_taxonomy_table()
    build_combined_assets_table()
    build_datasets_table()
    build_legend_table()


if __name__ == "__main__":
    main()
