from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spatialscope.agent.graph import run_agent
from spatialscope.agent.llm import llm_config_status, smoke_test_llm


def _load_dotenv_quietly() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpatialScope Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a spatial transcriptomics workflow")
    run.add_argument("--data", required=True, help="Path to an .h5ad file")
    run.add_argument("--query", required=True, help="Natural-language analysis request")
    run.add_argument("--mode", choices=["quick", "standard", "advanced"], default="quick")
    run.add_argument("--outdir", default="outputs/runs")
    llm = subparsers.add_parser("llm-check", help="Inspect LLM configuration and optionally run a live smoke test")
    llm.add_argument("--live", action="store_true", help="Send a tiny JSON smoke prompt to the configured provider")
    llm.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    _load_dotenv_quietly()
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
    if args.command == "llm-check":
        payload = smoke_test_llm() if args.live else {"status": "configured" if llm_config_status()["enabled"] else "fallback", "config": llm_config_status()}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            config = payload["config"]
            print(f"Provider: {config['provider']}")
            print(f"Model: {config['model']}")
            print(f"Base URL: {config['base_url']}")
            print(f"API key: {config['api_key_preview']}")
            print(f"Fallback: {config['fallback']}")
            print(f"Status: {payload['status']}")
            if payload.get("summary"):
                print(f"Summary: {payload['summary']}")
        return 0 if payload["status"] in {"configured", "success", "skipped", "fallback"} else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
