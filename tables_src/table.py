from collections import defaultdict
from typing import Dict, List, Tuple

import pandas as pd
import re
from pathlib import Path

csv_path = 'STAR - Digital Humans Taxonomy - Avatar.csv'
csv_path_assets = 'STAR - Digital Humans Taxonomy - Assets.csv'
csv_path_datasets = 'STAR - Digital Humans Taxonomy - Datasets.csv'
bib_path = 'bibliography.bib'
papers_path = 'papers.txt'  # list of references to select
papers_path_assets = 'assets.txt'  # list of references to select

# ------- Configuration: Columns to remove -------
COLUMNS_TO_REMOVE = [
    'GPU Days',
    'Time of Creation',
    'Time of Anim.',
    'Double Checked',
    'Reviewer'
]

# ------- Configuration: Which columns should contain colorful letterboxes (usually free-text columns) ----------
LETTERBOX_COLUMNS = [
    'Datasets',
    'Needed Assets',
    'Additional Priors',
    'Image Synthesis',
    'Representation'
]

# ------- Configuration: Table column specifier for selected columns. If nothing specified 'l' will be used ----------
DEFAULT_COLUMN_WIDTH = '1.1cm'
COLUMN_WIDTHS = {
    'Datasets': '1.8cm',
    'Data Modality': '1.5cm',
    'Req. Opt.': '0.8cm',
    'Image Refinement': '0.8cm',
    'Creation Speed': '0.8cm',
    'Animation Signal': '0.8cm',
    'Lighting Control': '0.8cm',
    'Animation Speed': '0.8cm',
    'Image Synthesis': '0.8cm',
}

COLUMN_WIDTHS_ASSETS = {
    'Data Modality': '1.5cm',
}

# ------- Configuration: Background colors for the 3 column groups (Prior, Creation, Animation) ----------
GROUP_COLORS = [
    'ForestGreen!10',
    'RoyalBlue!10',
    'BurntOrange!10',
]

# ------- Configuration: Flags ----------
USE_ALTERNATE_ROW_COLORS = True  # Whether to use alternating colors for each row instead of \hline
USE_BODY_PART_GROUP_LABEL = True  # Whether to use a \multirow label on the left indicating each body part

# ------- Legend mapping from legend.tex -------
LEGEND_MAPPING = {
    # ===== Prior Stage =====
    # Type
    'Real': r'\icoReal',
    'Synthetic': r'\icoSynth',
    'Generated': r'\icoGenerated',

    # Datasets
    'Internal': r'\icoInternal',
    'VFHQ': r'\icoVFHQ',
    'FFHQ': r'\icoFFHQ',
    'InterHand2.6M': r'\icoInterHand',
    'THuman2.1': r'\icoTHuman',
    'ActorsHQ': r'\icoActorsHQ',
    'Human4DiT': r'\icoHumanFourDiT',
    'ZJUMoCap': r'\icoZJUMoCap',
    'NeRSemble': r'\icoNeRSemble',
    'CelebVHQ': r'\icoCelebVHQ',
    'Ava-256': r'\icoAva',

    # Modality
    'Single image': r'\icoSingleImage',
    'Multi-view image': r'\icoMultiImage',
    'OLAT multi-view image': r'\icoOLATImage',
    'Mono video': r'\icoMonoVideo',
    'Multi-view video': r'\icoMultiViewVideo',
    'OLAT multi-view video': r'\icoOLATVideo',
    'Meshes': r'\icoMeshes',
    'MRI': r'\icoMRI',
    '3D Strands': r'\icoStrands',

    # ===== Creation Stage =====
    # Inputs
    'Zero': r'\icoZero',
    'One': r'\icoOne',
    'Few': r'\icoFew',
    'Input Mono video': r'\icoInputMonoVideo',
    'Input Multi-view video': r'\icoInputMultiVideo',
    'Input OLAT video': r'\icoInputOLATVideo',
    'Multi-view images': r'\icoMultiImage',
    'Depth': r'\icoDepth',
    'Audio': r'\icoAudio',
    'Video': r'\icoVideo',
    'OLAT multi-view images': r'\icoOLATImage',
    'Text': r'\icoText',
    '3D density volume': r'\icoMRI',
    'Point cloud': r'\icoPointCloud',

    # Needed assets
    'Tracked 3DMM': r'\icoThreeDMM',
    'Cameras': r'\icoCameras',
    'Registered Meshes': r'\icoMeshesReg',
    'Textures': r'\icoTextures',
    '3DMM': r'\icoThreeDMM',
    'Sewing Pattern': r'\icoSewingPattern',

    # Speed
    'Instant': r'\icoInstant',
    'Fast': r'\icoFast',
    'Medium': r'\icoMedium',
    'Slow': r'\icoSlow',

    # ===== Animation Stage =====
    # Animation Signal
    '3DMM expr': r'\icoExprThreeDMM',
    'General expr': r'\icoExprGeneral',
    'Anim Audio': r'\icoAnimAudio',
    'Anim Video': r'\icoAnimVideo',
    'Anim Text': r'\icoAnimText',
    'Pose': r'\icoPose',
    'Simulation': r'\icoSimulation',
    'Multi-view Image': r'\icoMultiViewVideo',

    # Lighting
    'None Light': r'\icoNoLight',
    'Local Light': r'\icoLocalLight',
    'Distant Light': r'\icoDistantLight',

    # Animation Speed
    'Real-time': r'\icoRealtime',
    'Interactive': r'\icoInteractive',
    'Offline': r'\icoOffline',

    # Representation / Modalities
    'Mesh': r'\icoMesh',
    'Strands': r'\icoStrands',
    '3DGS': r'\icoThreeDGS',
    'MVP': r'\icoMVP',
    'Neural Field': r'\icoNeuralField',
    'NeRF': r'\icoNeRF',
    'GAN': r'\icoGAN',

    # Body parts
    'Face': r'\icoFace',
    'Hair': r'\icoHair',
    'Full-body': r'\icoBody',
    'Hands': r'\icoHand',
    'Garment': r'\icoGarment',
    'Teeth': r'\icoTeeth',
    'Tongue': r'\icoTongue',

    # Generic booleans
    'Yes': r'\icoYes',
    'No': r'\icoNo',
    'TRUE': r'\icoYes',
    'FALSE': r'\icoNo',
    'True': r'\icoYes',
    'False': r'\icoNo',
}

