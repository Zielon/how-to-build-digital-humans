#!/usr/bin/env python3
"""Normalize classifications in final_results.json to use standard taxonomy values.

Run: python3 classify/normalize_classifications.py
Creates a backup at classify/final_results.backup.json before modifying.
"""

import json
import re
import shutil
from pathlib import Path

JSON_FILE = Path(__file__).resolve().parent / "final_results.json"
BACKUP_FILE = JSON_FILE.with_suffix(".backup.json")

# --- Image Synthesis normalization map ---
IMAGE_SYNTH_MAP = {
    # Direct mappings
    "3DGS": "3DGS",
    "MVP": "MVP",
    "Mesh": "Mesh",
    "NeRF": "NeRF",
    "Neural Rendering": "Neural Rendering",
    "SDF": "SDF",
    "Strands": "Strands",
}


def normalize_image_synthesis(val: str) -> str:
    """Map verbose Image Synthesis values to canonical taxonomy values."""
    val = val.strip()
    if val in IMAGE_SYNTH_MAP:
        return val

    v = val.lower()

    # Check for compound values with commas (e.g. "3DGS, Neural Rendering")
    if "," in val:
        parts = [normalize_image_synthesis(p.strip()) for p in val.split(",")]
        return ", ".join(parts)

    # Slash-separated: take primary
    if "/" in val:
        parts = val.split("/")
        return normalize_image_synthesis(parts[0].strip())

    # 3DGS variants
    if "3dgs" in v or "gaussian splat" in v or "3d gaussian" in v:
        return "3DGS"
    # MVP
    if "mvp" in v or "mixture of volumetric" in v:
        return "MVP"
    # NeRF variants
    if "nerf" in v or "neural radiance" in v:
        return "NeRF"
    # SDF
    if "sdf" in v or "signed distance" in v:
        return "SDF"
    # Strands
    if "strand" in v:
        return "Strands"
    # Mesh variants
    if "mesh" in v and ("marching" in v or "occupancy" in v or "implicit" in v):
        return "Mesh"
    if v.startswith("mesh"):
        return "Mesh"
    # Neural Rendering (GAN, Diffusion, CNN, etc.)
    if any(kw in v for kw in ["gan", "diffusion", "cnn", "neural rendering",
                               "video diffusion", "point-based", "deferred",
                               "volumetric primitive"]):
        return "Neural Rendering"
    # Points
    if "point" in v and "cloud" in v:
        return "Mesh"  # closest valid value

    # If starts with a valid prefix followed by parenthetical, strip it
    for canonical in IMAGE_SYNTH_MAP:
        if v.startswith(canonical.lower()):
            return canonical

    return val  # leave unchanged if no match


def normalize_representation(val: str) -> str:
    """Normalize Representation field for assets table."""
    val = val.strip()
    v = val.lower()

    if "strand" in v:
        return "Strands"
    if "3dgs" in v or "gaussian splat" in v or "3d gaussian" in v:
        return "3DGS"
    if "nerf" in v or "neural radiance" in v:
        return "NeRF"
    if "sdf" in v or "signed distance" in v:
        return "SDF"
    if "neural" in v and "rendering" in v:
        return "Neural Rendering"
    if "mesh" in v:
        return "Mesh"
    if "mvp" in v:
        return "MVP"

    # Strip parenthetical descriptions
    match = re.match(r"^(3DGS|MVP|Mesh|NeRF|Neural Rendering|SDF|Strands)", val)
    if match:
        return match.group(1)

    return val


def normalize_contents(val: str) -> str:
    """Normalize Contents field values."""
    # Replace slashes with commas
    val = val.replace("/", ", ")
    # Normalize individual parts
    parts = [p.strip() for p in val.split(",")]
    normalized = []
    for p in parts:
        if not p:
            continue
        pl = p.lower().strip()
        if pl in ("full-body", "full body", "body"):
            normalized.append("Body")
        elif pl in ("face", "head", "head (portrait)"):
            normalized.append("Face")
        elif pl in ("hand", "hands"):
            normalized.append("Hand")
        elif pl in ("hair", "hair (dynamic)"):
            normalized.append("Hair")
        elif pl in ("garment", "garment (multi-layer clothing simulation with intersection resolution)"):
            normalized.append("Garment")
        elif pl in ("teeth",):
            normalized.append("Teeth")
        elif pl in ("tongue", "tounge"):
            normalized.append("Tongue")
        elif "cloth" in pl:
            normalized.append("Garment")
        else:
            # Remove parenthetical qualifiers
            clean = re.sub(r'\s*\(.*?\)', '', p).strip()
            normalized.append(clean)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for n in normalized:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return ", ".join(result)


def normalize_speed(val: str, field_name: str) -> str:
    """Normalize speed values to include parenthetical time range."""
    val = val.strip()
    if not val:
        return val

    v = val.lower()

    # Already correct format
    if "(" in val and ")" in val:
        return val

    # Map common variants
    if v.startswith("slow"):
        return "Slow (>6h)"
    if v.startswith("medium"):
        return "Medium (<6h)"
    if v.startswith("fast"):
        return "Fast (<30min)"
    if v.startswith("instant"):
        return "Instant (<1min)"
    if v.startswith("offline"):
        return "Offline (<1 FPS)"
    if v.startswith("interactive"):
        return "Interactive (>5 FPS)"
    if v.startswith("real-time") or v.startswith("realtime"):
        return "Real-time (>30 FPS)"

    # Handle "Slow >6h" -> "Slow (>6h)" pattern
    match = re.match(r"(Slow|Medium|Fast|Instant|Offline|Interactive|Real-time)\s+(.+)", val, re.IGNORECASE)
    if match:
        label = match.group(1)
        rest = match.group(2).strip()
        if not rest.startswith("("):
            rest = f"({rest})"
        return f"{label} {rest}"

    return val


