import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Annotated, Protocol
from uuid import UUID

import httpx
from azure.core.exceptions import AzureError
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from opentelemetry import trace
from opentelemetry.propagate import inject
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from .agenda import EVENT, REFUSAL, SESSIONS, agenda_sources
from .auth import EntraAuthorizer
from .models import (
    ApiError,
    AssistantAnswer,
    AssistantInput,
    ModerationQuestion,
    ModerationQuestionPage,
    Question,
    QuestionInput,
    QuestionPage,
    Receipt,
    SuggestionInput,
)
from .storage import SQLiteStore, Store, TableStore

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("event-companion-backend")


class ModeratorAuthorizer(Protocol):
    async def authorize(self, request: Request) -> None: ...


class BodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT"):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 65536:
                response = JSONResponse(
                    {"error": {"code": "body_too_large", "message": "Request exceeds 64 KiB."}},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class RateLimit:
    def __init__(self):
        self.windows: OrderedDict[tuple[str, str], tuple[float, int]] = OrderedDict()

    def check(self, request: Request, category: str, limit: int) -> None:
        host = request.client.host if request.client else "unknown"
        key = (hashlib.sha256(host.encode()).hexdigest(), category)
        now = time.monotonic()
        start, count = self.windows.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= limit:
            raise ApiError(429, "rate_limited", "Please wait a minute before trying again.")
        self.windows[key] = (start, count + 1)
        self.windows.move_to_end(key)
        if len(self.windows) > 2048:
            self.windows.popitem(last=False)


def create_app(
    store: Store | None = None,
    agent_transport=None,
    moderator_authorizer: ModeratorAuthorizer | None = None,
) -> FastAPI:
    credential: DefaultAzureCredential | None = None
    owned_store = store is None
    limiter = RateLimit()
    agent_slots = asyncio.Semaphore(2)
    moderator_authorizer = moderator_authorizer or EntraAuthorizer()
    mcp = MCPServer("Geneva public agenda", version="1.0.0")

    @mcp.tool()
    def get_event_agenda(session_id: str | None = None) -> dict:
        """Read public Geneva event facts. Omit session_id for all sessions; samples are marked."""
        with tracer.start_as_current_span("execute_tool get_event_agenda") as span:
            span.set_attribute("gen_ai.tool.name", "get_event_agenda")
            result = agenda_sources(session_id)
            span.set_attribute("event.source_count", len(result["sources"]))
            return result

    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp", json_response=True, stateless_http=True, host="0.0.0.0"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal store, credential
        if store is None:
            mode = os.getenv("APP_ENV", "local")
            namespace = os.getenv("EVENT_NAMESPACE", "geneva-2026-local")
            if mode == "azure":
                endpoint = os.environ["AZURE_STORAGE_TABLE_ENDPOINT"]
                if not endpoint.startswith("https://"):
                    raise RuntimeError("Azure Table endpoint must use HTTPS.")
                credential = DefaultAzureCredential()
                store = TableStore(
                    TableClient(
                        endpoint,
                        os.getenv("EVENT_TABLE_NAME", "EventCompanion"),
                        credential=credential,
                    ),
                    namespace,
                )
            elif mode == "local":
                store = SQLiteStore(
                    os.getenv("LOCAL_DATABASE_PATH", ".local/event-companion.sqlite3"), namespace
                )
            else:
                raise RuntimeError("APP_ENV must be local or azure.")
        app.state.store = store
        async with mcp_app.router.lifespan_context(mcp_app):
            try:
                yield
            finally:
                if owned_store and store is not None:
                    store.close()
                if credential:
                    credential.close()

    app = FastAPI(title="Geneva Event Companion", lifespan=lifespan)
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if os.getenv("FRONTEND_ORIGIN"):
        origins.append(os.environ["FRONTEND_ORIGIN"].rstrip("/"))
    app.add_middleware(BodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "traceparent", "tracestate"],
        max_age=600,
    )

    @app.exception_handler(ApiError)
    async def api_error(_request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status,
            headers={"Retry-After": "60"} if exc.status == 429 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_input",
                    "message": "Check the field lengths and identifiers.",
                }
            },
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return JSONResponse(
            {"error": {"code": "http_error", "message": "The requested operation is unavailable."}},
            status_code=exc.status_code,
        )

    @app.exception_handler(AzureError)
    @app.exception_handler(sqlite3.Error)
    async def storage_error(_request, exc):
        logger.error(
            "Storage operation failed: %s status=%s code=%s",
            type(exc).__name__,
            getattr(exc, "status_code", None),
            getattr(exc, "error_code", None),
        )
        return JSONResponse(
            {
                "error": {
                    "code": "storage_unavailable",
                    "message": "Storage is unavailable. Retry later.",
                }
            },
            status_code=503,
        )

    def session_exists(session_id: str) -> None:
        if session_id not in SESSIONS:
            raise ApiError(404, "session_not_found", "That session is not in the published agenda.")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "event-companion"}

    @app.get("/api/event")
    def event():
        return EVENT

    @app.get("/api/sessions/{session_id}/questions", response_model=QuestionPage)
    def questions(
        request: Request,
        session_id: str,
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        session_exists(session_id)
        return request.app.state.store.questions(session_id, cursor)

    @app.post("/api/sessions/{session_id}/questions", response_model=Question)
    async def add_question(request: Request, session_id: str, value: QuestionInput):
        session_exists(session_id)
        limiter.check(request, "write", 30)
        return await asyncio.to_thread(
            request.app.state.store.add_question, session_id, str(value.idempotency_key), value.text
        )

    @app.get(
        "/api/moderation/sessions/{session_id}/questions", response_model=ModerationQuestionPage
    )
    async def pending_questions(
        request: Request,
        session_id: str,
        _moderator: None = Depends(moderator_authorizer.authorize),
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        session_exists(session_id)
        limiter.check(request, "moderation_read", 60)
        return await asyncio.to_thread(
            request.app.state.store.pending_questions, session_id, cursor
        )

    @app.put(
        "/api/moderation/sessions/{session_id}/questions/{question_id}/approve",
        response_model=ModerationQuestion,
    )
    async def approve_question(
        request: Request,
        session_id: str,
        question_id: UUID,
        _moderator: None = Depends(moderator_authorizer.authorize),
    ):
        session_exists(session_id)
        limiter.check(request, "moderation_write", 30)
        return await asyncio.to_thread(
            request.app.state.store.approve_question, session_id, str(question_id)
        )

    @app.put("/api/questions/{question_id}/votes/{voter_id}", response_model=Question)
    async def vote(request: Request, question_id: UUID, voter_id: UUID, session_id: str):
        session_exists(session_id)
        limiter.check(request, "vote", 60)
        return await asyncio.to_thread(
            request.app.state.store.vote, session_id, str(question_id), str(voter_id)
        )

    @app.post("/api/suggestions", response_model=Receipt)
    async def suggest(request: Request, value: SuggestionInput):
        limiter.check(request, "suggestion", 10)
        return await asyncio.to_thread(
            request.app.state.store.suggest,
            str(value.idempotency_key),
            value.title,
            value.description,
        )

    @app.post("/api/assistant", response_model=AssistantAnswer)
    async def assistant(request: Request, value: AssistantInput):
        nonlocal credential
        limiter.check(request, "assistant", 3)
        endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        if not endpoint and agent_transport is None:
            raise ApiError(
                503, "agent_not_configured", "The hosted event assistant is not configured."
            )
        if credential is None and agent_transport is None:
            credential = DefaultAzureCredential()
        headers = {"Content-Type": "application/json"}
        inject(headers)
        url = (
            f"{(endpoint or 'https://test.invalid').rstrip('/')}/agents/"
            f"{os.getenv('FOUNDRY_AGENT_NAME', 'event-guide')}/endpoint/protocols/openai/responses"
        )
        try:
            async with asyncio.timeout(60), agent_slots:
                if credential:
                    token = await asyncio.to_thread(
                        credential.get_token, "https://ai.azure.com/.default"
                    )
                    headers["Authorization"] = f"Bearer {token.token}"
                async with httpx.AsyncClient(timeout=55, transport=agent_transport) as client:
                    result = await client.post(
                        url,
                        params={"api-version": "v1"},
                        headers=headers,
                        json={
                            "input": value.message,
                            "stream": False,
                            "store": False,
                            "metadata": {"request_id": str(value.request_id)},
                        },
                    )
                    result.raise_for_status()
                    payload = result.json()
            if payload.get("status") == "failed" or payload.get("error"):
                raise ApiError(
                    502, "agent_failed", "The event assistant could not complete the request."
                )
            text = "".join(
                content["text"]
                for item in payload.get("output", [])
                if item.get("type") == "message"
                for content in item.get("content", [])
                if content.get("type") == "output_text"
            )
            answer = AssistantAnswer.model_validate(
                {**json.loads(text), "request_id": str(value.request_id)}
            )
            sources = {source["id"]: source for source in agenda_sources()["sources"]}
            if (
                answer.refused
                or not answer.citations
                or any(citation.source_id not in sources for citation in answer.citations)
            ):
                return AssistantAnswer(
                    answer=REFUSAL, citations=[], refused=True, request_id=str(value.request_id)
                )
            for citation in answer.citations:
                citation.title = sources[citation.source_id]["title"]
            return answer
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ApiError(
                504, "agent_timeout", "The assistant timed out. Please try again."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Hosted agent returned HTTP %s", exc.response.status_code)
            raise ApiError(
                502, "agent_unavailable", "The hosted assistant is unavailable."
            ) from exc
        except AzureError as exc:
            logger.error("Hosted agent authentication failed: %s", type(exc).__name__)
            raise ApiError(
                503, "agent_authentication_failed", "The hosted assistant could not authenticate."
            ) from exc
        except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
            logger.error("Hosted agent response failed: %s", type(exc).__name__)
            raise ApiError(
                502, "invalid_agent_response", "The assistant returned an invalid response."
            ) from exc

    app.mount("/", mcp_app)
    return app
