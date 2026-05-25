"""Tests for the publications build pipeline.

Covers BibTeX parsing, venue normalization, field normalization,
classification loading, and the full HTML generation pipeline.
"""

from __future__ import annotations

import re
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tables_src"

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_publications import (
    _load_bibtex_strings,
    _normalize_venue,
    _primary_category,
    build_publications_page,
    load_classifications,
    parse_bibliography_with_metadata,
)
from normalize_fields import normalize_fields

BIB_FILE = SRC / "bibliography.bib"
ABBR_FILE = ROOT / "abbr.bib"


# ===================================================================
# 1. BibTeX String Macro Loading
# ===================================================================
class TestLoadBibtexStrings:
    def test_loads_all_entries(self):
        macros = _load_bibtex_strings(ABBR_FILE)
        assert len(macros) > 0, "No macros loaded from abbr.bib"

    def test_returns_empty_for_missing_file(self):
        macros = _load_bibtex_strings(Path("/nonexistent/abbr.bib"))
        assert macros == {}

    def test_keys_are_lowercase(self):
        macros = _load_bibtex_strings(ABBR_FILE)
        for key in macros:
            assert key == key.lower(), f"Key {key!r} is not lowercase"

    @pytest.mark.parametrize(
        "macro,expected_substr",
        [
            ("cvpr", "CVPR"),
            ("eccv", "ECCV"),
            ("siggraph_tog", "SIGGRAPH"),
            ("neurips", "NeurIPS"),
            ("pami", "TPAMI"),
        ],
    )
    def test_spot_check_macros(self, macro, expected_substr):
        macros = _load_bibtex_strings(ABBR_FILE)
        assert macro in macros
        assert expected_substr in macros[macro]


# ===================================================================
# 2. Venue Normalization
# ===================================================================
class TestNormalizeVenue:
    def test_empty_string(self):
        assert _normalize_venue("") == ""

    def test_url_string_stripped(self):
        assert _normalize_venue("URL: https://example.com") == ""

    def test_http_string_stripped(self):
        assert _normalize_venue("https://arxiv.org/abs/1234") == ""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CVPR", "CVPR"),
            ("ECCV", "ECCV"),
            ("ICCV", "ICCV"),
            ("SIGGRAPH_TOG", "TOG (SIGGRAPH)"),
            ("NEURIPS", "NeurIPS"),
            ("PAMI", "TPAMI"),
            ("ICLR", "ICLR"),
            ("ICML", "ICML"),
        ],
    )
    def test_bare_macro_resolution(self, raw, expected):
        assert _normalize_venue(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("arXiv", "arXiv"),
            ("corr", "arXiv"),
            ("3dv", "3DV"),
        ],
    )
    def test_manual_overrides(self, raw, expected):
        assert _normalize_venue(raw) == expected

    def test_braced_value(self):
        assert _normalize_venue("{arXiv}") == "arXiv"

    def test_verbose_proceedings_shortened(self):
        venue = "Advances in Neural Information Processing Systems (NeurIPS)"
        assert _normalize_venue(venue) == "NeurIPS"

    def test_already_clean_passes_through(self):
        assert _normalize_venue("WACV") == "WACV"


