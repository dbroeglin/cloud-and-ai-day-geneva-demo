from event_companion.app import create_app
from event_companion.storage import SQLiteStore
from fastapi.testclient import TestClient


def test_mcp_exposes_only_public_agenda_and_no_private_submission_tools(tmp_path):
    store = SQLiteStore(str(tmp_path / "mcp.sqlite3"), "mcp")
    store.suggest("private-receipt", "Private suggestion", "This must not appear in MCP output.")
    headers = {"Accept": "application/json, text/event-stream"}
    with TestClient(create_app(store)) as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert initialized.status_code == 200
        version = initialized.json()["result"]["protocolVersion"]
        headers["MCP-Protocol-Version"] = version
        tools = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        ).json()["result"]["tools"]
        assert [tool["name"] for tool in tools] == ["get_event_agenda"]
        agenda = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_event_agenda", "arguments": {}},
            },
        )
        assert agenda.status_code == 200
        assert "meeting-to-pull-request" in agenda.text
        assert "Private suggestion" not in agenda.text
        assert "This must not appear" not in agenda.text
