import inspect
import io
import zipfile
from types import SimpleNamespace

import pytest
from agent_runner import REFUSAL, Draft, download_skill, grounded_answer
from copilot import CopilotClient
from copilot.session import CopilotSession
from telemetry import safe_attributes


def test_installed_sdk_uses_keyword_sessions_string_prompts_and_context_managers():
    creation = inspect.signature(CopilotClient.create_session)
    assert creation.parameters["model"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "provider" in creation.parameters
    assert "skill_directories" in creation.parameters
    assert "available_tools" in creation.parameters
    assert inspect.signature(CopilotSession.send_and_wait).parameters["prompt"].annotation == "str"
    assert hasattr(CopilotClient, "__aexit__")
    assert hasattr(CopilotSession, "__aexit__")


def test_grounding_refuses_missing_or_forged_evidence():
    draft = Draft(answer="A claim", source_ids=["event"], refused=False)
    assert grounded_answer(draft, {}) == {"answer": REFUSAL, "citations": [], "refused": True}
    assert grounded_answer(draft, {"other": {"title": "Other"}})["refused"] is True
    answer = grounded_answer(draft, {"event": {"title": "Verified title"}})
    assert answer["citations"] == [{"source_id": "event", "title": "Verified title"}]


def test_skill_download_writes_only_a_bounded_fixed_path(tmp_path):
    content = "---\nname: event-guide\n---\nRead the agenda.\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../../SKILL.md", content)
        archive.writestr("../../escape.txt", "must not be extracted")
    skills = SimpleNamespace(
        get=lambda _name: SimpleNamespace(default_version="1"),
        download=lambda _name: iter([buffer.getvalue()]),
    )
    project = SimpleNamespace(beta=SimpleNamespace(skills=skills))
    assert download_skill(project, tmp_path / "skills") == content
    assert (tmp_path / "skills" / "event-guide" / "SKILL.md").read_text() == content
    assert not (tmp_path / "escape.txt").exists()


def test_skill_download_rejects_ambiguous_packages(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("one/SKILL.md", "---")
        archive.writestr("two/SKILL.md", "---")
    skills = SimpleNamespace(
        get=lambda _name: SimpleNamespace(default_version="1"),
        download=lambda _name: iter([buffer.getvalue()]),
    )
    with pytest.raises(RuntimeError, match="one bounded"):
        download_skill(SimpleNamespace(beta=SimpleNamespace(skills=skills)), tmp_path / "skills")


def test_telemetry_drops_attendee_content_and_identifiers(monkeypatch):
    monkeypatch.setenv("ENABLE_SENSITIVE_DATA", "false")
    filtered = safe_attributes(
        {
            "gen_ai.prompt": "private attendee text",
            "gen_ai.completion": "private completion",
            "url.full": "https://example.invalid/?private=true",
            "gen_ai.request.model": "gpt-5.4-mini",
            "http.route": "/api/questions/12345678-1234-1234-1234-123456789012",
            "event.public.tool_result": "safe but capture disabled",
        }
    )
    assert filtered == {"gen_ai.request.model": "gpt-5.4-mini", "http.route": "/api/questions/{id}"}