# ===================================================================
# 3. BibTeX Parsing
# ===================================================================
class TestParseBibliography:
    @pytest.fixture(scope="class")
    def entries(self):
        return parse_bibliography_with_metadata(BIB_FILE)

    def test_nonexistent_file_returns_empty(self):
        result = parse_bibliography_with_metadata(Path("/nonexistent.bib"))
        assert result == []

    def test_parses_sufficient_entries(self, entries):
        assert len(entries) >= 500

    @pytest.mark.parametrize("field", ["key", "title", "authors", "year", "venue", "bibtex"])
    def test_entries_have_required_keys(self, entries, field):
        for e in entries:
            assert field in e, f"Entry {e.get('key', '?')} missing field {field!r}"

    def test_bare_macro_venues_captured(self, entries):
        """Bare macros like CVPR, ECCV should appear as raw strings, not empty."""
        cvpr_entries = [e for e in entries if e["venue"] == "CVPR"]
        eccv_entries = [e for e in entries if e["venue"] == "ECCV"]
        assert len(cvpr_entries) > 0
        assert len(eccv_entries) > 0

    def test_brace_delimited_fields_parsed(self, entries):
        """Titles wrapped in braces should be parsed correctly."""
        for e in entries:
            if e["title"]:
                assert not e["title"].startswith("{"), (
                    f"Title for {e['key']} starts with brace: {e['title'][:40]}"
                )

    def test_metadata_attached_to_entries(self, entries):
        """% Webpage:, % Code: etc. comments should be attached."""
        e = next(e for e in entries if e["key"] == "Lombardi21mvp")
        assert "stephenlombardi" in e["webpage"]
        assert "github.com" in e["code"]
        assert "arxiv.org" in e["arxiv"]

    def test_latex_accents_cleaned(self, entries):
        r"""No {\' or {\" or {\v sequences should remain."""
        for e in entries:
            for field in ("title", "authors"):
                val = e.get(field, "")
                assert r"{'" not in val, f"{e['key']}.{field} has raw latex: {val[:60]}"
                assert r'{"' not in val, f"{e['key']}.{field} has raw latex: {val[:60]}"

    def test_specific_paper_fields(self, entries):
        e = next(e for e in entries if e["key"] == "Zielonka2022mica")
        assert "Metrical Reconstruction" in e["title"]
        assert "Zielonka" in e["authors"]
        assert e["year"] == "2022"
        assert e["venue"] == "ECCV"


# ===================================================================
# 4. Classification Loading
# ===================================================================
class TestLoadClassifications:
    @pytest.fixture(scope="class")
    def classifications(self):
        return load_classifications()

    def test_returns_3_tuple(self, classifications):
        assert len(classifications) == 3

    def test_classified_count(self, classifications):
        classified, _, _ = classifications
        assert len(classified) > 0, "No classified entries found"

    def test_classified_entry_structure(self, classifications):
        classified, _, _ = classifications
        for key, info in classified.items():
            assert "table_type" in info, f"{key} missing table_type"
            assert "category" in info, f"{key} missing category"
            assert "fields" in info, f"{key} missing fields"
            assert info["table_type"] in ("avatar", "assets")

    def test_skipped_count(self, classifications):
        _, skipped, _ = classifications
        assert len(skipped) > 0, "No skipped entries found"

    def test_classified_plus_skipped_matches_metadata(self, classifications):
        """Verify counts are consistent with final_results.json metadata."""
        classified, skipped, _ = classifications
        json_path = Path(__file__).resolve().parent.parent / "classify" / "final_results.json"
        with open(json_path) as f:
            meta = json.load(f)["metadata"]
        assert len(classified) == meta["avatar_count"] + meta["assets_count"]
        assert len(skipped) == meta["skipped_count"]

    def test_notes_non_empty(self, classifications):
        _, _, notes = classifications
        assert len(notes) > 0, "No notes found"

    def test_missing_json_returns_empty(self, tmp_path, monkeypatch):
        import build_publications

        monkeypatch.setattr(build_publications, "JSON_FILE", tmp_path / "missing.json")
        c, s, n = load_classifications()
        assert c == {} and s == {} and n == {}


