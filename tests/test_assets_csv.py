from pathlib import Path

import pandas as pd


def test_assets_csv_schema_is_valid():
    """
    Basic sanity check that the Assets taxonomy CSV is present
    and has the expected high-level columns.
    """
    # repo_root = .../how-to-build-digital-humans
    repo_root = Path(__file__).resolve().parents[1]

    csv_path = repo_root / "tables_src" / "STAR - Digital Humans Taxonomy - Assets.csv"
    assert csv_path.exists(), f"CSV file not found: {csv_path}"

    df = pd.read_csv(csv_path)

    # These are the top-level header columns actually used in the file
    expected_columns = {
        "Metadata",
        "Assets Prior",
        "Assets Creation",
        "Double Checked",
        "Reviewer",
    }

    missing = expected_columns - set(df.columns)
    assert not missing, f"Missing expected columns in Assets CSV: {missing}"

    # Ensure we have at least one data row
    assert len(df) > 0, "Assets CSV appears to be empty"
