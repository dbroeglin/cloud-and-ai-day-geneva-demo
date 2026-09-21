#!/usr/bin/env python3
"""Run deterministic assistant checks and a Foundry hosted-agent evaluation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))

from event_companion.evaluation import (  # noqa: E402
    build_report,
    evaluate_cases,
    invoke_assistant,
    load_cases,
    passed,
    run_foundry_evaluation,
)

CASES = ROOT / "src" / "agents" / "event-guide" / "evals" / "v1" / "cases.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-origin", required=True)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument(
        "--skip-foundry",
        action="store_true",
        help="Run deterministic contract checks only; never use this for release approval.",
    )
    args = parser.parse_args()
    try:
        cases = load_cases(CASES)
        results = evaluate_cases(
            cases,
            lambda case: invoke_assistant(args.backend_origin, case),
        )
        evaluation_id = evaluation_run_id = None
        if not args.skip_foundry:
            evaluation_id, evaluation_run_id = run_foundry_evaluation()
        report = build_report(
            results,
            evaluation_id,
            evaluation_run_id,
            os.getenv("FOUNDRY_AGENT_NAME", "event-guide"),
            os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"] if not args.skip_foundry else "not-run",
        )
        report["timestamp_utc"] = datetime.now(UTC).isoformat()
        if args.report_path:
            args.report_path.parent.mkdir(parents=True, exist_ok=True)
            args.report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0 if passed(report) and (args.skip_foundry or evaluation_run_id) else 1
    except (KeyError, RuntimeError, ValueError, OSError) as error:
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
