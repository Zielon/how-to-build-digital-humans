#!/usr/bin/env bash
# Converts assets/img/thumbnails/*.jpg to WebP at max width 400 px.
# Requires: cwebp (brew install webp). Uses macOS `sips` to read width.
# Writes .webp next to each .jpg. Does not delete originals.
# After conversion, swap .jpg -> .webp in tables_src/build_publications.py
# (thumb_src line) and regenerate.

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)/assets/img/thumbnails"
MAX_WIDTH=800
QUALITY=78

if ! command -v cwebp >/dev/null; then
  echo "cwebp not found. Install with: brew install webp" >&2
  exit 1
fi
if ! command -v sips >/dev/null; then
  echo "sips not found (expected on macOS)." >&2
  exit 1
fi

cd "$SRC_DIR"
count=0
skipped=0
for f in *.jpg; do
  [ -e "$f" ] || continue
  out="${f%.jpg}.webp"
  if [ -f "$out" ] && [ "$out" -nt "$f" ]; then
    skipped=$((skipped + 1))
    continue
  fi
  w=$(sips -g pixelWidth "$f" 2>/dev/null | awk '/pixelWidth/{print $2}')
  if [ -n "$w" ] && [ "$w" -gt "$MAX_WIDTH" ]; then
    cwebp -quiet -q "$QUALITY" -resize "$MAX_WIDTH" 0 "$f" -o "$out"
  else
    cwebp -quiet -q "$QUALITY" "$f" -o "$out"
  fi
  count=$((count + 1))
done
echo "Converted $count, skipped $skipped (already up-to-date)."
echo "Next: change thumb_src to .webp in tables_src/build_publications.py and regenerate."
