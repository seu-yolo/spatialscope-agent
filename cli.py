from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spatialscope.agent.graph import run_agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpatialScope Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a spatial transcriptomics workflow")
    run.add_argument("--data", required=True, help="Path to an .h5ad file")
    run.add_argument("--query", required=True, help="Natural-language analysis request")
    run.add_argument("--mode", choices=["quick", "standard", "advanced"], default="quick")
    run.add_argument("--outdir", default="outputs/runs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        state = run_agent(data_path=args.data, query=args.query, mode=args.mode, outdir=args.outdir)
        report = state.get("report_path")
        print(f"Run ID: {state.get('run_id')}")
        print(f"Report: {report}")
        print(f"Warnings: {len(state.get('warnings', []))}")
        print(f"Errors: {len(state.get('errors', []))}")
        if report and Path(str(report)).exists():
            return 0
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