# ------- Configuration: Which categories should appear in legend.tex ----------
# stage => [category | (category, [label order])]
LEGEND_CONFIG = {
    'Prior Stage': [
        "Datasets",
        ("Data Type", [
            'Real',
            'Synthetic',
            ('Generated', 'Generated (e.g., by a pre-trained generative model)')
        ]),
        "Data Modality",
    ],

    'Creation Stage': [
        "Needed Assets",
        ('Input', ['Text', 'Audio', 'Zero', 'One', 'Few', 'Mono video', 'Multi-view images', 'Multi-view video', 'OLAT multi-view images', 'OLAT multi-view video', 'Meshes', 'Depth', '3D density volume', 'Point cloud']),
        "Additional Priors",
        ("Creation Speed", [
            ('Slow', 'Slow (>6 hours)'),
            ('Medium', 'Medium (<6 hours)'),
            ('Fast', 'Fast (<30 minutes)'),
            ('Instant', 'Instant (<1 minute)'),
        ]),
    ],

    'Animation Stage': [
        "Animation Signal",
        "Lighting Control",
        ("Animation Speed", [
            ('Offline', 'Offline (<1 fps)'),
            ('Interactive', 'Interactive (>5 fps)'),
            ('Real-time', 'Real-time (>30 fps)')]),
        "Image Synthesis"
    ],
}


# ===== Helpers =====
def strip_control(s):
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\t")


def tex_escape(s):
    s = strip_control(s)
    for a, b in [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"),
                 ("_", "\\_"), ("{", "\\{"), ("}", "\\}"), ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}")]:
        s = s.replace(a, b)
    return s


def display_single_value(cleaned: str):
    # cleaned = clean_single_value(value)

    # Direct match first
    if cleaned in LEGEND_MAPPING:
        return LEGEND_MAPPING[cleaned]

    # Try lowercase substring heuristics
    value_lower = cleaned.lower()
    for key in LEGEND_MAPPING:
        if key.lower() in value_lower:
            return LEGEND_MAPPING[key]

    # Fallback to escaped text
    return tex_escape(cleaned)


# def get_legend_value(t):
#     if not t or pd.isna(t): return ''
#     t=str(t).strip()
#     for d in [',',';','|','+','&',' and ',' + ',' & ']:
#         if d in t:
#             return ' '.join(parse_single_value(p) for p in t.split(d) if p.strip())
#     return parse_single_value(t)

def clean_single_value(value):
    value = value.strip()
    if not value:
        return ''

    # Normalize by removing anything inside parentheses, brackets, etc.
    cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', value).strip()

    return cleaned


def get_legend_values(t) -> List[str]:
    if not t or pd.isna(t): return ''
    t = str(t).strip()
    for d in [',', ';', '|', '+', '&', ' and ', ' + ', ' & ']:
        if d in t:
            return [clean_single_value(p) for p in t.split(d) if p.strip()]

    if t.strip():
        return [clean_single_value(t)]
    else:
        return []


def get_letterbox_values(t) -> List[str]:
    if not t or pd.isna(t): return []
    t = str(t).strip()
    for d in [',', ';', '|', '+', '&', ' and ', ' + ', ' & ']:
        if d in t:
            parts = [p.strip() for p in t.split(d)]
            letterbox_values = parts
            return letterbox_values
            # return ' '.join(f"\\crbox{''.join(ch for ch in p if ch.isalpha())}" for p in parts if p)
    return [t]
    # return f"\\crbox{''.join(ch for ch in t if ch.isalpha())}"


def display_single_letterbox(value: str) -> str:
    return f"\\crbox{''.join(ch for ch in value if ch.isalpha())}"


