#!/usr/bin/env python3
"""Watch tables_src/ for changes and auto-rebuild HTML tables + publications."""

import subprocess
import sys
import time
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WATCH_DIRS = [
    ROOT / "tables_src",
    ROOT / "assets",
    ROOT / "templates",
    ROOT / "scripts",
    ROOT / "tables",
]
WATCH_EXTENSIONS = {".bib", ".csv", ".tex", ".py", ".txt", ".html", ".css", ".js", ".json"}

def get_snapshot():
    """Return dict of {filepath: mtime} for all watched files."""
    snap = {}
    for d in WATCH_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in WATCH_EXTENSIONS and "__pycache__" not in str(f):
                snap[f] = f.stat().st_mtime
    # Also watch root-level files
    for f in ROOT.glob("*.bib"):
        snap[f] = f.stat().st_mtime
    idx = ROOT / "index.html"
    if idx.exists():
        snap[idx] = idx.stat().st_mtime
    return snap

def rebuild():
    """Run the build steps (tables + publications + cache bust)."""
    print("\n\033[1;34m>>> Rebuilding...\033[0m\n")
    try:
        subprocess.run(
            [sys.executable, "build_tables.py"],
            cwd=ROOT / "tables_src", check=True,
        )
        subprocess.run(
            [sys.executable, "build_publications.py"],
            cwd=ROOT / "tables_src", check=True,
        )
        # Cache bust data-build + CSS/JS references
        import re
        build_ts = str(int(time.time()))
        index = ROOT / "index.html"
        html = index.read_text()
        if 'data-build="' in html:
            html = re.sub(r'data-build="[^"]*"', f'data-build="{build_ts}"', html)
        else:
            html = html.replace('<html lang="en">', f'<html lang="en" data-build="{build_ts}">')
        html = re.sub(r'style\.css[^"]*"', f'style.css?v={build_ts}"', html)
        html = re.sub(r'app\.js[^"]*"', f'app.js?v={build_ts}"', html)
        html = re.sub(r'bib-popup\.js[^"]*"', f'bib-popup.js?v={build_ts}"', html)
        index.write_text(html)

        print(f"\033[1;32m>>> Rebuild complete (v{build_ts}). Refresh your browser.\033[0m\n")
    except subprocess.CalledProcessError as e:
        print(f"\033[1;31m>>> Build failed: {e}\033[0m\n")

def main():
    poll_interval = 1.0  # seconds
    dirs = ", ".join(str(d.relative_to(ROOT)) for d in WATCH_DIRS if d.exists())
    print(f"Watching [{dirs}] for changes (poll every {poll_interval}s)...")
    print("Press Ctrl+C to stop.\n")

    # Initial build
    rebuild()
    prev = get_snapshot()

    while True:
        time.sleep(poll_interval)
        curr = get_snapshot()

        changed = []
        for f, mtime in curr.items():
            if f not in prev or prev[f] != mtime:
                changed.append(f)
        for f in prev:
            if f not in curr:
                changed.append(f)

        if changed:
            names = [str(f.relative_to(ROOT)) for f in changed]
            print(f"\033[0;33mChanged: {', '.join(names)}\033[0m")
            rebuild()
            prev = get_snapshot()

if __name__ == "__main__":
    main()
