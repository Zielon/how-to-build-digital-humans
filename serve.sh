#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8000}"

cleanup() {
  echo -e "\nStopping..."
  kill $SERVER_PID $WATCH_PID 2>/dev/null
  wait $SERVER_PID $WATCH_PID 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Serving at http://localhost:$PORT"
echo "Watching tables_src/ for changes — auto-rebuild on save."
echo "Press Ctrl+C to stop."
echo ""

# Use conda python if available, otherwise python3
PY=$(command -v python 2>/dev/null || command -v python3)

# Start HTTP server
$PY -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT" &
SERVER_PID=$!

# Start file watcher
$PY "$ROOT/watch.py" &
WATCH_PID=$!

wait
