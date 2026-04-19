#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY=$(command -v python 2>/dev/null || command -v python3)

echo -e "\n======== Fetching thumbnails ========\n"
cd "$ROOT/scripts"
$PY fetch_thumbnails.py

echo -e "\n======== Converting thumbnails to WebP ========\n"
bash "$ROOT/scripts/convert_thumbnails_webp.sh"

echo -e "\n======== Fetching abstracts ========\n"
cd "$ROOT/tables_src"
$PY fetch_abstracts.py

echo -e "\n======== Building tables ========\n"
$PY build_tables.py

echo -e "\n======== Building publications ========\n"
$PY build_publications.py

echo -e "\n======== Building statistics ========\n"
$PY build_statistics.py

echo -e "\n======== Updating cache version ========\n"
cd "$ROOT"
BUILD_TS=$(date +%s)
# Inject or update the data-build attribute on <html> for cache busting
if grep -q 'data-build=' index.html; then
  sed -i '' "s/data-build=\"[^\"]*\"/data-build=\"${BUILD_TS}\"/" index.html
else
  sed -i '' "s/<html lang=\"en\">/<html lang=\"en\" data-build=\"${BUILD_TS}\">/" index.html
fi

# Cache-bust CSS and JS file references
sed -i '' "s|style\.css[^\"]*\"|style.css?v=${BUILD_TS}\"|" index.html
sed -i '' "s|app\.js[^\"]*\"|app.js?v=${BUILD_TS}\"|" index.html
sed -i '' "s|bib-popup\.js[^\"]*\"|bib-popup.js?v=${BUILD_TS}\"|" index.html

echo "Build version: ${BUILD_TS}"
echo -e "\n======== Done ========\n"