# ===================================================================
# 5. Field Normalization
# ===================================================================
class TestNormalizeFields:
    def test_snake_case_keys_to_title_case(self):
        result = normalize_fields({"prior_dataset_size": "100"})
        assert "Prior Dataset Size" in result

    def test_contents_normalization(self):
        result = normalize_fields({"contents": "Full-body"})
        assert result["Contents"] == "Full-body"

    def test_body_to_full_body(self):
        result = normalize_fields({"contents": "Body"})
        assert result["Contents"] == "Full-body"

    def test_head_to_face(self):
        result = normalize_fields({"contents": "Head"})
        assert result["Contents"] == "Face"

    def test_boolean_yes_with_detail(self):
        result = normalize_fields({"req_optimization": "Yes (per-subject training)"})
        assert result["Req. Optimization"] == "Yes"

    def test_boolean_none_to_no(self):
        result = normalize_fields({"req_optimization": "None"})
        assert result["Req. Optimization"] == "No"

    def test_speed_feed_forward(self):
        result = normalize_fields({"creation_speed": "Feed-forward"})
        assert result["Creation Speed"] == "Instant"

    def test_speed_slow_with_qualifier(self):
        result = normalize_fields({"creation_speed": "Slow >6h"})
        assert result["Creation Speed"] == "Slow (>6h)"

    def test_gan_to_neural_rendering(self):
        result = normalize_fields({"image_synthesis": "GAN"})
        assert result["Image Synthesis"] == "Neural Rendering"

    def test_3dgs_alias(self):
        result = normalize_fields({"image_synthesis": "3D Gaussian Splatting"})
        assert result["Image Synthesis"] == "3DGS"


# ===================================================================
# 6. Primary Category Extraction
# ===================================================================
class TestPrimaryCategory:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Face, Hair", "Face"),
            ("Full-body (clothed)", "Full-body"),
            ("", ""),
            ("Hair", "Hair"),
            ("Hands", "Hands"),
            ("Garment", "Garment"),
        ],
    )
    def test_primary_category(self, raw, expected):
        assert _primary_category(raw) == expected


# ===================================================================
# 7. Full Pipeline Integration Test
# ===================================================================
class TestBuildPublicationsPage:
    @pytest.fixture(scope="class")
    def html_output(self):
        build_publications_page()
        path = ROOT / "tables" / "publications.html"
        assert path.exists(), "publications.html was not generated"
        return path.read_text(encoding="utf-8")

    def test_file_generated(self, html_output):
        assert len(html_output) > 0

    def test_venue_dropdown_contains_expected(self, html_output):
        for venue in ("CVPR", "ECCV", "ICCV"):
            assert f'value="{venue}"' in html_output, f"Venue dropdown missing {venue}"

    def test_siggraph_in_venue_dropdown(self, html_output):
        assert "TOG (SIGGRAPH)" in html_output

    def test_every_card_has_table_type(self, html_output):
        cards = re.findall(r'<article class="pub-card"[^>]*>', html_output)
        assert len(cards) > 0
        for card in cards:
            assert 'data-table-type="' in card

    def test_notes_cards_have_data_attribute(self, html_output):
        assert 'data-has-notes="1"' in html_output

    def test_no_url_in_venues(self, html_output):
        venue_values = re.findall(r'data-venue="([^"]*)"', html_output)
        for v in venue_values:
            assert "URL:" not in v, f"Venue contains URL: {v}"
            assert "http" not in v.lower(), f"Venue contains http: {v}"

    def test_type_filter_options(self, html_output):
        for val in ("avatar", "assets", "skipped", "has_notes"):
            assert f'value="{val}"' in html_output

    def test_notes_render_pub_note_div(self, html_output):
        assert '<div class="pub-note">' in html_output


