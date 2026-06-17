#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${1:-8501}"

if command -v conda >/dev/null 2>&1; then
  conda run --no-capture-output -n spatialscope-agent streamlit run app.py --server.port "$PORT"
else
  streamlit run app.py --server.port "$PORT"
fi
