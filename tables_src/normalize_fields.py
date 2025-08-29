"""Normalize free-form classifier field values to the controlled vocabulary.

This module is shared by build_tables.py and build_publications.py so that
auto-classified entries from classify/final_results.json use the same
canonical labels (and therefore the same icons) as the curated CSV data.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. Field key normalisation  (snake_case → Title Case)
# ---------------------------------------------------------------------------
_KEY_ALIASES: dict[str, str] = {
    "prior_dataset_size": "Prior Dataset Size",
    "datasets": "Datasets",
    "data_type": "Data Type",
    "data_modality": "Data Modality",
    "needed_assets": "Needed Assets",
    "input": "Input",
    "additional_priors": "Additional Priors",
    "req_optimization": "Req. Optimization",
    "creation_speed": "Creation Speed",
    "animation_signal": "Animation Signal",
    "lighting_control": "Lighting Control",
    "animation_speed": "Animation Speed",
    "image_synthesis": "Image Synthesis",
    "image_refinement": "Image Refinement",
    "contents": "Contents",
    "representation": "Representation",
    "simulation_ready": "Simulation Ready",
}

# ---------------------------------------------------------------------------
# 2. Per-field value alias maps
# ---------------------------------------------------------------------------

_CONTENTS_ALIASES: dict[str, str] = {
    "Head": "Face",
    "Head only": "Face",
    "Portrait": "Face",
    "Full Body": "Full-body",
    "Body": "Full-body",
    "Upper Body": "Full-body",
    "Hand": "Hands",
    "Clothing": "Garment",
    "Garments": "Garment",
}

_DATA_TYPE_ALIASES: dict[str, str] = {
    "Both": "Real, Synthetic",
}

_DATA_MODALITY_ALIASES: dict[str, str] = {
    "Video": "Mono video",
    "Monocular video": "Mono video",
    "Monocular RGB video": "Mono video",
    "Monocular RGB Video": "Mono video",
    "Image": "Single image",
    "Multi-view images": "Multi-view image",
    "3D scans": "Meshes",
    "3D Scans": "Meshes",
    "3D meshes": "Meshes",
    "RGB-D video": "Mono video",
    "Dense multi-view video": "Multi-view video",
    "Sparse multi-view video": "Multi-view video",
}

_NEEDED_ASSETS_ALIASES: dict[str, str] = {
    "Tracked FLAME": "Tracked 3DMM",
    "Tracked SMPL": "Tracked 3DMM",
    "FLAME mesh": "Tracked 3DMM",
    "FLAME model": "Tracked 3DMM",
    "SMPL body model": "Tracked 3DMM",
    "SMPL-X body mesh": "Tracked 3DMM",
    "SMPL-X model": "Tracked 3DMM",
    "MANO hand model": "Tracked 3DMM",
    "3D Body Model": "Tracked 3DMM",
    "3D Skeleton": "Tracked 3DMM",
    "foreground masks": "segmentation masks",
}

_INPUT_ALIASES: dict[str, str] = {
    "Single image": "One",
    "Single RGB image": "One",
    "Monocular video": "Mono video",
    "Monocular RGB video": "Mono video",
    "Monocular portrait video": "Mono video",
    "Multi-view image": "Multi-view images",
    "Random noise": "Zero",
    "Text prompt": "Text",
}

_CREATION_SPEED_ALIASES: dict[str, str] = {
    "Feed-forward": "Instant",
    "feedforward inference": "Instant",
    "Seconds to minutes": "Fast",
    "Minutes": "Fast",
    "Hours": "Slow",
    "Per-subject training": "Slow",
    "per-video optimization": "Slow",
    "per-subject optimization required": "Slow",
}

_ANIMATION_SIGNAL_ALIASES: dict[str, str] = {
    "FLAME expression code": "3DMM expr",
    "FLAME expression and pose parameters": "3DMM expr",
    "FLAME expression": "3DMM expr",
    "Latent expression code": "General expr",
    "3D Skeleton Pose": "Pose",
    "3D Body Pose": "Pose",
    "Body pose": "Pose",
    "Hand pose": "Pose",
    "Head motion": "Pose",
    "Skeleton": "Pose",
    "SMPL body pose": "Pose",
}

_LIGHTING_CONTROL_ALIASES: dict[str, str] = {
    "No": "None",
    "no": "None",
    "Environment Map": "Distant Light",
    "Spherical Harmonics": "Distant Light",
    "HDRI": "Distant Light",
}

_ANIMATION_SPEED_ALIASES: dict[str, str] = {
    "Not real-time": "Offline",
    "Near real-time": "Interactive",
}

_SYNTHESIS_REPR_ALIASES: dict[str, str] = {
    "3D Gaussian Splatting": "3DGS",
    "3D Gaussian splatting": "3DGS",
    "Gaussian Splatting": "3DGS",
    "Diffusion": "Neural Rendering",
    "Video Diffusion": "Neural Rendering",
    "2D Diffusion": "Neural Rendering",
    "GAN": "Neural Rendering",
    "neural radiance field": "NeRF",
    "Mesh-based": "Mesh",
    "Point-based rendering": "Neural Rendering",
    "Ray tracing": "Neural Rendering",
    "Deferred neural rendering": "Neural Rendering",
}

# Map field name → alias dict
_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "Contents": _CONTENTS_ALIASES,
    "Data Type": _DATA_TYPE_ALIASES,
    "Data Modality": _DATA_MODALITY_ALIASES,
    "Needed Assets": _NEEDED_ASSETS_ALIASES,
    "Input": _INPUT_ALIASES,
    "Creation Speed": _CREATION_SPEED_ALIASES,
    "Animation Signal": _ANIMATION_SIGNAL_ALIASES,
    "Lighting Control": _LIGHTING_CONTROL_ALIASES,
    "Animation Speed": _ANIMATION_SPEED_ALIASES,
    "Image Synthesis": _SYNTHESIS_REPR_ALIASES,
    "Representation": _SYNTHESIS_REPR_ALIASES,
}

# Boolean-like fields: strip parenthetical elaborations, normalize "none"
_BOOLEAN_FIELDS = {"Req. Optimization", "Image Refinement", "Simulation Ready"}

# ---------------------------------------------------------------------------
# Split / join helpers
# ---------------------------------------------------------------------------
_SPLIT_RE = re.compile(r"\s*(?:,\s*|\s/\s|\s\+\s|;\s*)")
_PAREN_RE = re.compile(r"\s*\([^)]*\)")

# Speed fields: ensure parenthetical qualifiers use (…) format
# e.g. "Slow >6h" → "Slow (>6h)",  "Offline <1 FPS" → "Offline (<1 FPS)"
_SPEED_FIX_RE = re.compile(
    r"^(Instant|Fast|Slow|Real-time|Interactive|Offline)\s+"
    r"(?:\()?([<>≈~][\d\w\s]+?)(?:\))?\s*$"
)


def _normalize_speed_value(v: str) -> str:
    """Fix parenthetical qualifiers on speed values."""
    m = _SPEED_FIX_RE.match(v)
    if m:
        return f"{m.group(1)} ({m.group(2).strip()})"
    return v


def _normalize_boolean(v: str) -> str:
    """Normalise boolean-ish values."""
    stripped = _PAREN_RE.sub("", v).strip()
    if stripped.lower() == "none":
        return "No"
    if stripped.lower() in ("yes", "no"):
        return stripped.capitalize()
    return stripped


def _normalize_value_list(raw: str, aliases: dict[str, str] | None) -> str:
    """Core per-field normalisation pipeline.

    1. Strip parenthetical content
    2. Split multi-values
    3. Map each through alias table
    4. Rejoin with ", "
    """
    # Strip parenthetical content
    cleaned = _PAREN_RE.sub("", raw).strip()
    if not cleaned:
        return ""
    # Split
    parts = _SPLIT_RE.split(cleaned)
    result: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if aliases and p in aliases:
            mapped = aliases[p]
            # An alias can itself be multi-valued (e.g. "Both" → "Real, Synthetic")
            result.extend(v.strip() for v in mapped.split(", "))
        else:
            result.append(p)
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for v in result:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return ", ".join(deduped)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_fields(fields: dict[str, str]) -> dict[str, str]:
    """Return a copy of *fields* with keys and values normalised."""
    out: dict[str, str] = {}
    for key, value in fields.items():
        # 1. Fix snake_case keys
        canonical_key = _KEY_ALIASES.get(key, key)
        if not isinstance(value, str):
            value = str(value) if value is not None else ""
        value = value.strip()
        if not value:
            out[canonical_key] = value
            continue

        # 2. Boolean fields — just strip parenthetical elaborations
        if canonical_key in _BOOLEAN_FIELDS:
            out[canonical_key] = _normalize_boolean(value)
            continue

        # 3. Speed fields — fix parenthetical format before alias mapping
        if canonical_key in ("Creation Speed", "Animation Speed"):
            aliases = _FIELD_ALIASES.get(canonical_key)
            normalised = _normalize_value_list(value, aliases)
            out[canonical_key] = _normalize_speed_value(normalised)
            continue

        # 4. Regular fields with alias tables
        aliases = _FIELD_ALIASES.get(canonical_key)
        if aliases is not None:
            out[canonical_key] = _normalize_value_list(value, aliases)
            continue

        # 5. No special handling — pass through
        out[canonical_key] = value

    return out
