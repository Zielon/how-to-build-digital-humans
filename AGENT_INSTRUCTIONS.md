# Instructions for LLM Agents: Adding and Classifying Papers

This document describes how to add new academic papers to the
**"How to Build Digital Humans"** survey website and correctly classify them
so they appear in the taxonomy tables, publications list, and statistics.

Read this entire document before making any changes.

---

## 1. Repository Structure Overview

```
├── tables_src/
│   ├── bibliography.bib           # Master BibTeX file (source of truth)
│   ├── build_publications.py      # Generates publications.html + publications.json
│   ├── build_tables.py            # Generates taxonomy/assets/datasets/legend HTML
│   ├── build_statistics.py        # Generates statistics.html (Chart.js charts)
│   ├── normalize_fields.py        # Canonical vocabulary mappings (shared)
│   ├── table.py                   # Legend config, icon mappings, CSV helpers
│   ├── papers.txt                 # Curated avatar table row ordering
│   ├── assets.txt                 # Curated assets table row ordering
│   ├── macros.tex                 # LaTeX icon/color macro definitions
│   ├── legend.tex                 # LaTeX legend source
│   ├── STAR - Digital Humans Taxonomy - Avatar.csv
│   ├── STAR - Digital Humans Taxonomy - Assets.csv
│   └── STAR - Digital Humans Taxonomy - Datasets.csv
├── classify/
│   ├── final_results.json         # Classification database
│   ├── auto_classify.py           # Heuristic auto-classifier
│   └── normalize_classifications.py  # Batch re-normalizer
├── assets/
│   ├── data/
│   │   ├── publications.json      # Generated consolidated JSON
│   │   └── abstracts/*.txt        # Paper abstracts (one per paper)
│   └── img/
│       ├── thumbnails/*.jpg       # Paper first-page thumbnails
│       └── icons/                 # Legend icon images
├── tables/                        # Generated HTML fragments (do not edit)
├── scripts/
│   ├── fetch_thumbnails.py        # Downloads PDF thumbnails from arXiv
│   ├── fetch_abstracts.py         # Fetches abstracts from arXiv API
│   ├── validate_new_entries.py    # PR validation (schema, venues, links)
│   └── check_assets.py            # Checks for missing thumbnails/abstracts
├── tests/
│   ├── test_publications.py       # ~70 tests for publications pipeline
│   └── test_build_pipeline.py     # ~25 tests for build artifacts
├── abbr.bib                       # 52 venue abbreviation macros
├── deploy.sh                      # Full build pipeline script
├── index.html                     # Main website page
└── llms.txt                       # LLM-readable site description
```

---

## 2. How to Add a New Paper

### Step 1: Add BibTeX Entry to `tables_src/bibliography.bib`

Every paper needs a BibTeX entry with four metadata comment lines immediately
above it. The comments attach to the **next** `@` entry.

```bibtex
% Webpage: https://project-page.example.com
% Code:    https://github.com/author/repo
% Video:   https://youtu.be/xxxx
% Arxiv:   https://arxiv.org/pdf/XXXX.XXXXX
@inproceedings{AuthorYear_shortname,
  author       = {First Author and Second Author and Third Author},
  title        = {Paper Title With Proper Capitalization},
  booktitle    = CVPR,
  year         = {2024},
}
```

#### Rules for the BibTeX entry:

1. **Citation key format**: `FirstAuthorSurname` + `Year` + `shortname`
   - Examples: `Zielonka2022mica`, `Kirschstein2023nersemble`, `Saito2024relightable`
   - The key must be unique across all entries

2. **Metadata comments**: All four lines are required. Use `None` if a link
   does not exist:
   ```
   % Webpage: None
   % Code:    None
   % Video:   None
   % Arxiv:   https://arxiv.org/pdf/2204.06607
   ```
   **Important**: At least one link must be a real URL (not `None`). Entries
   with all four set to `None` are filtered out of the website.

3. **Venue field**: Use a bare macro name from `abbr.bib` when possible:
   ```
   booktitle = CVPR,        % not {CVPR} or "CVPR"
   booktitle = ECCV,
   booktitle = ICCV,
   journal   = SIGGRAPH_TOG,
   journal   = PAMI,
   booktitle = NEURIPS,
   booktitle = ICLR,
   booktitle = ICML,
   journal   = TOG,
   ```
   For venues not in `abbr.bib`, use brace-delimited strings:
   ```
   booktitle = {3DV},
   journal   = {arXiv},
   ```

