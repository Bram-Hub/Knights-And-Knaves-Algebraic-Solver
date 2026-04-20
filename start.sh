#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting FastAPI backend on port 8000…"
uvicorn api.main:app --reload --port 8000 &
API_PID=$!

echo "Starting Vite dev server on port 5173…"
cd "$SCRIPT_DIR/web"
npm run dev &
VITE_PID=$!

trap "kill $API_PID $VITE_PID 2>/dev/null; exit" INT TERM
wait
