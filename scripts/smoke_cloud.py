#!/usr/bin/env python3
"""Verify the real deployed app; writes only clearly labelled synthetic smoke data."""

import argparse
import json
import re
import subprocess
import time
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from azure_hooks import environment, https_url, needed


def request(client, method, url, *, payload=None, attempts=1):
    for attempt in range(attempts):
        response = client.request(method, url, json=payload)
        if response.status_code in (424, 429, 502, 503, 504) and attempt + 1 < attempts:
            time.sleep(min(60, 15 * (attempt + 1)))
            continue
        response.raise_for_status()
        return response
    raise AssertionError("unreachable retry state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart-backend", action="store_true")
    args = parser.parse_args()
    values = environment()
    frontend = https_url(needed(values, "FRONTEND_ORIGIN"), origin=True)
    backend = https_url(needed(values, "BACKEND_ORIGIN"), origin=True)
    session = "meeting-to-pull-request"
    key = str(uuid4())
    suggestion_key = str(uuid4())
    question_payload = {
        "text": "Demo check: how does the event guide use the published agenda?",
        "idempotency_key": key,
    }
    suggestion_payload = {
        "title": "Demo check: clearer session rooms",
        "description": "Synthetic deployment verification; a room map would help attendees.",
        "idempotency_key": suggestion_key,
    }
    with httpx.Client(timeout=75, follow_redirects=True) as client:
        page = request(client, "GET", frontend, attempts=4)
        assert "Cloud &amp; AI Day Geneva" in page.text, "Not the companion frontend."
        assets = re.findall(r'<script[^>]+src="([^"]+)"', page.text)
        assert assets, "Frontend JavaScript asset missing."
        assert any(
            backend in request(client, "GET", urljoin(frontend, asset)).text for asset in assets
        ), "Frontend bundle does not target the current backend."
        assert request(client, "GET", backend + "/api/health", attempts=4).json()["status"] == "ok"
        event = request(client, "GET", backend + "/api/event").json()
        assert any(item["id"] == session for item in event["sessions"])
        question = request(
            client, "POST", f"{backend}/api/sessions/{session}/questions", payload=question_payload
        ).json()
        assert question["id"] == key
        voter = uuid4()
        vote_url = f"{backend}/api/questions/{key}/votes/{voter}?session_id={session}"
        assert request(client, "PUT", vote_url).json()["votes"] == 1
        assert request(client, "PUT", vote_url).json()["votes"] == 1
        receipt = request(
            client, "POST", backend + "/api/suggestions", payload=suggestion_payload
        ).json()
        assert receipt["id"] == suggestion_key
        assert client.get(backend + "/api/suggestions").status_code in (404, 405)

        if args.restart_backend:
            app = needed(values, "AZURE_BACKEND_NAME")
            group = needed(values, "AZURE_RESOURCE_GROUP")
            revision = subprocess.check_output(
                [
                    "az",
                    "containerapp",
                    "show",
                    "-n",
                    app,
                    "-g",
                    group,
                    "--query",
                    "properties.latestReadyRevisionName",
                    "-o",
                    "tsv",
                ],
                text=True,
            ).strip()
            assert revision, "No ready backend revision exists."
            subprocess.run(
                [
                    "az",
                    "containerapp",
                    "revision",
                    "restart",
                    "-n",
                    app,
                    "-g",
                    group,
                    "--revision",
                    revision,
                    "--only-show-errors",
                ],
                check=True,
            )
            request(client, "GET", backend + "/api/health", attempts=6)
            persisted = request(
                client,
                "POST",
                f"{backend}/api/sessions/{session}/questions",
                payload=question_payload,
                attempts=4,
            ).json()
            assert persisted["votes"] == 1 and persisted["created_at"] == question["created_at"]
            again = request(
                client,
                "POST",
                backend + "/api/suggestions",
                payload=suggestion_payload,
                attempts=4,
            ).json()
            assert again == receipt

        answer = request(
            client,
            "POST",
            backend + "/api/assistant",
            payload={
                "message": "When does the live demonstration start?",
                "request_id": str(uuid4()),
            },
            attempts=5,
        ).json()
        assert answer["refused"] is False and answer["citations"]
        assert "13:27" in answer["answer"], "Expected a grounded answer from the actual agenda."
        refusal = request(
            client,
            "POST",
            backend + "/api/assistant",
            payload={
                "message": "What is tomorrow's weather forecast in Tokyo?",
                "request_id": str(uuid4()),
            },
            attempts=3,
        ).json()
        assert refusal["refused"] is True and refusal["citations"] == []
    print(
        json.dumps(
            {
                "frontend": frontend,
                "backend": backend,
                "frontend_bundle": "passed",
                "durable_writes": "passed",
                "restart_persistence": "passed" if args.restart_backend else "not exercised",
                "real_agent_grounding": "passed",
                "unsupported_question_refusal": "passed",
                "synthetic_question_id": key,
                "synthetic_suggestion_id": suggestion_key,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