4. **LaTeX in titles**: Use standard LaTeX commands. The build system handles
   conversion of accents (`{\"o}` → ö), math mode (`$x^2$` → x²), and
   formatting commands (`\emph{text}` → text).

### Step 2: Add Abstract

Create a text file at `assets/data/abstracts/<key>.txt` containing the paper's
abstract as plain text. The filename must match the citation key (with any
non-alphanumeric characters except `_`, `.`, `-` replaced by `_`).

Example: for key `Zielonka2022mica`, create
`assets/data/abstracts/Zielonka2022mica.txt`.

If you have network access, you can run `python tables_src/fetch_abstracts.py`
to auto-fetch missing abstracts from the arXiv API.

### Step 3: Add Thumbnail

Place a JPEG thumbnail of the paper's first page at
`assets/img/thumbnails/<key>.jpg`.

Requirements:
- JPEG format, quality 85
- Approximately 850×1100 pixels
- Filename matches the citation key

If you have network access, run `python scripts/fetch_thumbnails.py` to
auto-download thumbnails from arXiv PDF links.

---

## 3. How to Classify a Paper

### Step 4: Add Classification to `classify/final_results.json`

This is the most important step. Each paper must be classified into one of
three categories:

1. **Avatar** (`avatar_classifications`): Methods that create animatable
   digital human avatars
2. **Assets** (`assets_classifications`): Methods that generate static digital
   human assets (hair strands, garments, body meshes, etc.)
3. **Skipped** (`skipped`): Papers that should not be classified (surveys,
   benchmarks, datasets, pose estimation, general-purpose models, etc.)

### Deciding: Avatar vs Assets vs Skip

| Classify as... | When the paper... |
|---|---|
| **Avatar** | Creates an animatable human representation (face, body, hands) that can be driven by signals (expressions, poses, audio, video) |
| **Assets** | Generates static/simulation-ready human components (hair strands, garment meshes, body scans) without real-time animation |
| **Skip** | Is a survey, benchmark, dataset paper, or does not create digital humans (e.g., pure pose estimation, scene reconstruction, general image synthesis) |

### Avatar Classification Fields

Add an entry to the `avatar_classifications` array:

```json
{
  "key": "AuthorYear_shortname",
  "table_type": "avatar",
  "fields": {
    "Prior Dataset Size": "<number or range>",
    "Datasets": "<comma-separated dataset names>",
    "Data Type": "<see vocabulary>",
    "Data Modality": "<see vocabulary>",
    "Needed Assets": "<see vocabulary>",
    "Input": "<see vocabulary>",
    "Additional Priors": "<comma-separated, e.g. FLAME, ArcFace>",
    "Req. Optimization": "<Yes or No>",
    "Creation Speed": "<see vocabulary>",
    "Animation Signal": "<see vocabulary>",
    "Lighting Control": "<see vocabulary>",
    "Animation Speed": "<see vocabulary>",
    "Image Synthesis": "<see vocabulary>",
    "Image Refinement": "<Yes or No>",
    "Contents": "<see vocabulary>"
  }
}
```

### Assets Classification Fields

Add an entry to the `assets_classifications` array:

```json
{
  "key": "AuthorYear_shortname",
  "table_type": "assets",
  "fields": {
    "Prior Dataset Size": "<number or range>",
    "Datasets": "<comma-separated dataset names>",
    "Data Type": "<see vocabulary>",
    "Data Modality": "<see vocabulary>",
    "Needed Assets": "<see vocabulary>",
    "Input": "<see vocabulary>",
    "Additional Priors": "<comma-separated>",
    "Creation Speed": "<see vocabulary>",
    "Representation": "<see vocabulary>",
    "Simulation Ready": "<Yes or No>",
    "Lighting Control": "<see vocabulary>",
    "Contents": "<see vocabulary>"
  }
}
```

### Skip Entry

Add an entry to the `skipped` array:

```json
{
  "key": "AuthorYear_shortname",
  "reason": "Brief explanation of why this paper was skipped, e.g. 'Survey paper on 3D face reconstruction. No novel method proposed.'"
}
```

### Optional Notes

For any classified entry (avatar or assets), you can add a `note` field:

```json
{
  "key": "AuthorYear_shortname",
  "table_type": "avatar",
  "fields": { ... },
  "note": "Uses a novel hybrid 3DGS+mesh representation. Related to AuthorYear2."
}
```

