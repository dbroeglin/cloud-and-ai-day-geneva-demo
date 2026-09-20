import importlib.util
import json
from pathlib import Path

from starlette.testclient import TestClient


def test_real_responses_host_emits_the_backend_contract(monkeypatch):
    path = Path(__file__).parents[1] / "src" / "agents" / "event-guide" / "main.py"
    spec = importlib.util.spec_from_file_location("event_guide_host", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def answer(message):
        assert message == "When is the demo?"
        return {
            "answer": "The live demo starts at 13:27.",
            "citations": [{"source_id": "session:meeting-to-pull-request", "title": "Demo"}],
            "refused": False,
        }

    monkeypatch.setattr(module, "run_agent", answer)
    with TestClient(module.app) as client:
        assert client.get("/readiness").status_code == 200
        response = client.post(
            "/responses",
            json={
                "input": "When is the demo?",
                "store": False,
                "stream": False,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    text = "".join(
        content["text"]
        for item in payload["output"]
        if item["type"] == "message"
        for content in item["content"]
        if content["type"] == "output_text"
    )
    assert json.loads(text)["citations"][0]["source_id"] == "session:meeting-to-pull-request"