def load_order_from_papers(path) -> Tuple[Dict[str, List[str]], List[str], List[str]]:
    ordered_papers = defaultdict(list)
    current_key = None
    keys = []
    paper_names = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s: continue
            if set(s) == {'='} or s.startswith('=') or s.endswith('='):
                current_key = s.replace('=', '').strip()
                continue
            if s.lower() in {'face', 'full-body', 'hands', 'hair', 'garment'}: continue
            parts = s.split(' ')
            key = parts[-1]
            paper_name = ' '.join(parts[:-1])
            ordered_papers[current_key].append(key)
            keys.append(key)
            paper_names.append(paper_name)
    return ordered_papers, keys, paper_names


# ===== Load CSV =====
df0 = pd.read_csv(csv_path, encoding='utf-8-sig')

# SAFELY drop the last two columns (no KeyError on chained drops)
if df0.shape[1] >= 2:
    df0 = df0.iloc[:, :-2]
elif df0.shape[1] == 1:
    # leave it as-is; nothing to drop
    pass

df0 = df0.map(lambda x: strip_control("" if pd.isna(x) else str(x)))
df0.fillna('', inplace=True)
subhdr = df0.iloc[0].tolist();
subhdr[0] = 'Author'

cols_keep, subhdr_keep = [], []
for i, c in enumerate(df0.columns):
    if not any(subhdr[i].strip().lower() == r.lower() for r in COLUMNS_TO_REMOVE):
        cols_keep.append(c)
        subhdr_keep.append(subhdr[i])
df0 = df0[cols_keep];
subhdr = subhdr_keep

escaped_subhdr = ['Author'] + [tex_escape(h) for h in subhdr[1:]]
df0_cols = df0.columns.tolist()
df = df0.iloc[1:].copy()
df.dropna(subset=[df0_cols[0]], inplace=True)
feature_cols = df0_cols[1:]
df = df.loc[df[feature_cols].astype(bool).any(axis=1)]
column_names = df0.loc[0].values

# ===== Filter strictly by papers.txt =====
order_dict, order_list, paper_names = load_order_from_papers(papers_path)
body_part_per_paper = [body_part for body_part, papers in order_dict.items() for _ in range(len(papers))]
ref_col = df.columns[0]
available_papers = df[ref_col].astype(str).str.strip().tolist()
missing_paper_ids = [i for i, paper in enumerate(order_list) if paper not in available_papers]
missing_papers = [order_list[i] for i in missing_paper_ids]
found_order_dict = {body_part: [paper for paper in papers if paper in available_papers] for body_part, papers in order_dict.items()}
df = df[df[ref_col].astype(str).str.strip().isin(order_list)]

if missing_papers:
    print(f"[WARNING] The following papers were specified in {papers_path} but are not available in the csv!")
    for paper in missing_papers:
        print(f" - {paper}")

if df.empty:
    print("Warning: No matching references found between CSV and papers.txt.")
else:
    idx_map = {k: i for i, k in enumerate(order_list)}
    df = df.copy()
    df['__rank__'] = df[ref_col].astype(str).str.strip().map(idx_map)
    df = df.sort_values('__rank__', kind='stable').drop(columns='__rank__')
    df['__body_part__'] = [body_part for i, body_part in enumerate(body_part_per_paper) if not i in missing_paper_ids]
    df['__paper_name__'] = [paper_name for i, paper_name in enumerate(paper_names) if not i in missing_paper_ids]

print(f"Selected {len(df)} rows matching papers.txt ({len(order_list)} listed).")

# =====================================
# Render main LaTeX table: taxonomy.tex
# =====================================
groups = {'Avatar Prior': 4, 'Avatar Creation': 5, 'Avatar Animation': 6}
body_part_groups = {body_part: len(papers) for body_part, papers in found_order_dict.items()}

author_re = re.compile(r'([A-Za-z]+)')
lines = [
    r'\begin{table*}[th!]',
    r'  \centering',
    r'  \footnotesize',
    r'  \setlength{\tabcolsep}{2pt}',
    r'  \resizebox{\textwidth}{!}{%',
]
col_defs = ''
if USE_BODY_PART_GROUP_LABEL:
    col_defs = '|l|'

col_defs += 'l|'
i_col = 1
for span in groups.values():
    for _ in range(span):
        if column_names[i_col] in COLUMN_WIDTHS:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{COLUMN_WIDTHS[column_names[i_col]]}}}'
        else:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{DEFAULT_COLUMN_WIDTH}}}'
        i_col += 1
    col_defs += '|'
# NiceTabular environment is necessary for the following reasons:
#   - Proper background colors in table cells (regular tabular environment has bugs where vertical lines or text may disappear behind the background)
#   - Proper vertical centering of the body part labels
lines.append(f'  \\begin{{NiceTabular}}{{{col_defs}}}[colortbl-like]')
lines.append(r'   \toprule')
top_cells = ['']
for i, (name, span) in enumerate(groups.items()):
    col_seps = '&' * (span - 1)# if i != len(groups) - 1 else ''
    top_cells.append(rf'\Block[fill={GROUP_COLORS[i]}]{{1-{span}}}{{\textbf{{{tex_escape(name)}}}}} {col_seps}')
