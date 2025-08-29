"""Tests for the full build pipeline.

Verifies that build_tables.py, build_publications.py, and build_statistics.py
produce all expected HTML artifacts, and that generated output uses canonical
vocabulary (no alias values leaking through).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tables_src"
TABLES_DIR = ROOT / "tables"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# table.py (imported by build_tables.py) uses bare relative paths for CSVs,
# so it must be imported with CWD set to tables_src/.
_original_cwd = os.getcwd()
os.chdir(SRC)
try:
    from build_tables import main as build_tables_main  # noqa: E402
finally:
    os.chdir(_original_cwd)


# ===================================================================
# 1. Build Tables — artifact generation
# ===================================================================
class TestBuildTablesArtifacts:
    """Run build_tables.main() and verify all output files."""

    @pytest.fixture(scope="class", autouse=True)
    def run_build(self):
        build_tables_main()

    @pytest.mark.parametrize("filename", [
        "taxonomy.html",
        "assets.html",
        "datasets.html",
        "legend.html",
    ])
    def test_artifact_exists_and_nonempty(self, filename):
        path = TABLES_DIR / filename
        assert path.exists(), f"{filename} was not generated"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"{filename} is suspiciously small ({len(content)} bytes)"

    def test_taxonomy_has_rows(self):
        html = (TABLES_DIR / "taxonomy.html").read_text(encoding="utf-8")
        assert "<tr" in html, "taxonomy.html contains no table rows"

    def test_assets_has_rows(self):
        html = (TABLES_DIR / "assets.html").read_text(encoding="utf-8")
        assert "<tr" in html, "assets.html contains no table rows"

    def test_datasets_has_rows(self):
        html = (TABLES_DIR / "datasets.html").read_text(encoding="utf-8")
        assert "<tr" in html, "datasets.html contains no table rows"

    def test_legend_has_filter_buttons(self):
        html = (TABLES_DIR / "legend.html").read_text(encoding="utf-8")
        assert "Data Modality" in html or "data-modality" in html.lower(), \
            "legend.html missing Data Modality section"


# ===================================================================
# 2. Build Statistics — artifact generation
# ===================================================================
class TestBuildStatisticsArtifacts:
    """Run build_statistics and verify output."""

    @pytest.fixture(scope="class", autouse=True)
    def run_build(self):
        from build_publications import build_publications_page
        build_publications_page()
        from build_statistics import main as build_statistics_main
        build_statistics_main()

    def test_statistics_html_exists(self):
        path = TABLES_DIR / "statistics.html"
        assert path.exists(), "statistics.html was not generated"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, "statistics.html is suspiciously small"

    def test_statistics_has_chart_data(self):
        html = (TABLES_DIR / "statistics.html").read_text(encoding="utf-8")
        assert "Chart" in html or "chart" in html, \
            "statistics.html missing chart references"


# ===================================================================
# 3. CSV Schema Validation
# ===================================================================
class TestAvatarCsvSchema:
    def test_avatar_csv_exists_and_has_rows(self):
        csv_path = SRC / "STAR - Digital Humans Taxonomy - Avatar.csv"
        assert csv_path.exists(), f"Avatar CSV not found: {csv_path}"
        df = pd.read_csv(csv_path)
        assert len(df) > 0, "Avatar CSV is empty"

    def test_avatar_csv_expected_columns(self):
        csv_path = SRC / "STAR - Digital Humans Taxonomy - Avatar.csv"
        df = pd.read_csv(csv_path)
        expected = {"Metadata", "Avatar Prior", "Avatar Creation", "Avatar Animation"}
        missing = expected - set(df.columns)
        assert not missing, f"Missing columns in Avatar CSV: {missing}"


class TestDatasetsCsvSchema:
    def test_datasets_csv_exists_and_has_rows(self):
        csv_path = SRC / "STAR - Digital Humans Taxonomy - Datasets.csv"
        assert csv_path.exists(), f"Datasets CSV not found: {csv_path}"
        df = pd.read_csv(csv_path)
        assert len(df) > 0, "Datasets CSV is empty"

    def test_datasets_csv_expected_columns(self):
        csv_path = SRC / "STAR - Digital Humans Taxonomy - Datasets.csv"
        df = pd.read_csv(csv_path)
        expected = {"Metadata", "Dataset"}
        missing = expected - set(df.columns)
        assert not missing, f"Missing columns in Datasets CSV: {missing}"


# ===================================================================
# 4. Vocabulary Consistency — check GENERATED output, not source data
# ===================================================================
_SPLIT_RE = re.compile(r"\s*,\s*")


def _split_field(val: str) -> list[str]:
    """Split a comma-separated field value."""
    if not val or not isinstance(val, str):
        return []
    return [v.strip() for v in _SPLIT_RE.split(val) if v.strip()]


class TestVocabularyConsistency:
    """Ensure the generated publications.json uses canonical values
    after normalization. Alias values should not appear in the output."""

    @pytest.fixture(scope="class")
    def pub_data(self):
        from build_publications import build_publications_page
        build_publications_page()
        json_path = ROOT / "assets" / "data" / "publications.json"
        assert json_path.exists()
        return json.loads(json_path.read_text(encoding="utf-8"))

    # Alias values that should NOT appear in generated output
    # (they should have been mapped to canonical forms)
    DATA_MODALITY_ALIASES = {
        "Video", "Monocular video", "Monocular RGB video",
        "Monocular RGB Video", "Image", "Multi-view images",
        "3D scans", "3D Scans", "3D meshes",
        "RGB-D video", "Dense multi-view video",
        "Sparse multi-view video",
    }

    CONTENTS_ALIASES = {
        "Head", "Head only", "Portrait", "Full Body",
        "Body", "Upper Body", "Hand", "Clothing", "Garments",
    }

    def test_no_data_modality_aliases_in_output(self, pub_data):
        violations = []
        for entry in pub_data:
            cls = entry.get("classification")
            if not cls:
                continue
            dm = cls.get("fields", {}).get("Data Modality", "")
            for val in _split_field(dm):
                if val in self.DATA_MODALITY_ALIASES:
                    violations.append(f"{entry['key']}: '{val}'")
        assert not violations, (
            "publications.json has un-normalized Data Modality values:\n"
            + "\n".join(violations[:20])
        )

    def test_no_contents_aliases_in_output(self, pub_data):
        violations = []
        for entry in pub_data:
            cls = entry.get("classification")
            if not cls:
                continue
            contents = cls.get("fields", {}).get("Contents", "")
            for val in _split_field(contents):
                if val in self.CONTENTS_ALIASES:
                    violations.append(f"{entry['key']}: '{val}'")
        assert not violations, (
            "publications.json has un-normalized Contents values:\n"
            + "\n".join(violations[:20])
        )


class TestLegendNoDuplicates:
    """Ensure the generated legend.html has no duplicate filter items
    within the same category. This catches the 'Multi-view images' vs
    'Multi-view image' bug."""

    def test_no_duplicate_legend_labels(self):
        path = TABLES_DIR / "legend.html"
        if not path.exists():
            pytest.skip("legend.html not generated yet")
        html = path.read_text(encoding="utf-8")
        # Extract all legend item labels from the HTML
        # Legend items use data-value attributes or visible text in spans
        labels_by_section = {}
        current_section = None
        for line in html.split("\n"):
            # Section headers
            section_match = re.search(r'<(?:th|td)[^>]*>.*?<strong>([^<]+)</strong>', line)
            if section_match:
                current_section = section_match.group(1).strip()
                labels_by_section[current_section] = []
            # Legend item labels (within val spans or similar)
            label_matches = re.findall(r'class="val-label[^"]*"[^>]*>([^<]+)<', line)
            if label_matches and current_section:
                labels_by_section[current_section].extend(label_matches)

        for section, labels in labels_by_section.items():
            counts = Counter(labels)
            dupes = {l: c for l, c in counts.items() if c > 1}
            assert not dupes, (
                f"Legend section '{section}' has duplicate labels: {dupes}"
            )


class TestDatasetsCSVVocabulary:
    """The Datasets CSV feeds directly into legend auto-collection
    (via table.py) WITHOUT normalization. Alias values here create
    duplicate legend entries."""

    DATA_MODALITY_ALIASES = {
        "Video", "Monocular video", "Monocular RGB video",
        "Monocular RGB Video", "Image", "Multi-view images",
        "3D scans", "3D Scans", "3D meshes",
        "RGB-D video", "Dense multi-view video",
        "Sparse multi-view video",
    }

    def test_datasets_csv_data_modality_uses_canonical_values(self):
        """Values in the Datasets CSV Data Modality column must use
        canonical forms, since they are auto-collected for the legend."""
        csv_path = SRC / "STAR - Digital Humans Taxonomy - Datasets.csv"
        if not csv_path.exists():
            pytest.skip("Datasets CSV not found")
        df = pd.read_csv(csv_path)
        violations = []
        if "Data Modality" in df.columns:
            for idx, cell in df["Data Modality"].items():
                if not isinstance(cell, str):
                    continue
                for val in _split_field(cell):
                    if val in self.DATA_MODALITY_ALIASES:
                        violations.append(
                            f"Row {idx}: '{val}' should use canonical form"
                        )
        assert not violations, (
            "Datasets CSV 'Data Modality' has alias values that will create "
            "duplicate legend entries:\n" + "\n".join(violations)
        )


# ===================================================================
# 5. All expected deploy artifacts exist
# ===================================================================
class TestDeployArtifacts:
    """Verify that after a full build, all files served by
    the website are present."""

    EXPECTED_ARTIFACTS = [
        "tables/taxonomy.html",
        "tables/assets.html",
        "tables/datasets.html",
        "tables/legend.html",
        "tables/publications.html",
        "tables/statistics.html",
        "assets/data/publications.json",
    ]

    @pytest.fixture(scope="class", autouse=True)
    def run_full_build(self):
        """Run the complete build pipeline (minus fetch steps that need network)."""
        from build_publications import build_publications_page
        from build_statistics import main as build_statistics_main

        build_tables_main()
        build_publications_page()
        build_statistics_main()

    @pytest.mark.parametrize("rel_path", EXPECTED_ARTIFACTS)
    def test_artifact_exists(self, rel_path):
        full = ROOT / rel_path
        assert full.exists(), f"Missing deploy artifact: {rel_path}"
        assert full.stat().st_size > 0, f"Deploy artifact is empty: {rel_path}"
