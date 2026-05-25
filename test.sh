#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY=$(command -v python3 2>/dev/null || command -v python)

echo "Running tests..."
$PY -m pytest "$ROOT/tests" -v "$@"