if USE_BODY_PART_GROUP_LABEL:
    top_row = r'\Block[B]{2-2}{\includegraphics[height=1.9cm]{icons/table_logos/table_logo_avatars.png}\\\\ \textbf{Digital Human Avatars}} &'
else:
    top_row = r'\Block{2-1}{\textbf{Author}}'
lines.append(top_row + ' & '.join(top_cells) + r' \\')

hdr = []
if USE_BODY_PART_GROUP_LABEL:
    hdr.append('&')
# hdr.append(r'\textbf{Author}')
count = 0
for i, (name, span) in enumerate(groups.items()):
    for _ in range(span):
        hdr.append(rf'\rot{{\cellcolor{{{GROUP_COLORS[i]}}}\textbf{{{escaped_subhdr[1 + count]}}}}}')
        count += 1
lines.append('    ' + ' & '.join(hdr) + r' \\')

collected_legend = defaultdict(set)  # col name => {(icon, value)}

# ------------- Row loop ----------------
for i_row, (_, row) in enumerate(df.iterrows()):
    is_new_section = i_row == 0 or df.iloc[i_row]['__body_part__'] != df.iloc[i_row - 1]['__body_part__']

    if not USE_ALTERNATE_ROW_COLORS:
        if USE_BODY_PART_GROUP_LABEL and not is_new_section:
            lines.append(rf'    \cline{{2-{len(df0_cols) + 1}}}')
        else:
            lines.append(r'    \hline')

    body_part = df.iloc[i_row]['__body_part__']
    if is_new_section:
        if USE_ALTERNATE_ROW_COLORS:
            # lines.append(r'    \hline')
            lines.append(r'    \midrule')
        if USE_BODY_PART_GROUP_LABEL:
            lines.append(rf"    \Block{{{body_part_groups[body_part]}-1}}{{\rotate {body_part}}}")
    cells = []
    for i, key in enumerate(df0_cols):
        v = row[key]
        if pd.isna(v) or v == '':
            cells.append('')
        else:
            txt = str(v).strip()
            # use raw string to avoid SyntaxWarning for \i
            if r"\ico" in txt:
                cells.append(txt)
            elif i == 0:
                paper_name = row['__paper_name__']
                if paper_name == '?':
                    m = author_re.match(txt)
                    name = m.group(1) if m else txt
                    name = tex_escape(name).capitalize()
                    cells.append(f'{name} \\etal~\\cite{{{txt}}}')
                else:
                    cells.append(f"{paper_name}~\\cite{{{txt}}}")
            elif column_names[i] in LETTERBOX_COLUMNS:
                letterbox_values = get_letterbox_values(txt)
                letterbox_displays = [display_single_letterbox(v) for v in letterbox_values]

                letterbox_values_and_displays = zip(letterbox_values, letterbox_displays)
                letterbox_values_and_displays = sorted(letterbox_values_and_displays, key=lambda x: x[0])

                cells.append(' '.join([d for _, d in letterbox_values_and_displays]))

                for letterbox_value, letterbox_display in letterbox_values_and_displays:
                    collected_legend[column_names[i]].add((letterbox_display, letterbox_value))
            else:
                legend_values = get_legend_values(txt)
                legend_displays = [display_single_value(v) for v in legend_values]
                cells.append(' '.join(legend_displays))

                for legend_value, legend_display in zip(legend_values, legend_displays):
                    collected_legend[column_names[i]].add((legend_display, legend_value))
    cell_cmd = ' & '
    if USE_ALTERNATE_ROW_COLORS and i_row % 2 == 0:
        cell_cmd += rf"\cellcolor{{blue!04}}"
    lines.append(cell_cmd + cell_cmd.join(cells) + r' \\')

lines += [
    r'  \bottomrule',
    r'  \end{NiceTabular}',
    r'  }',
    r'  \caption{Digital Humans Taxonomy: We show representative state-of-the-art methods for human faces, bodies and hands.}',
    r'  \label{tab:taxonomy}',
    r'\end{table*}'
]

