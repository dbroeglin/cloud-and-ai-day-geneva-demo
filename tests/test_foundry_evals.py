from subprocess import CompletedProcess
from uuid import uuid4

import pytest
from event_companion.evaluation import (
    EvaluationCase,
    assess_response,
    build_report,
    evaluate_cases,
    load_cases,
    passed,
    run_foundry_evaluation,
)


def grounded_payload(request_id):
    return {
        "answer": "The demo starts at 13:27.",
        "citations": [
            {
                "source_id": "session:meeting-to-pull-request",
                "title": "Meeting to pull request",
            }
        ],
        "refused": False,
        "request_id": str(request_id),
    }


def test_load_cases_rejects_duplicate_identifiers_and_empty_lines(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"case_id":"one","question":"One?","expected_outcome":"refused","required_source_ids":[]}\n'
        '{"case_id":"one","question":"Two?","expected_outcome":"refused","required_source_ids":[]}\n'
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(path)
    path.write_text("\n")
    with pytest.raises(ValueError, match="empty line"):
        load_cases(path)


def test_grounded_case_requires_an_exact_citation_set():
    case = EvaluationCase(
        case_id="grounded",
        question="When?",
        expected_outcome="grounded",
        required_source_ids=["session:meeting-to-pull-request"],
    )
    request_id = uuid4()
    assert assess_response(case, grounded_payload(request_id), request_id).passed
    extra = grounded_payload(request_id)
    extra["citations"].append({"source_id": "other", "title": "Other"})
    result = assess_response(case, extra, request_id)
    assert not result.passed
    assert result.diagnostic == "contract_mismatch"


def test_refusal_case_requires_refusal_without_citations():
    case = EvaluationCase(
        case_id="refusal",
        question="Who?",
        expected_outcome="refused",
        required_source_ids=[],
    )
    request_id = uuid4()
    payload = {
        "answer": "I cannot answer that from the published event information.",
        "citations": [],
        "refused": True,
        "request_id": str(request_id),
    }
    assert assess_response(case, payload, request_id).passed
    payload["citations"] = [{"source_id": "session:meeting-to-pull-request", "title": "Demo"}]
    assert not assess_response(case, payload, request_id).passed


def test_failed_requests_are_not_skipped_and_reports_are_bounded():
    case = EvaluationCase(
        case_id="unavailable",
        question="When?",
        expected_outcome="refused",
        required_source_ids=[],
    )
    results = evaluate_cases([case], lambda _case: (_ for _ in ()).throw(ValueError("unavailable")))
    report = build_report(results, "eval_abc", "evalrun_def", "event-guide", "gpt-5.4-mini")
    assert report["failed_cases"] == 1
    assert report["cases"] == [
        {"case_id": "unavailable", "passed": False, "diagnostic": "assistant_request_failed"}
    ]
    assert "question" not in str(report)
    assert not passed(report)


def test_foundry_runner_requires_identifiers():
    def runner(*_args, **_kwargs):
        return CompletedProcess([], 0, stdout="Eval: eval_abc\nRun: evalrun_def\n", stderr="")

    assert run_foundry_evaluation(runner) == ("eval_abc", "evalrun_def")

    def missing_ids(*_args, **_kwargs):
        return CompletedProcess([], 0, stdout="completed", stderr="")

    with pytest.raises(RuntimeError, match="identifiers"):
        run_foundry_evaluation(missing_ids)
