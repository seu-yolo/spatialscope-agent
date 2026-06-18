#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_cmd() {
  if command -v conda >/dev/null 2>&1; then
    conda run --no-capture-output -n spatialscope-agent "$@"
  else
    "$@"
  fi
}

if [ ! -f data/demo_embryo.h5ad ]; then
  run_cmd python scripts/create_demo_data.py --output data/demo_embryo.h5ad
fi

run_cmd pytest
SPATIALSCOPE_LLM_API_KEY= DEEPSEEK_API_KEY= run_cmd python cli.py run \
  --data data/demo_embryo.h5ad \
  --query "Run quick spatial analysis and plot Pou5f1 Sox17 Mesp1" \
  --mode quick