with open('taxonomy.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("✅ Wrote taxonomy.tex")

# ===============================================================================================================================
# Create assets table: assets.tex
# ===============================================================================================================================

df0 = pd.read_csv(csv_path_assets, encoding='utf-8-sig')

# SAFELY drop the last two columns (no KeyError on chained drops)
if df0.shape[1] >= 2:
    df0 = df0.iloc[:, :-2]
elif df0.shape[1] == 1:
    # leave it as-is; nothing to drop
    pass

df0 = df0.map(lambda x: strip_control("" if pd.isna(x) else str(x)))
df0.fillna('', inplace=True)
subhdr = df0.iloc[0].tolist();
subhdr[0] = 'Author'

cols_keep, subhdr_keep = [], []
for i, c in enumerate(df0.columns):
    if not any(subhdr[i].strip().lower() == r.lower() for r in COLUMNS_TO_REMOVE):
        cols_keep.append(c)
        subhdr_keep.append(subhdr[i])
df0 = df0[cols_keep];
subhdr = subhdr_keep

escaped_subhdr = ['Author'] + [tex_escape(h) for h in subhdr[1:]]
df0_cols = df0.columns.tolist()
df = df0.iloc[1:].copy()
df.dropna(subset=[df0_cols[0]], inplace=True)
feature_cols = df0_cols[1:]
df = df.loc[df[feature_cols].astype(bool).any(axis=1)]
column_names = df0.loc[0].values

# ===== Filter strictly by assets.txt =====
order_dict, order_list, paper_names = load_order_from_papers(papers_path_assets)
body_part_per_paper = [body_part for body_part, papers in order_dict.items() for _ in range(len(papers))]
ref_col = df.columns[0]
available_papers = df[ref_col].astype(str).str.strip().tolist()
missing_paper_ids = [i for i, paper in enumerate(order_list) if paper not in available_papers]
missing_papers = [order_list[i] for i in missing_paper_ids]
found_order_dict = {body_part: [paper for paper in papers if paper in available_papers] for body_part, papers in order_dict.items()}
df = df[df[ref_col].astype(str).str.strip().isin(order_list)]

if missing_papers:
    print(f"[WARNING] The following papers were specified in {papers_path_assets} but are not available in the csv!")
    for paper in missing_papers:
        print(f" - {paper}")

if df.empty:
    print(f"Warning: No matching references found between CSV and {papers_path_assets}.")
else:
    idx_map = {k: i for i, k in enumerate(order_list)}
    df = df.copy()
    df['__rank__'] = df[ref_col].astype(str).str.strip().map(idx_map)
    df = df.sort_values('__rank__', kind='stable').drop(columns='__rank__')
    df['__body_part__'] = [body_part for i, body_part in enumerate(body_part_per_paper) if not i in missing_paper_ids]
    df['__paper_name__'] = [paper_name for i, paper_name in enumerate(paper_names) if not i in missing_paper_ids]

print(f"Selected {len(df)} rows matching {papers_path_assets} ({len(order_list)} listed).")

# -------------------------------------
# Render main LaTeX table: assets.tex
# -------------------------------------
groups = {'Assets Prior': 4, 'Assets Creation': 8}
body_part_groups = {body_part: len(papers) for body_part, papers in found_order_dict.items()}

author_re = re.compile(r'([A-Za-z]+)')
lines = [
    r'\begin{table*}[th!]',
    r'  \centering',
    r'  \footnotesize',
    r'  \setlength{\tabcolsep}{2pt}',
    r'  \resizebox{\textwidth}{!}{%',
]
col_defs = ''
if USE_BODY_PART_GROUP_LABEL:
    col_defs = '|l|'
col_defs += 'l|'
i_col = 1
for span in groups.values():
    for _ in range(span):
        if column_names[i_col] in COLUMN_WIDTHS_ASSETS:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{COLUMN_WIDTHS_ASSETS[column_names[i_col]]}}}'
        else:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{DEFAULT_COLUMN_WIDTH}}}'
        i_col += 1
    col_defs += '|'

# NiceTabular environment is necessary for the following reasons:
#   - Proper background colors in table cells (regular tabular environment has bugs where vertical lines or text may disappear behind the background)
#   - Proper vertical centering of the body part labels
lines.append(f'  \\begin{{NiceTabular}}{{{col_defs}}}[colortbl-like]')
lines.append(r'   \toprule')
top_cells = ['']
for i, (name, span) in enumerate(groups.items()):
    col_seps = '&' * (span - 1) #if i != len(groups) - 1 else ''
    top_cells.append(rf'\Block[fill={GROUP_COLORS[i]}]{{1-{span}}}{{\textbf{{{tex_escape(name)}}}}} {col_seps}')
if USE_BODY_PART_GROUP_LABEL:
    top_row = r'\Block[B]{2-2}{\includegraphics[height=1.9cm]{icons/table_logos/table_logo_assets.png}\\\\ \textbf{Digital Human Assets}} &'
else:
    top_row = r'\Block{2-1}{\textbf{Author}}'
lines.append(top_row + ' & '.join(top_cells) + r' \\')

hdr = []
if USE_BODY_PART_GROUP_LABEL:
    hdr.append('&')
# hdr.append(r'\textbf{Author}')
count = 0
for i, (name, span) in enumerate(groups.items()):
    for _ in range(span):
        hdr.append(rf'\rot{{\cellcolor{{{GROUP_COLORS[i]}}}\textbf{{{escaped_subhdr[1 + count]}}}}}')
        count += 1
lines.append('    ' + ' & '.join(hdr) + r' \\')