def normalize_data_modality(val: str) -> str:
    """Normalize Data Modality values."""
    val = val.strip()
    if not val:
        return val

    parts = [p.strip() for p in val.split(",")]
    normalized = []
    for p in parts:
        pl = p.lower().strip()
        if "3d scan" in pl or pl == "3d scans" or "registered mesh" in pl or "4d scan" in pl:
            normalized.append("Meshes")
        elif pl == "multi-view image":
            normalized.append("Multi-view images")
        elif "monocular video" in pl:
            normalized.append("Mono video")
        elif pl == "video" or pl == "rgb-d video":
            normalized.append("Mono video")
        elif "3d motion" in pl:
            normalized.append("Meshes")
        else:
            # Remove parenthetical qualifiers
            clean = re.sub(r'\s*\(.*?\)', '', p).strip()
            normalized.append(clean)

    # Deduplicate
    seen = set()
    result = []
    for n in normalized:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return ", ".join(result)


def normalize_input(val: str) -> str:
    """Normalize Input field values."""
    val = val.strip()
    if not val:
        return val

    v = val.lower()
    if "single image" in v and "," not in val:
        return "One"
    if v == "single image":
        return "One"
    if "collection" in v and "image" in v:
        return "Few"
    if v == "rgb-d video":
        return "Mono video"
    if v.startswith("monocular video"):
        return "Mono video"

    # Remove parenthetical qualifiers
    val = re.sub(r'\s*\(.*?\)', '', val).strip()
    return val


def normalize_animation_signal(val: str) -> str:
    """Normalize Animation Signal values."""
    val = val.strip()
    if not val:
        return val

    # Replace slashes with commas
    val = val.replace("/", ", ")
    parts = [p.strip() for p in val.split(",")]
    normalized = []
    for p in parts:
        pl = p.lower().strip()
        if not pl:
            continue
        # Remove parenthetical
        clean = re.sub(r'\s*\(.*?\)', '', p).strip()
        cl = clean.lower()

        if "3dmm" in cl or cl == "3dmm expr":
            normalized.append("3DMM expr")
        elif cl == "audio":
            normalized.append("Audio")
        elif cl in ("general expr", "general expression"):
            normalized.append("General expr")
        elif cl in ("multi-view image", "multi-view images"):
            normalized.append("Multi-view image")
        elif cl == "pose" or "body pose" in cl or "hand pose" in cl or "skeletal" in cl or "smpl" in cl or "mano" in cl:
            normalized.append("Pose")
        elif cl == "video" or "driving video" in cl:
            normalized.append("Video")
        elif cl in ("text", "camera", "simulation", "latent code", "landmarks"):
            # Skip invalid animation signals
            continue
        else:
            normalized.append(clean)

    # Deduplicate
    seen = set()
    result = []
    for n in normalized:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return ", ".join(result)


def normalize_additional_priors(val: str) -> str:
    """Clean up Additional Priors - remove parenthetical details."""
    if not val:
        return val
    # Remove verbose parenthetical descriptions
    val = re.sub(r'\s*\([^)]*\)', '', val)
    return val.strip()


def normalize_fields(fields: dict, table_type: str) -> dict:
    """Normalize all fields in a classification entry."""
    result = dict(fields)

    # Normalize Contents
    for key in ("Contents", "contents"):
        if key in result and result[key]:
            result[key] = normalize_contents(result[key])

    # Normalize Image Synthesis
    for key in ("Image Synthesis", "image_synthesis"):
        if key in result and result[key]:
            result[key] = normalize_image_synthesis(result[key])

    # Normalize Representation (assets)
    if "Representation" in result and result["Representation"]:
        result["Representation"] = normalize_representation(result["Representation"])

    # Normalize speeds
    for key in ("Creation Speed", "creation_speed"):
        if key in result and result[key]:
            result[key] = normalize_speed(result[key], "creation")
    for key in ("Animation Speed", "animation_speed"):
        if key in result and result[key]:
            result[key] = normalize_speed(result[key], "animation")

    # Normalize Data Modality
    for key in ("Data Modality", "data_modality"):
        if key in result and result[key]:
            result[key] = normalize_data_modality(result[key])

    # Normalize Input
    for key in ("Input", "input"):
        if key in result and result[key]:
            result[key] = normalize_input(result[key])

    # Normalize Animation Signal
    for key in ("Animation Signal", "animation_signal"):
        if key in result and result[key]:
            result[key] = normalize_animation_signal(result[key])

    # Normalize Additional Priors (strip parenthetical details)
    for key in ("Additional Priors", "additional_priors"):
        if key in result and result[key]:
            result[key] = normalize_additional_priors(result[key])

    return result


def main():
    # Backup
    shutil.copy2(JSON_FILE, BACKUP_FILE)
    print(f"Backup created: {BACKUP_FILE}")

    with JSON_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    changes = 0
    for section in ["avatar_classifications", "assets_classifications"]:
        table_type = "avatar" if "avatar" in section else "assets"
        for item in data[section]:
            old_fields = dict(item.get("fields", {}))
            new_fields = normalize_fields(old_fields, table_type)
            if new_fields != old_fields:
                item["fields"] = new_fields
                changes += 1

    with JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Normalized {changes} entries")
    print(f"Updated {JSON_FILE}")


if __name__ == "__main__":
    main()
