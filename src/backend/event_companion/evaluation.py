from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import AssistantAnswer

FOUNDATION_EVAL_COMMAND = (
    "azd",
    "ai",
    "agent",
    "eval",
    "run",
    "--config",
    "eval.yaml",
)
EVAL_ID = re.compile(r"(?m)^\s*Eval:\s*(eval_[A-Za-z0-9]+)\s*$")
EVAL_RUN_ID = re.compile(r"(?m)^\s*Run:\s*(evalrun_[A-Za-z0-9]+)\s*$")


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    case_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    question: str = Field(min_length=1, max_length=1000)
    expected_outcome: Literal["grounded", "refused"]
    required_source_ids: list[str] = Field(max_length=20)

    @field_validator("required_source_ids")
    @classmethod
    def require_unique_source_ids(cls, value: list[str]) -> list[str]:
        if any(not source_id or len(source_id) > 200 for source_id in value):
            raise ValueError("required_source_ids must contain bounded non-empty values.")
        if len(value) != len(set(value)):
            raise ValueError("required_source_ids must not contain duplicates.")
        return value

    @model_validator(mode="after")
    def require_ids_for_grounded_cases(self) -> EvaluationCase:
        if self.expected_outcome == "grounded" and not self.required_source_ids:
            raise ValueError("grounded cases require at least one source ID.")
        if self.expected_outcome == "refused" and self.required_source_ids:
            raise ValueError("refused cases must not declare source IDs.")
        return self


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    schema_valid: bool
    outcome_correct: bool
    citation_precision: bool
    citation_recall: bool
    refusal_correct: bool
    diagnostic: str | None

    @property
    def passed(self) -> bool:
        return all(
            (
                self.schema_valid,
                self.outcome_correct,
                self.citation_precision,
                self.citation_recall,
                self.refusal_correct,
            )
        )


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Evaluation dataset contains an empty line at {line_number}.")
        try:
            cases.append(EvaluationCase.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"Invalid evaluation case at line {line_number}: {error}") from error
    if not cases:
        raise ValueError("Evaluation dataset must contain at least one case.")
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Evaluation dataset contains duplicate case IDs.")
    return cases


def assess_response(case: EvaluationCase, payload: object, request_id: UUID) -> CaseResult:
    try:
        answer = AssistantAnswer.model_validate(payload)
        if answer.request_id != str(request_id):
            raise ValueError("Response request_id does not match the evaluation request.")
    except ValueError:
        return CaseResult(
            case_id=case.case_id,
            schema_valid=False,
            outcome_correct=False,
            citation_precision=False,
            citation_recall=False,
            refusal_correct=False,
            diagnostic="invalid_response_schema",
        )

    actual_source_ids = [citation.source_id for citation in answer.citations]
    expected_source_ids = set(case.required_source_ids)
    actual_source_id_set = set(actual_source_ids)
    citation_precision = (
        len(actual_source_ids) == len(actual_source_id_set)
        and actual_source_id_set.issubset(expected_source_ids)
    )
    citation_recall = actual_source_id_set == expected_source_ids
    if case.expected_outcome == "grounded":
        outcome_correct = not answer.refused
        refusal_correct = not answer.refused
    else:
        outcome_correct = answer.refused
        refusal_correct = answer.refused and not actual_source_ids
    diagnostic = None
    if not all((outcome_correct, citation_precision, citation_recall, refusal_correct)):
        diagnostic = "contract_mismatch"
    return CaseResult(
        case_id=case.case_id,
        schema_valid=True,
        outcome_correct=outcome_correct,
        citation_precision=citation_precision,
        citation_recall=citation_recall,
        refusal_correct=refusal_correct,
        diagnostic=diagnostic,
    )


def invoke_assistant(backend_origin: str, case: EvaluationCase) -> tuple[dict, UUID]:
    request_id = uuid4()
    response = httpx.post(
        f"{backend_origin.rstrip('/')}/api/assistant",
        json={"message": case.question, "request_id": str(request_id)},
        timeout=65,
    )
    response.raise_for_status()
    return response.json(), request_id


def evaluate_cases(
    cases: Iterable[EvaluationCase],
    invoke: Callable[[EvaluationCase], tuple[object, UUID]],
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        try:
            payload, request_id = invoke(case)
            results.append(assess_response(case, payload, request_id))
        except (httpx.HTTPError, ValueError, TypeError):
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    schema_valid=False,
                    outcome_correct=False,
                    citation_precision=False,
                    citation_recall=False,
                    refusal_correct=False,
                    diagnostic="assistant_request_failed",
                )
            )
    return results


def run_foundry_evaluation(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, str]:
    completed = runner(
        FOUNDATION_EVAL_COMMAND,
        check=True,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    evaluation_id = EVAL_ID.search(output)
    evaluation_run_id = EVAL_RUN_ID.search(output)
    if not evaluation_id or not evaluation_run_id:
        raise RuntimeError("Foundry evaluation completed without evaluation and run identifiers.")
    return evaluation_id.group(1), evaluation_run_id.group(1)


def build_report(
    results: list[CaseResult],
    evaluation_id: str | None,
    evaluation_run_id: str | None,
    agent_name: str,
    model_deployment: str,
) -> dict:
    if not results:
        raise ValueError("Evaluation report cannot be created without case results.")
    metric_names = (
        "schema_valid",
        "outcome_correct",
        "citation_precision",
        "citation_recall",
        "refusal_correct",
    )
    metrics = {name: sum(getattr(result, name) for result in results) for name in metric_names}
    failed = [result for result in results if not result.passed]
    return {
        "evaluation_id": evaluation_id,
        "evaluation_run_id": evaluation_run_id,
        "agent_name": agent_name,
        "model_deployment": model_deployment,
        "total_cases": len(results),
        "passed_cases": len(results) - len(failed),
        "failed_cases": len(failed),
        "metrics": {
            name: {"passed": count, "total": len(results)} for name, count in metrics.items()
        },
        "cases": [
            {"case_id": result.case_id, "passed": result.passed, "diagnostic": result.diagnostic}
            for result in results
        ],
    }


def passed(report: dict) -> bool:
    return (
        report["failed_cases"] == 0
        and all(metric["passed"] == metric["total"] for metric in report["metrics"].values())
    )