# ------------- Row loop ----------------
for i_row, (_, row) in enumerate(df.iterrows()):
    is_new_section = i_row == 0 or df.iloc[i_row]['__body_part__'] != df.iloc[i_row - 1]['__body_part__']

    if not USE_ALTERNATE_ROW_COLORS:
        if USE_BODY_PART_GROUP_LABEL and not is_new_section:
            lines.append(rf'    \cline{{2-{len(df0_cols) + 1}}}')
        else:
            lines.append(r'    \hline')

    body_part = df.iloc[i_row]['__body_part__']
    if is_new_section:
        if USE_ALTERNATE_ROW_COLORS:
            # lines.append(r'    \hline')
            lines.append(r'    \midrule')
        if USE_BODY_PART_GROUP_LABEL:
            lines.append(rf"    \Block{{{body_part_groups[body_part]}-1}}{{\rotate {body_part}}}")
    cells = []
    for i, key in enumerate(df0_cols):
        v = row[key]
        if pd.isna(v) or v == '':
            cells.append('')
        else:
            txt = str(v).strip()
            # use raw string to avoid SyntaxWarning for \i
            if r"\ico" in txt:
                cells.append(txt)
            elif i == 0:
                paper_name = row['__paper_name__']
                if paper_name == '?':
                    m = author_re.match(txt)
                    name = m.group(1) if m else txt
                    name = tex_escape(name).capitalize()
                    cells.append(f'{name} \\etal~\\cite{{{txt}}}')
                else:
                    cells.append(f"{paper_name}~\\cite{{{txt}}}")
            elif column_names[i] in LETTERBOX_COLUMNS:
                letterbox_values = get_letterbox_values(txt)
                letterbox_displays = [display_single_letterbox(v) for v in letterbox_values]

                letterbox_values_and_displays = zip(letterbox_values, letterbox_displays)
                letterbox_values_and_displays = sorted(letterbox_values_and_displays, key=lambda x: x[0])

                cells.append(' '.join([d for _, d in letterbox_values_and_displays]))

                for letterbox_value, letterbox_display in letterbox_values_and_displays:
                    collected_legend[column_names[i]].add((letterbox_display, letterbox_value))

                    if column_names[i] == 'Representation':
                        collected_legend['Image Synthesis'].add((letterbox_display, letterbox_value))  # Add Representations to Image Synthesis column
            else:
                legend_values = get_legend_values(txt)
                legend_displays = [display_single_value(v) for v in legend_values]
                cells.append(' '.join(legend_displays))

                for legend_value, legend_display in zip(legend_values, legend_displays):
                    collected_legend[column_names[i]].add((legend_display, legend_value))
    cell_cmd = ' & '
    if USE_ALTERNATE_ROW_COLORS and i_row % 2 == 0:
        cell_cmd += rf"\cellcolor{{blue!04}}"
    lines.append(cell_cmd + cell_cmd.join(cells) + r' \\')

lines += [
    r'  \bottomrule',
    r'  \end{NiceTabular}',
    r'  }',
    r'  \caption{Digital Human Assets Taxonomy: We show representative state-of-the-art methods for human avatar assets like hair and garments.}',
    r'  \label{tab:assets}',
    r'\end{table*}'
]

with open('assets.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("✅ Wrote assets.tex")

# ===============================================================================================================================
# Create assets table: datasets.tex
# ===============================================================================================================================

USE_BODY_PART_GROUP_LABEL = False  # Not implemented for datasets table
df0 = pd.read_csv(csv_path_datasets, encoding='utf-8-sig')

# SAFELY drop the last column (no KeyError on chained drops)
if df0.shape[1] >= 1:
    df0 = df0.iloc[:, :-1]
elif df0.shape[1] == 1:
    # leave it as-is; nothing to drop
    pass

df0 = df0.map(lambda x: strip_control("" if pd.isna(x) else str(x)))
df0.fillna('', inplace=True)
subhdr = df0.iloc[0].tolist();
subhdr[0] = 'Author'

cols_keep, subhdr_keep = [], []
for i, c in enumerate(df0.columns):
    if not any(subhdr[i].strip().lower() == r.lower() for r in COLUMNS_TO_REMOVE):
        cols_keep.append(c)
        subhdr_keep.append(subhdr[i])
df0 = df0[cols_keep];
subhdr = subhdr_keep

escaped_subhdr = ['Author'] + [tex_escape(h) for h in subhdr[1:]]
df0_cols = df0.columns.tolist()
df = df0.iloc[1:].copy()
df.dropna(subset=[df0_cols[0]], inplace=True)
feature_cols = df0_cols[1:]
df = df.loc[df[feature_cols].astype(bool).any(axis=1)]
column_names = df0.loc[0].values

# # ===== Filter strictly by assets.txt =====
# order_dict, order_list, paper_names = load_order_from_papers(papers_path_assets)
# body_part_per_paper = [body_part for body_part, papers in order_dict.items() for _ in range(len(papers))]
# ref_col = df.columns[0]
# available_papers = df[ref_col].astype(str).str.strip().tolist()
# missing_paper_ids = [i for i, paper in enumerate(order_list) if paper not in available_papers]
# missing_papers = [order_list[i] for i in missing_paper_ids]
# found_order_dict = {body_part: [paper for paper in papers if paper in available_papers] for body_part, papers in order_dict.items()}
# df = df[df[ref_col].astype(str).str.strip().isin(order_list)]
#
# if missing_papers:
#     print(f"[WARNING] The following papers were specified in {papers_path_assets} but are not available in the csv!")
#     for paper in missing_papers:
#         print(f" - {paper}")
#
# if df.empty:
#     print(f"Warning: No matching references found between CSV and {papers_path_assets}.")
# else:
#     idx_map = {k: i for i, k in enumerate(order_list)}
#     df = df.copy()
#     df['__rank__'] = df[ref_col].astype(str).str.strip().map(idx_map)
#     df = df.sort_values('__rank__', kind='stable').drop(columns='__rank__')
#     df['__body_part__'] = [body_part for i, body_part in enumerate(body_part_per_paper) if not i in missing_paper_ids]
#     df['__paper_name__'] = [paper_name for i, paper_name in enumerate(paper_names) if not i in missing_paper_ids]

# print(f"Selected {len(df)} rows matching {papers_path_assets} ({len(order_list)} listed).")

# -------------------------------------
# Render LaTeX table: datasets.tex
# -------------------------------------
groups = {'Dataset': 6}
body_part_groups = {body_part: len(papers) for body_part, papers in found_order_dict.items()}

author_re = re.compile(r'([A-Za-z]+)')
lines = [
    r'\begin{table*}[th!]',
    r'  \centering',
    r'  \footnotesize',
    r'  \setlength{\tabcolsep}{2pt}',
    # r'  \resizebox{\textwidth}{!}{%',
]
col_defs = ''
if USE_BODY_PART_GROUP_LABEL:
    col_defs = 'l|'
# col_defs += 'l|'
col_defs += 'l'
i_col = 1
for span in groups.values():
    for _ in range(span):
        if column_names[i_col] in COLUMN_WIDTHS:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{COLUMN_WIDTHS[column_names[i_col]]}}}'
        else:
            col_defs += f'>{{\\centering\\arraybackslash}}p{{{DEFAULT_COLUMN_WIDTH}}}'
        i_col += 1
    # col_defs += '|'

