#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Pre-generating static puzzle data…"
python3 scripts/pregenerate.py

echo "Starting Vite dev server on port 5173…"
cd "$SCRIPT_DIR/web"
npm run dev