---

## 4. Controlled Vocabulary Reference

**You MUST use these exact canonical values.** The normalization system
(`normalize_fields.py`) will fix common aliases, but using canonical values
directly avoids issues.

### Contents (body part)

| Canonical Value | Common Aliases (auto-corrected) |
|---|---|
| `Face` | Head, Head only, Portrait |
| `Full-body` | Full Body, Body, Upper Body |
| `Hands` | Hand |
| `Hair` | — |
| `Garment` | Clothing, Garments |
| `Teeth` | — |
| `Tongue` | — |

Multiple values: `Face, Hair` (comma-separated).

### Data Type

| Canonical Value | Aliases |
|---|---|
| `Real` | — |
| `Synthetic` | — |
| `Real, Synthetic` | Both |

### Data Modality

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `Single image` | Image |
| `Multi-view image` | Multi-view images |
| `Mono video` | Video, Monocular video, Monocular RGB video, RGB-D video |
| `Multi-view video` | Dense multi-view video, Sparse multi-view video |
| `OLAT multi-view image` | — |
| `OLAT multi-view video` | — |
| `Meshes` | 3D scans, 3D Scans, 3D meshes |
| `MRI` | — |
| `3D Strands` | — |

### Needed Assets

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `Tracked 3DMM` | Tracked FLAME, Tracked SMPL, FLAME mesh, FLAME model, SMPL body model, SMPL-X body mesh, SMPL-X model, MANO hand model, 3D Body Model, 3D Skeleton |
| `Cameras` | — |
| `Registered Meshes` | — |
| `Textures` | — |
| `segmentation masks` | foreground masks |
| `Sewing Pattern` | — |
| `None` | — |

Multiple values: `Tracked 3DMM, Cameras` (comma-separated).

### Input

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `Zero` | Random noise |
| `One` | Single image, Single RGB image |
| `Few` | — |
| `Text` | Text prompt |
| `Audio` | — |
| `Mono video` | Monocular video |
| `Multi-view images` | — |
| `Multi-view video` | — |
| `Depth` | — |
| `Point cloud` | — |
| `3D density volume` | — |
| `OLAT multi-view images` | — |
| `OLAT multi-view video` | — |
| `Meshes` | — |
| `Video` | — |

### Creation Speed

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `Instant` | Feed-forward, feedforward inference |
| `Fast` | Seconds to minutes, Minutes |
| `Medium` | — |
| `Slow` | Hours, Per-subject training, per-video optimization |

Add a parenthetical qualifier for precision: `Instant (<1min)`, `Fast (1-10min)`,
`Slow (>6h)`.

### Animation Signal (avatar only)

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `3DMM expr` | FLAME expression code, FLAME expression |
| `General expr` | Latent expression code |
| `Pose` | 3D Skeleton Pose, 3D Body Pose, Body pose, Hand pose, SMPL body pose, Skeleton |
| `Audio` | — |
| `Video` | — |
| `Text` | — |
| `Simulation` | — |
| `Multi-view Image` | — |

### Lighting Control

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `None` | No |
| `Distant Light` | Environment Map, Spherical Harmonics, HDRI |
| `Local Light` | — |

### Animation Speed (avatar only)

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `Real-time` | — |
| `Interactive` | Near real-time |
| `Offline` | Not real-time |

Add a parenthetical qualifier: `Real-time (>30 FPS)`, `Interactive (1-30 FPS)`,
`Offline (<1 FPS)`.

### Image Synthesis (avatar) / Representation (assets)

| Canonical Value | Aliases (auto-corrected) |
|---|---|
| `3DGS` | 3D Gaussian Splatting, Gaussian Splatting |
| `NeRF` | neural radiance field |
| `Mesh` | Mesh-based |
| `Neural Rendering` | Diffusion, Video Diffusion, 2D Diffusion, GAN, Point-based rendering, Ray tracing, Deferred neural rendering |
| `MVP` | — |
| `SDF` | — |
| `Neural Field` | — |
| `Strands` | — |

### Req. Optimization / Image Refinement / Simulation Ready

Boolean fields: `Yes` or `No`.

---

## 5. Complete Example: Adding a Paper End-to-End

Suppose you want to add the paper "GaussianHead: High-fidelity Head Avatars
with Learnable Gaussian Derivation" by Wang et al. (CVPR 2024).