# ===================================================================
# 8. Venue Coverage Validation
# ===================================================================
class TestVenueCoverage:
    @pytest.fixture(scope="class")
    def entries_with_venues(self):
        entries = parse_bibliography_with_metadata(BIB_FILE)
        return entries

    def test_journal_booktitle_produces_non_empty_venue(self, entries_with_venues):
        """Every paper with a non-URL journal/booktitle should get a non-empty venue."""
        for e in entries_with_venues:
            raw = e["venue"]
            if not raw:
                continue
            # URLs as venues are intentionally stripped to empty
            if raw.strip().startswith("URL:") or raw.strip().startswith("http"):
                assert _normalize_venue(raw) == ""
                continue
            normalized = _normalize_venue(raw)
            assert normalized, (
                f"Paper {e['key']} has venue {raw!r} but normalizes to empty"
            )

    def test_no_venue_too_long(self, entries_with_venues):
        """Venues should be short abbreviations, not verbose proceedings names."""
        MAX_LEN = 45  # allow some flexibility for edge cases
        for e in entries_with_venues:
            v = _normalize_venue(e["venue"])
            if v:
                assert len(v) <= MAX_LEN, (
                    f"Paper {e['key']}: venue {v!r} is {len(v)} chars (max {MAX_LEN})"
                )

    @pytest.mark.parametrize(
        "key,expected_venue",
        [
            ("Lombardi21mvp", "TOG (SIGGRAPH)"),
            ("Zielonka2022mica", "ECCV"),
            ("Ma2021pica", "CVPR"),
            ("Wuu2022multiface", "arXiv"),
            ("Kirschstein2023nersemble", "TOG (SIGGRAPH)"),
        ],
    )
    def test_specific_paper_venue(self, entries_with_venues, key, expected_venue):
        e = next((e for e in entries_with_venues if e["key"] == key), None)
        assert e is not None, f"Paper {key} not found"
        assert _normalize_venue(e["venue"]) == expected_venue


# ===================================================================
# 9. JSON Export
# ===================================================================
class TestJsonExport:
    JSON_PATH = ROOT / "assets" / "data" / "publications.json"

    @pytest.fixture(scope="class")
    def json_data(self):
        build_publications_page()
        assert self.JSON_PATH.exists(), "publications.json was not generated"
        with self.JSON_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    def test_file_generated(self, json_data):
        assert isinstance(json_data, list)

    def test_entry_count(self, json_data):
        assert len(json_data) > 0, "No entries in publications.json"

    @pytest.mark.parametrize("field", [
        "key", "title", "authors", "year", "venue",
        "entry_type", "links", "classification", "note", "skip_reason",
    ])
    def test_entries_have_required_fields(self, json_data, field):
        for entry in json_data:
            assert field in entry, f"Entry {entry.get('key', '?')} missing {field!r}"

    def test_links_structure(self, json_data):
        for entry in json_data:
            links = entry["links"]
            for lk in ("webpage", "code", "video", "arxiv"):
                assert lk in links, f"Entry {entry['key']} missing link {lk!r}"

    def test_no_none_strings_in_links(self, json_data):
        for entry in json_data:
            for lk, lv in entry["links"].items():
                assert lv != "None", (
                    f"Entry {entry['key']} link {lk} is string 'None', should be null"
                )

    def test_sorted_by_year_desc(self, json_data):
        for i in range(len(json_data) - 1):
            y1 = int(json_data[i]["year"]) if json_data[i]["year"] else 0
            y2 = int(json_data[i + 1]["year"]) if json_data[i + 1]["year"] else 0
            if y1 != y2:
                assert y1 >= y2, (
                    f"Not sorted: {json_data[i]['key']} ({y1}) before {json_data[i+1]['key']} ({y2})"
                )

    def test_classification_structure(self, json_data):
        classified = [e for e in json_data if e["classification"] is not None]
        assert len(classified) > 0
        for entry in classified:
            cls = entry["classification"]
            assert "table_type" in cls
            assert cls["table_type"] in ("avatar", "assets")
            assert "fields" in cls
            assert isinstance(cls["fields"], dict)

    def test_specific_entry(self, json_data):
        entry = next((e for e in json_data if e["key"] == "Zielonka2022mica"), None)
        assert entry is not None
        assert "Metrical Reconstruction" in entry["title"]
        assert entry["year"] == "2022"
        assert entry["venue"] == "ECCV"
        assert entry["links"]["arxiv"] is not None
        assert entry["classification"] is not None
        assert entry["classification"]["table_type"] == "avatar"