# NiceTabular environment is necessary for the following reasons:
#   - Proper background colors in table cells (regular tabular environment has bugs where vertical lines or text may disappear behind the background)
#   - Proper vertical centering of the body part labels
lines.append(f'  \\begin{{NiceTabular}}{{{col_defs}}}[colortbl-like]')
# top_cells = ['']
# for i, (name, span) in enumerate(groups.items()):
#     col_seps = '&' * (span - 1) #if i != len(groups) - 1 else ''
#     top_cells.append(rf'\Block[fill={GROUP_COLORS[i]}]{{1-{span}}}{{\textbf{{{tex_escape(name)}}}}} {col_seps}')
# if USE_BODY_PART_GROUP_LABEL:
#     top_row = '    & '
# else:
#     top_row = '     '
# lines.append(top_row + ' & '.join(top_cells) + r' \\')
lines.append('    \\toprule')

hdr = []
if USE_BODY_PART_GROUP_LABEL:
    hdr.append('')
hdr.append(r'\textbf{Dataset}')
count = 0
for i, (name, span) in enumerate(groups.items()):
    for _ in range(span):
        hdr.append(rf'\rot{{\cellcolor{{{GROUP_COLORS[i]}}}\textbf{{{escaped_subhdr[2 + count]}}}}}')
        count += 1
lines.append('    ' + ' & '.join(hdr) + r' \\')

lines.append('    \\midrule')

used_datasets_with_icons = {d[1]: d[0] for d in collected_legend['Datasets']}
listed_datasets = []
# ------------- Row loop ----------------
i_dataset = 0
for i_row, (_, row) in enumerate(df.iterrows()):
    dataset_name = row.iloc[1]
    if dataset_name not in used_datasets_with_icons:
        continue

    # is_new_section = i_row == 0 or df.iloc[i_row]['__body_part__'] != df.iloc[i_row - 1]['__body_part__']
    is_new_section = i_row == 0

    if not USE_ALTERNATE_ROW_COLORS:
        if USE_BODY_PART_GROUP_LABEL and not is_new_section:
            lines.append(rf'    \cline{{2-{len(df0_cols) + 1}}}')
        else:
            lines.append(r'    \hline')

    body_part = None
    if is_new_section:
        if USE_ALTERNATE_ROW_COLORS:
            # lines.append(r'    \hline')
            lines.append(r'    \midrule')
        if USE_BODY_PART_GROUP_LABEL:
            lines.append(rf"    \Block{{{body_part_groups[body_part]}-1}}{{\rotate {body_part}}}")
    cells = []
    for i, key in enumerate(df0_cols):
        v = row[key]
        if pd.isna(v) or v == '':
            cells.append('')
        else:
            txt = str(v).strip()
            # use raw string to avoid SyntaxWarning for \i
            if r"\ico" in txt:
                cells.append(txt)
            elif i == 0:
                cells.append(f'{{{used_datasets_with_icons[dataset_name]}}} {dataset_name}~\\cite{{{row.iloc[0]}}}')
                listed_datasets.append(row.iloc[1])
            elif i == 1:
                # Dataset name is already used in first column
                continue
            elif column_names[i] in LETTERBOX_COLUMNS:
                letterbox_values = get_letterbox_values(txt)
                letterbox_displays = [display_single_letterbox(v) for v in letterbox_values]

                letterbox_values_and_displays = zip(letterbox_values, letterbox_displays)
                letterbox_values_and_displays = sorted(letterbox_values_and_displays, key=lambda x: x[0])

                cells.append(' '.join([d for _, d in letterbox_values_and_displays]))

                for letterbox_value, letterbox_display in letterbox_values_and_displays:
                    collected_legend[column_names[i]].add((letterbox_display, letterbox_value))
            else:
                legend_values = get_legend_values(txt)
                legend_displays = [display_single_value(v) for v in legend_values]
                cells.append(' '.join(legend_displays))

                for legend_value, legend_display in zip(legend_values, legend_displays):
                    collected_legend[column_names[i]].add((legend_display, legend_value))
    cell_cmd = ' & '
    if USE_ALTERNATE_ROW_COLORS and i_dataset % 2 == 0:
        cell_cmd += rf"\cellcolor{{blue!04}}"
    lines.append(cell_cmd.join(cells) + r' \\')
    i_dataset += 1