### 5.1 Add BibTeX entry

Append to `tables_src/bibliography.bib`:

```bibtex
% Webpage: https://gaussianhead.github.io/
% Code:    https://github.com/chiehwangs/gaussian-head
% Video:   None
% Arxiv:   https://arxiv.org/pdf/2312.01632
@inproceedings{Wang2024gaussianhead,
  author       = {Jiale Wang and others},
  title        = {GaussianHead: High-fidelity Head Avatars with Learnable Gaussian Derivation},
  booktitle    = CVPR,
  year         = {2024},
}
```

### 5.2 Add abstract

Create `assets/data/abstracts/Wang2024gaussianhead.txt`:

```
We propose GaussianHead, a method for creating high-fidelity 3D head avatars...
```

### 5.3 Add thumbnail

Place `assets/img/thumbnails/Wang2024gaussianhead.jpg` (first page of the PDF,
850×1100px JPEG).

### 5.4 Add classification

Add to `classify/final_results.json` in the `avatar_classifications` array:

```json
{
  "key": "Wang2024gaussianhead",
  "table_type": "avatar",
  "fields": {
    "Prior Dataset Size": "1",
    "Datasets": "NeRSemble",
    "Data Type": "Real",
    "Data Modality": "Multi-view video",
    "Needed Assets": "Tracked 3DMM, Cameras",
    "Input": "Multi-view video",
    "Additional Priors": "FLAME",
    "Req. Optimization": "Yes",
    "Creation Speed": "Slow (>6h)",
    "Animation Signal": "3DMM expr",
    "Lighting Control": "None",
    "Animation Speed": "Real-time (>30 FPS)",
    "Image Synthesis": "3DGS",
    "Image Refinement": "No",
    "Contents": "Face"
  }
}
```

### 5.5 Update metadata counts

Update the `metadata` section at the top of `final_results.json`:

```json
"metadata": {
  "total_classified": 470,
  "avatar_count": 363,
  "assets_count": 107,
  "skipped_count": 72
}
```

### 5.6 Build and test

```bash
# Build all generated HTML and JSON
cd tables_src
python build_tables.py
python build_publications.py
python build_statistics.py

# Run tests to verify
cd ..
python -m pytest tests/ -v
```

---

## 6. Build Pipeline

The scripts must run in this order (each depends on the previous):

```
1. python tables_src/build_tables.py
     → tables/taxonomy.html, assets.html, datasets.html, legend.html

2. python tables_src/build_publications.py
     → tables/publications.html, assets/data/publications.json

3. python tables_src/build_statistics.py
     → tables/statistics.html
```

Or run everything at once:

```bash
bash deploy.sh
```

**Note**: `deploy.sh` also runs `fetch_thumbnails.py` and `fetch_abstracts.py`
first (requires network access), then updates cache-bust timestamps in
`index.html`.

---

## 7. Validation Checks

### Automated checks that run on PRs:

1. **`tests.yml`**: Runs `pytest` — 118 tests covering:
   - Build artifact generation (all HTML files exist and are non-empty)
   - CSV schema validation
   - Vocabulary consistency (no alias values in generated output)
   - No duplicate legend labels
   - JSON export structure and field validation

2. **`validate-entry.yml`**: Runs when `publications.json` changes:
   - Schema validation (required fields, types, year range 1990–2030)
   - At least one non-null link per entry
   - URL format checking
   - Venue validation against known venues
   - Duplicate detection (matching keys or fuzzy-similar titles)

3. **`check-assets.yml`**: Runs when `publications.json` changes:
   - Checks for missing thumbnails and abstracts
   - Creates/updates a GitHub issue listing missing assets

### Running validation locally:

```bash
# Full test suite
python -m pytest tests/ -v

# Validate publications.json schema
python scripts/validate_new_entries.py assets/data/publications.json

# Check for missing assets
python scripts/check_assets.py
```

---

## 8. Common Mistakes to Avoid

1. **Wrong field names**: Use exact Title Case names (`Data Modality`, not
   `data_modality` or `Data modality`). The normalizer handles `snake_case`
   conversion but not arbitrary casing.

2. **Using alias values**: Always use canonical values from Section 4. While
   the normalizer fixes known aliases, unknown variants will leak through and
   create duplicate legend entries.

