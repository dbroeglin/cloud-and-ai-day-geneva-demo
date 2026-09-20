import json
from pathlib import Path

EVENT = json.loads((Path(__file__).parent / "data" / "event.json").read_text())
SESSIONS = {session["id"]: session for session in EVENT["sessions"]}
REFUSAL = "I cannot answer that from the published event information."


def agenda_sources(session_id: str | None = None) -> dict:
    if session_id is not None and session_id not in SESSIONS:
        return {"sources": []}
    sessions = [SESSIONS[session_id]] if session_id else list(SESSIONS.values())
    return {
        "sources": [
            {
                "id": "event",
                "title": EVENT["name"],
                "date": EVENT["date"],
                "timezone": EVENT["timezone"],
                "venue": EVENT["venue"],
                "notice": EVENT["notice"],
            },
            *[
                {
                    "id": f"session:{session['id']}",
                    **{k: v for k, v in session.items() if k != "id"},
                }
                for session in sessions
            ],
        ]
    }
