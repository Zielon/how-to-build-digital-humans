#!/usr/bin/env python3
"""Heuristic classifier for digital human papers.

Reads unclassified papers from bibliography.bib, classifies them by
analyzing titles and abstracts, and updates classify/final_results.json.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tables_src"))
from build_publications import parse_bibliography_with_metadata, load_abstract_file
from normalize_fields import normalize_fields

JSON_FILE = ROOT / "classify" / "final_results.json"
BIB_FILE = ROOT / "tables_src" / "bibliography.bib"

# ---------------------------------------------------------------------------
# Category detection keywords (checked against title + abstract, case-insensitive)
# ---------------------------------------------------------------------------
# Order matters: more specific categories checked first

_CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("Teeth", [r"\bteeth\b", r"\bdental\b", r"\btooth\b"]),
    ("Tongue", [r"\btongue\b"]),
    ("Hair", [
        r"\bhair\b", r"\bhairstyle\b", r"\bstrand[s]?\b", r"\bgroom\b",
        r"\bhaircut\b", r"\bhairnet\b", r"\bhair[\s-]?cap",
    ]),
    ("Hands", [
        r"\bhand[s]?\b(?!.{0,5}(craft|le|some|pick|book))", r"\bfinger[s]?\b",
        r"\bgrasp\b", r"\bdexterous\b", r"\bmano\b",
    ]),
    ("Garment", [
        r"\bgarment[s]?\b", r"\bcloth(ing|ed|3d)?\b", r"\bdress\b",
        r"\bapparel\b", r"\bfashion\b", r"\bsewing\b", r"\bdrape\b",
        r"\btextile\b", r"\bfabric\b", r"\bwear\b",
    ]),
    ("Face", [
        r"\bface\b", r"\bfacial\b", r"\bhead\b(?!.*phone)", r"\bportrait\b",
        r"\bexpression[s]?\b", r"\btalking\b", r"\bflame\b",
        r"\b3dmm\b", r"\bmorphable\b", r"\breenact\b", r"\blip[\s-]?sync\b",
        r"\bface[\s-]?swap\b", r"\bdeepfake\b", r"\bblendshape\b",
        r"\bcodec[\s-]?avatar\b",
    ]),
    ("Full-body", [
        r"\bbody\b", r"\bhuman\b", r"\bavatar[s]?\b", r"\bmotion\b",
        r"\bpose\b", r"\bfull[\s-]?body\b", r"\bcharacter\b",
        r"\bperson\b", r"\bpeople\b", r"\bsmpl\b", r"\bskeleton\b",
        r"\bdance\b", r"\bperform\b",
    ]),
]

# ---------------------------------------------------------------------------
# Skip detection — papers that are not about digital human creation
# ---------------------------------------------------------------------------
_SKIP_PATTERNS: list[str] = [
    r"\bsurvey\b", r"\breview\b", r"\bstate[\s-]of[\s-]the[\s-]art\b",
    r"\bbenchmark\b(?!.*avatar)", r"\bdataset\b(?!.*(avatar|human|face|body|garment|hair))",
]

# ---------------------------------------------------------------------------
# Assets vs Avatar detection
# Assets papers create reusable geometry/appearance assets (meshes, strands, patterns)
# Avatar papers create animatable digital humans
# ---------------------------------------------------------------------------
_ASSETS_PATTERNS: list[str] = [
    r"\b(hair|strand)\s*(reconstruction|modeling|capture|generation)\b",
    r"\bgarment\s*(reconstruction|generation|modeling|draping|simulation)\b",
    r"\bcloth\s*(reconstruction|simulation|generation)\b",
    r"\bsewing\s*pattern\b",
    r"\b3d\s*(hair|garment|cloth)\b",
    r"\b(reconstruct|generat)\w*\s+(hair|garment|cloth|strand)",
    r"\bhair\s*from\b",
]

# ---------------------------------------------------------------------------
# Field inference helpers
# ---------------------------------------------------------------------------

def _detect_category(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for cat, patterns in _CATEGORY_PATTERNS:
        count = 0
        for p in patterns:
            count += len(re.findall(p, text_lower))
        if count > 0:
            scores[cat] = count
    if not scores:
        return "Face"  # default
    # Return category with highest score
    return max(scores, key=scores.get)


def _should_skip(title: str, abstract: str) -> tuple[bool, str]:
    text = (title + " " + abstract).lower()
    for p in _SKIP_PATTERNS:
        if re.search(p, text):
            return True, f"Matched skip pattern: {p}"
    return False, ""


def _is_assets(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    for p in _ASSETS_PATTERNS:
        if re.search(p, text):
            return True
    return False


def _detect_input(text: str) -> str:
    t = text.lower()
    inputs = []
    if re.search(r"\btext[\s-]?(prompt|driven|guided|to[\s-])", t):
        inputs.append("Text")
    if re.search(r"\baudio[\s-]?(driven|guided|input|signal)|speech[\s-]driven", t):
        inputs.append("Audio")
    if re.search(r"\bmulti[\s-]?view\s*(video|capture)", t):
        inputs.append("Multi-view video")
    elif re.search(r"\bmulti[\s-]?view\s*(image|photo)", t):
        inputs.append("Multi-view images")
    elif re.search(r"\bmonocular\s*video|\bvideo[\s-]?(input|driven|based)", t):
        inputs.append("Mono video")
    elif re.search(r"\bsingle[\s-]?(image|photo|view)|from\s*(a\s+)?single", t):
        inputs.append("One")
    elif re.search(r"\bfew[\s-]?(shot|image|view)", t):
        inputs.append("Few")
    elif re.search(r"\b(unconditional|from\s+noise|random\s+sampl)", t):
        inputs.append("Zero")
    if not inputs:
        inputs.append("One")  # default
    return ", ".join(inputs)


def _detect_representation(text: str) -> str:
    t = text.lower()
    reps = []
    if re.search(r"\bgaussian\s*splat|3d\s*gaussian|3dgs\b", t):
        reps.append("3DGS")
    if re.search(r"\bnerf\b|neural\s*radiance", t):
        reps.append("NeRF")
    if re.search(r"\bmesh\b(?!.*network)", t) and not reps:
        reps.append("Mesh")
    if re.search(r"\bdiffusion\b", t) and not reps:
        reps.append("Neural Rendering")
    if re.search(r"\bgan\b|generative\s*adversarial", t) and not reps:
        reps.append("Neural Rendering")
    if re.search(r"\bsdf\b|signed\s*distance", t):
        reps.append("SDF")
    if re.search(r"\bstrand[s]?\b", t) and not reps:
        reps.append("Strands")
    if not reps:
        reps.append("Mesh")
    return ", ".join(reps)


def _detect_data_type(text: str) -> str:
    t = text.lower()
    if re.search(r"\bsynthetic\b|\brendered\b|\bsimulated\b", t):
        if re.search(r"\breal\b|\bcaptured\b|\brecorded\b", t):
            return "Real, Synthetic"
        return "Synthetic"
    return "Real"


def _detect_animation_signal(text: str, category: str) -> str:
    t = text.lower()
    signals = []
    if re.search(r"\baudio[\s-]?driven|speech[\s-]?driven|audio\s*signal", t):
        signals.append("Audio")
    if re.search(r"\btext[\s-]?(driven|guided|prompt)", t):
        pass  # text is input, not animation signal
    if re.search(r"\bvideo[\s-]?driven|video\s*reenact", t):
        signals.append("Video")
    if re.search(r"\bpose[\s-]?(driven|guided|control)|body\s*pose|skeleton", t):
        signals.append("Pose")
    if re.search(r"\bflame\b.*express|3dmm\b.*express|blendshape", t):
        signals.append("3DMM expr")
    elif re.search(r"\bexpress(ion)?[\s-]?(driven|control|edit|transfer)", t):
        signals.append("General expr")
    if not signals:
        if category == "Face":
            signals.append("3DMM expr")
        elif category in ("Full-body", "Garment"):
            signals.append("Pose")
        else:
            signals.append("General expr")
    return ", ".join(signals)


def _detect_speed(text: str, prefix: str) -> str:
    t = text.lower()
    if re.search(r"\breal[\s-]?time\b|\binteractive\s*rate|>?\s*30\s*fps", t):
        return "Real-time (>30 FPS)" if prefix == "animation" else "Instant"
    if re.search(r"\bfeed[\s-]?forward\b|\binference\s*time.{0,15}(ms|second)", t):
        return "Instant" if prefix == "creation" else "Real-time (>30 FPS)"
    if re.search(r"\boptimiz\w+\s*(per|each|every|required)", t):
        return "Slow"
    if re.search(r"\bminutes?\b", t):
        return "Fast"
    if re.search(r"\bhours?\b|\bovernight\b", t):
        return "Slow"
    return "Medium" if prefix == "creation" else "Interactive"


def classify_paper(key: str, title: str, abstract: str) -> dict | None:
    """Classify a single paper. Returns classification dict or None to skip."""
    text = title + " " + abstract

    # Check if should be skipped
    skip, reason = _should_skip(title, abstract)
    if skip:
        return {"skip": True, "reason": reason}

    category = _detect_category(text)
    is_asset = _is_assets(title, abstract)
    table_type = "assets" if is_asset else "avatar"

    fields = {
        "Prior Dataset Size": "",
        "Datasets": "",
        "Data Type": _detect_data_type(text),
        "Data Modality": "",
        "Needed Assets": "",
        "Input": _detect_input(text),
        "Additional Priors": "",
        "Creation Speed": _detect_speed(text, "creation"),
        "Contents": category,
    }

    if table_type == "avatar":
        fields.update({
            "Req. Optimization": "Yes" if re.search(r"\boptimiz|per[\s-]?subject\s*train|fine[\s-]?tun", text.lower()) else "No",
            "Animation Signal": _detect_animation_signal(text, category),
            "Lighting Control": "Distant Light" if re.search(r"\brelight|illuminat|lighting\s*control", text.lower()) else "",
            "Animation Speed": _detect_speed(text, "animation"),
            "Image Synthesis": _detect_representation(text),
            "Image Refinement": "No",
        })
    else:
        fields.update({
            "Representation": _detect_representation(text),
            "Simulation Ready": "Yes" if re.search(r"\bsimulat|physic", text.lower()) else "No",
            "Lighting Control": "Distant Light" if re.search(r"\brelight|illuminat", text.lower()) else "",
        })

    fields = normalize_fields(fields)

    return {
        "key": key,
        "table_type": table_type,
        "category": category,
        "fields": fields,
    }


def main():
    # Load existing classifications
    with JSON_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    classified_keys = {item["key"] for item in data.get("avatar_classifications", [])}
    classified_keys |= {item["key"] for item in data.get("assets_classifications", [])}
    skipped_keys = {item["key"] for item in data.get("skipped", [])}
    all_known = classified_keys | skipped_keys

    # Load all bib entries
    entries = parse_bibliography_with_metadata(BIB_FILE)

    def has_meta(e):
        for field in ("webpage", "code", "video", "arxiv"):
            v = e.get(field, "")
            if v and v.lower() != "none":
                return True
        return False

    entries = [e for e in entries if has_meta(e)]

    # Find unclassified
    unclassified = [e for e in entries if e["key"] not in all_known]

    # Load abstracts
    for e in unclassified:
        if not e["abstract"]:
            e["abstract"] = load_abstract_file(e["key"])

    print(f"Found {len(unclassified)} unclassified papers")

    new_avatar = []
    new_assets = []
    new_skipped = []

    for e in unclassified:
        result = classify_paper(e["key"], e["title"], e["abstract"])
        if result is None:
            continue
        if result.get("skip"):
            new_skipped.append({"key": e["key"], "reason": result["reason"]})
            print(f"  SKIP  {e['key']}: {result['reason']}")
        elif result["table_type"] == "assets":
            new_assets.append({"key": result["key"], "table_type": "assets", "fields": result["fields"]})
            print(f"  ASSET {e['key']} -> {result['category']}")
        else:
            new_avatar.append({"key": result["key"], "table_type": "avatar", "fields": result["fields"]})
            print(f"  AVATAR {e['key']} -> {result['category']}")

    # Merge into existing data
    data["avatar_classifications"].extend(new_avatar)
    data["assets_classifications"].extend(new_assets)
    data["skipped"].extend(new_skipped)
    data["metadata"]["avatar_count"] = len(data["avatar_classifications"])
    data["metadata"]["assets_count"] = len(data["assets_classifications"])
    data["metadata"]["skipped_count"] = len(data["skipped"])
    data["metadata"]["total_classified"] = data["metadata"]["avatar_count"] + data["metadata"]["assets_count"]

    # Write updated JSON
    with JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {len(new_avatar)} avatar, {len(new_assets)} assets, {len(new_skipped)} skipped")
    print(f"Total: {data['metadata']['avatar_count']} avatar, {data['metadata']['assets_count']} assets, {data['metadata']['skipped_count']} skipped")
    print(f"Updated {JSON_FILE}")


if __name__ == "__main__":
    main()
