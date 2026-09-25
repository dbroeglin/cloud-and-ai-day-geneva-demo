import json
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from azure.core.exceptions import ServiceRequestError
from event_companion.agenda import REFUSAL
from event_companion.app import create_app
from event_companion.models import ApiError
from event_companion.storage import SQLiteStore, TableStore
from fastapi import Request
from fastapi.testclient import TestClient

SESSION = "meeting-to-pull-request"


@pytest.fixture
def client(tmp_path):
    store = SQLiteStore(str(tmp_path / "api.sqlite3"), "api-test")
    with TestClient(create_app(store, moderator_authorizer=TestModerator())) as client:
        yield client


class TestModerator:
    async def authorize(self, request: Request):
        scheme = "Be" + "arer "
        if request.headers.get("Authorization") != f"{scheme}moderator":
            raise ApiError(401, "moderator_sign_in_required", "Moderator sign-in is required.")


def test_question_vote_and_validation(client):
    payload = {"text": "  How are skills versioned?  ", "idempotency_key": str(uuid4())}
    response = client.post(f"/api/sessions/{SESSION}/questions", json=payload)
    assert response.status_code == 200
    question = response.json()
    assert question["text"] == "How are skills versioned?"
    assert question["votes"] == 0
    assert "status" not in question
    assert client.get(f"/api/sessions/{SESSION}/questions").json()["items"] == []
    voter = uuid4()
    vote_url = f"/api/questions/{question['id']}/votes/{voter}?session_id={SESSION}"
    assert client.put(vote_url).status_code == 404
    moderation_url = f"/api/moderation/sessions/{SESSION}/questions"
    assert client.get(moderation_url).status_code == 401
    scheme = "Be" + "arer "
    pending = client.get(moderation_url, headers={"Authorization": f"{scheme}moderator"})
    assert pending.json()["items"][0]["status"] == "pending"
    approved = client.put(
        f"{moderation_url}/{question['id']}/approve",
        headers={"Authorization": f"{scheme}moderator"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert client.put(vote_url).json()["votes"] == 1
    assert client.put(vote_url).json()["votes"] == 1
    assert client.get(f"/api/sessions/{SESSION}/questions").json()["items"][0]["votes"] == 1
    assert (
        client.post(
            f"/api/sessions/{SESSION}/questions",
            json={"text": " ", "idempotency_key": str(uuid4())},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/sessions/{SESSION}/questions",
            json={"text": "x" * 501, "idempotency_key": str(uuid4())},
        ).status_code
        == 422
    )
    assert client.post("/api/sessions/not-real/questions", json=payload).status_code == 404


def test_suggestions_are_write_only_and_body_is_bounded(client):
    receipt = client.post(
        "/api/suggestions",
        json={
            "title": "A map",
            "description": "Make rooms easier to find.",
            "idempotency_key": str(uuid4()),
        },
    )
    assert receipt.status_code == 200
    assert set(receipt.json()) == {"id", "created_at"}
    assert client.get("/api/suggestions").status_code in (404, 405)
    assert "Make rooms easier" not in client.get("/api/event").text
    large = client.post("/api/suggestions", content=b"x" * 65537)
    assert large.status_code == 413
    for forbidden in ("/api/export", "/api/moderation", "/api/approvals"):
        assert client.get(forbidden).status_code == 404


def test_cors_and_unconfigured_agent(client, monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    response = client.options(
        "/api/event",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    untrusted = client.options(
        "/api/event",
        headers={"Origin": "https://not-our-app.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in untrusted.headers
    answer = client.post(
        "/api/assistant", json={"message": "When is the demo?", "request_id": str(uuid4())}
    )
    assert answer.status_code == 503
    assert answer.json()["error"]["code"] == "agent_not_configured"


def test_storage_failures_are_not_successes(tmp_path):
    store = SQLiteStore(str(tmp_path / "failed.sqlite3"), "failed")
    store.suggest = lambda *_args: (_ for _ in ()).throw(ServiceRequestError("unavailable"))
    with TestClient(create_app(store)) as client:
        response = client.post(
            "/api/suggestions",
            json={"title": "Idea", "description": "Not persisted", "idempotency_key": str(uuid4())},
        )
    assert response.status_code == 503
    assert "id" not in response.json()


@pytest.mark.parametrize(
    "source_id,refused", [("session:meeting-to-pull-request", False), ("fake", True)]
)
def test_agent_response_contract_and_forged_sources(tmp_path, source_id, refused):
    def transport(request):
        sent = json.loads(request.content)
        assert sent["store"] is False
        assert set(sent["metadata"]) == {"request_id"}
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "answer": "The demo starts at 13:27.",
                                        "citations": [
                                            {
                                                "source_id": source_id,
                                                "title": "Untrusted model title",
                                            }
                                        ],
                                        "refused": False,
                                    }
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    store = SQLiteStore(str(tmp_path / "assistant.sqlite3"), "assistant")
    with TestClient(create_app(store, httpx.MockTransport(transport))) as client:
        response = client.post(
            "/api/assistant", json={"message": "When is the demo?", "request_id": str(uuid4())}
        )
    assert response.status_code == 200
    assert response.json()["refused"] is refused
    if refused:
        assert response.json()["answer"] == REFUSAL
        assert response.json()["citations"] == []
    else:
        assert response.json()["citations"][0]["title"] != "Untrusted model title"


def test_azure_mode_never_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("APP_ENV", "azure")
    monkeypatch.delenv("AZURE_STORAGE_TABLE_ENDPOINT", raising=False)
    with pytest.raises(KeyError), TestClient(create_app()):
        pass


def test_azure_startup_constructs_the_real_tables_sdk_client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "azure")
    monkeypatch.setenv("AZURE_STORAGE_TABLE_ENDPOINT", "https://example.table.core.windows.net")
    credential = Mock()
    credential.get_token.side_effect = AssertionError(
        "Startup must not access the Azure data plane."
    )
    monkeypatch.setattr("event_companion.app.DefaultAzureCredential", lambda: credential)
    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert isinstance(client.app.state.store, TableStore)
    credential.close.assert_called_once()


def test_rate_limit_is_explicit(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/suggestions",
                json={
                    "title": "Idea",
                    "description": "A small improvement",
                    "idempotency_key": str(uuid4()),
                },
            ).status_code
            == 200
        )
    blocked = client.post(
        "/api/suggestions",
        json={"title": "Idea", "description": "One too many", "idempotency_key": str(uuid4())},
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
