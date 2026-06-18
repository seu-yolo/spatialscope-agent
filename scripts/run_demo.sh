#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DATA_PATH="${1:-data/demo_embryo.h5ad}"
MODE="${2:-standard}"
QUERY="${3:-Explore early mouse embryo spatial structure, rank cluster markers, and plot Pou5f1 Sox2 Nanog Sox17 Gata6 T Mesp1.}"

run_python() {
  if command -v conda >/dev/null 2>&1; then
    conda run --no-capture-output -n spatialscope-agent python "$@"
  else
    python "$@"
  fi
}

if [ ! -f "$DATA_PATH" ]; then
  run_python scripts/create_demo_data.py --output "$DATA_PATH"
fi

run_python cli.py run \
  --data "$DATA_PATH" \
  --query "$QUERY" \
  --mode "$MODE"