3. **Missing metadata comments**: All four `% Webpage/Code/Video/Arxiv` lines
   must appear immediately before the `@` entry. Missing lines cause metadata
   to leak from the previous entry.

4. **Duplicate citation keys**: Each key must be unique. The validation script
   catches this, but fixing it after the fact is more work.

5. **Forgetting to update metadata counts**: The `metadata` block at the top
   of `final_results.json` must reflect the actual counts of
   `avatar_classifications`, `assets_classifications`, and `skipped` arrays.

6. **Not rebuilding**: After editing `bibliography.bib` or
   `final_results.json`, you must re-run the build scripts. The HTML files in
   `tables/` and `assets/data/publications.json` are generated — do not edit
   them directly.

7. **Classifying non-method papers**: Survey papers, benchmark papers, dataset
   papers, and papers that do not propose a method for creating digital humans
   should go in the `skipped` array with a reason.

---

## 9. Field-by-Field Classification Guide

When classifying a paper, answer these questions:

| Field | Question to Ask |
|---|---|
| **Prior Dataset Size** | How many subjects/identities are in the training dataset? |
| **Datasets** | Which named datasets does the method train on? |
| **Data Type** | Does it use real captured data, synthetic data, or both? |
| **Data Modality** | What form is the input data? (images, video, meshes, etc.) |
| **Needed Assets** | What pre-existing assets does it need? (tracked meshes, cameras, etc.) |
| **Input** | What does the method take as input at inference time? |
| **Additional Priors** | What pretrained models or parametric models does it use? (FLAME, SMPL, etc.) |
| **Req. Optimization** | Does it need per-subject optimization, or is it feed-forward? |
| **Creation Speed** | How long does it take to create an avatar for a new subject? |
| **Animation Signal** | What drives the animation? (expressions, pose, audio, text, etc.) |
| **Lighting Control** | Can the lighting be changed? (none, distant light, local light) |
| **Animation Speed** | How fast is rendering during animation? |
| **Image Synthesis** | What is the core rendering representation? |
| **Image Refinement** | Is there a post-processing refinement network (e.g., super-resolution)? |
| **Contents** | What body part does this address? |
| **Representation** | (Assets only) What is the output representation? |
| **Simulation Ready** | (Assets only) Can the output be used in physics simulation? |

---

## 10. Batch Operations

### Adding multiple papers at once

1. Add all BibTeX entries to `bibliography.bib` (with metadata comments)
2. Add all classifications to `final_results.json`
3. Run `python classify/normalize_classifications.py` to batch-normalize
4. Run the build pipeline (Section 6)
5. Run tests (Section 7)

### Auto-classifying unclassified papers

```bash
python classify/auto_classify.py
```

This uses heuristic regex patterns on titles and abstracts. Review the output
in `final_results.json` — auto-classifications are approximate and may need
manual correction.

---

## 11. File Format Details

### `papers.txt` / `assets.txt` (Curated Row Ordering)

These files control the row order for curated entries in the taxonomy/assets
tables. Format:

```
======= Face =======

DisplayName bibkey1
AnotherMethod bibkey2

======= Full-body =======

MethodName bibkey3
```

Only add entries here if the paper is a key/representative method that should
appear in the curated (top) section of the table. Most papers are auto-placed
via their `final_results.json` classification.

### `bibliography.bib` (Venue Macros)

Common venue macros defined in `abbr.bib`:

| Macro | Resolves To |
|---|---|
| `CVPR` | Conference on Computer Vision and Pattern Recognition (CVPR) |
| `ECCV` | European Conference on Computer Vision (ECCV) |
| `ICCV` | International Conference on Computer Vision (ICCV) |
| `SIGGRAPH_TOG` | Transactions on Graphics, (Proc. SIGGRAPH) |
| `SIGGRAPH_ASIA` | Transactions on Graphics, (Proc. SIGGRAPH Asia) |
| `NEURIPS` | Advances in Neural Information Processing Systems (NeurIPS) |
| `ICLR` | International Conference on Learning Representations (ICLR) |
| `ICML` | International Conference on Machine Learning (ICML) |
| `PAMI` | Transactions on Pattern Analysis and Machine Intelligence (TPAMI) |
| `TOG` | Transactions on Graphics (TOG) |
| `AAAI` | AAAI Conference on Artificial Intelligence (AAAI) |

The build system resolves these macros and then further shortens the venue
names for display (e.g., the full CVPR name becomes just "CVPR").