missing_datasets = set(used_datasets_with_icons).difference(listed_datasets)
if 'Internal' in missing_datasets:
    missing_datasets.remove('Internal')
if missing_datasets:
    print("[WARNING] The following datasets are used in the Avatars/Assets tables, but are not defined in the Datasets sheet:")
    for dset in missing_datasets:
        print(f" - {dset}")

lines += [
    r'  \bottomrule',
    r'  \end{NiceTabular}',
    # r'  }',
    r'  \caption{Overview of commonly used digital human datasets, detailing covered body parts (face, body, hands, garments, hair), data types (real, synthetic, or generated), and modalities (images, videos, meshes, strands).}',
    r'  \label{tab:datasets}',
    r'\end{table*}'
]

with open('datasets.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("✅ Wrote datasets.tex")

# =====================================
# Render Legend LaTeX table: legend.tex
# =====================================

lines = [
    r'\begin{table*}[th!]',
    r'  \centering',
    r'  \small',
    r'  \setlength{\tabcolsep}{4pt}',
    r'  \renewcommand{\arraystretch}{1.5}',
]
# col_defs = 'lX'
col_defs = 'lX'
lines.append(f'  \\begin{{NiceTabular}}{{{col_defs}}}[colortbl-like]')
# lines.append(f'  \\begin{{tabularx}}{{\\textwidth}}{{{col_defs}}}')
lines.append(f'   \\toprule')


for i_stage, (stage, categories) in enumerate(LEGEND_CONFIG.items()):
    lines.append(rf'\Block[fill={GROUP_COLORS[i_stage]}]{{1-2}}{{\textbf{{{stage}}}}} & \\')
    # lines.append(f'   \\rowcolor{{{GROUP_COLORS[i_stage]}}}')
    # lines.append(f'   \\multicolumn{{2}}{{@{{}}l}}{{}}} \\\\')
    lines.append(f'   \\midrule')

    i_row = 0
    for category in categories:
        if isinstance(category, tuple):
            # Order icons/labels by pre-defined order from LEGEND_CONFIG
            label_order = [l[1] if isinstance(l, tuple) else l for l in category[1]]
            label_mapping = dict()
            for l in category[1]:
                if isinstance(l, tuple):
                    label_mapping[l[0]] = l[1]
                else:
                    label_mapping[l] = l

            category = category[0]
            icons_and_descriptions = {k: label_mapping[v] if v in label_mapping else v for k, v in collected_legend[category]}.items()
            icons_and_descriptions = sorted(icons_and_descriptions, key=lambda x: label_order.index(x[1]))
        else:
            # Order icons/labels alphanumerically
            icons_and_descriptions = sorted(collected_legend[category], key=lambda x: x[1])

        if USE_ALTERNATE_ROW_COLORS and i_row % 2 == 1:
            if i_stage == 0:
                color = 'green'
            elif i_stage == 1:
                color = 'blue'
            else:
                color = 'orange'
            lines.append(rf"\rowcolor{{{color}!04}}")
        lines.append(f'   {category} &')

        icons_and_descriptions_displays = []
        for icon, description in icons_and_descriptions:
            icons_and_descriptions_displays.append(rf'\val{{{description}}}{{\scalebox{{0.9}}{{{icon}}}}}')

        lines.append('\\valsep'.join(icons_and_descriptions_displays))
        lines.append('\\\\')

        i_row += 1
    if i_stage == 2:
        lines.append(f'   \\bottomrule')
    else:
        lines.append(f'   \\midrule')

lines += [
    r'  \end{NiceTabular}',
    r'  \caption{Avatar pipeline taxonomy legend of the three stages: prior learning, avatar creation and avatar animation.}',
    r'  \label{tab:avatar_pipeline_taxonomy}',
    r'\end{table*}'
]

with open('legend.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("✅ Wrote legend.tex")
