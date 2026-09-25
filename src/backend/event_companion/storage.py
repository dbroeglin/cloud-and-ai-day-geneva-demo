import base64
import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient, TableEntity, UpdateMode

from .models import (
    ApiError,
    ModerationQuestion,
    ModerationQuestionPage,
    Question,
    QuestionPage,
    Receipt,
)


class Store(Protocol):
    def questions(self, session_id: str, cursor: str | None) -> QuestionPage: ...
    def add_question(self, session_id: str, key: str, text: str) -> Question: ...
    def vote(self, session_id: str, question_id: str, voter_id: str) -> Question: ...
    def pending_questions(self, session_id: str, cursor: str | None) -> ModerationQuestionPage: ...
    def approve_question(self, session_id: str, question_id: str) -> ModerationQuestion: ...
    def suggest(self, key: str, title: str, description: str) -> Receipt: ...
    def close(self) -> None: ...


def conflict() -> ApiError:
    return ApiError(
        409, "idempotency_conflict", "This request ID was already used for different text."
    )


def missing_question() -> ApiError:
    return ApiError(404, "question_not_found", "That question does not exist in this session.")


def encode_cursor(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def decode_cursor(cursor: str | None) -> dict | None:
    if cursor is None:
        return None
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(400, "invalid_cursor", "The page cursor is invalid.") from exc
    if (
        not isinstance(value, dict)
        or not value
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items())
    ):
        raise ApiError(400, "invalid_cursor", "The page cursor is invalid.")
    return value


class TableStore:
    def __init__(self, client: TableClient, namespace: str):
        self.client = client
        self.namespace = namespace

    def partition(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}"

    @staticmethod
    def question(entity: dict) -> Question:
        return Question(**{k: entity[k] for k in Question.model_fields})

    @staticmethod
    def moderation_question(entity: dict) -> ModerationQuestion:
        return ModerationQuestion(
            **{k: entity[k] for k in Question.model_fields}, status=entity.get("status", "pending")
        )

    def questions(self, session_id: str, cursor: str | None) -> QuestionPage:
        pages = self.client.query_entities(
            query_filter=(
                "PartitionKey eq @partition and RowKey ge 'q:' and RowKey lt 'q;' "
                "and status eq 'approved'"
            ),
            parameters={"partition": self.partition(session_id)},
            results_per_page=50,
        ).by_page(continuation_token=decode_cursor(cursor))
        page = next(pages, [])
        items = [self.question(entity) for entity in page]
        token = pages.continuation_token
        return QuestionPage(items=items, next_cursor=encode_cursor(token) if token else None)

    def pending_questions(self, session_id: str, cursor: str | None) -> ModerationQuestionPage:
        pages = self.client.query_entities(
            query_filter="PartitionKey eq @partition and RowKey ge 'q:' and RowKey lt 'q;'",
            parameters={"partition": self.partition(session_id)},
            results_per_page=1,
        ).by_page(continuation_token=decode_cursor(cursor))
        items = []
        token = None
        for page in pages:
            items.extend(
                self.moderation_question(entity)
                for entity in page
                if entity.get("status", "pending") == "pending"
            )
            token = pages.continuation_token
            if len(items) >= 50:
                items = items[:50]
                break
        return ModerationQuestionPage(
            items=items,
            next_cursor=encode_cursor(token) if token else None,
        )

    def _get_question(self, session_id: str, question_id: str) -> TableEntity:
        partition = self.partition(session_id)
        try:
            index = self.client.get_entity(partition, f"i:{question_id}")
            return self.client.get_entity(partition, index["question_key"])
        except ResourceNotFoundError as exc:
            raise missing_question() from exc

    def add_question(self, session_id: str, key: str, text: str) -> Question:
        partition = self.partition(session_id)
        now = datetime.now(UTC)
        question_key = f"q:{now.isoformat()}:{key}"
        entity = {
            "PartitionKey": partition,
            "RowKey": question_key,
            "id": key,
            "session_id": session_id,
            "text": text,
            "votes": 0,
            "created_at": now,
            "status": "pending",
        }
        index = {"PartitionKey": partition, "RowKey": f"i:{key}", "question_key": question_key}
        try:
            self.client.submit_transaction([("create", index), ("create", entity)])
            return self.question(entity)
        except HttpResponseError as exc:
            if exc.status_code != 409:
                raise
            existing = self._get_question(session_id, key)
            if existing["text"] != text:
                raise conflict() from exc
            return self.question(existing)

    def vote(self, session_id: str, question_id: str, voter_id: str) -> Question:
        partition = self.partition(session_id)
        vote_key = f"v:{question_id}:{voter_id}"
        for attempt in range(6):
            question = self._get_question(session_id, question_id)
            if question.get("status") != "approved":
                raise missing_question()
            try:
                self.client.get_entity(partition, vote_key)
            except ResourceNotFoundError:
                pass
            else:
                return self.question(self._get_question(session_id, question_id))
            updated = {**question, "votes": question["votes"] + 1}
            try:
                self.client.submit_transaction(
                    [
                        ("create", {"PartitionKey": partition, "RowKey": vote_key}),
                        (
                            "update",
                            updated,
                            {
                                "mode": UpdateMode.MERGE,
                                "etag": question.metadata["etag"],
                                "match_condition": MatchConditions.IfNotModified,
                            },
                        ),
                    ]
                )
                return self.question(updated)
            except HttpResponseError as exc:
                if exc.status_code not in (409, 412):
                    raise
                if attempt == 5:
                    raise ApiError(503, "vote_busy", "Voting is busy. Please retry.") from exc
                time.sleep(0.02 * (attempt + 1))
        raise AssertionError("unreachable vote retry state")

    def approve_question(self, session_id: str, question_id: str) -> ModerationQuestion:
        for attempt in range(6):
            question = self._get_question(session_id, question_id)
            if question.get("status") == "approved":
                return self.moderation_question(question)
            updated = {**question, "status": "approved"}
            status_update = {
                "PartitionKey": question["PartitionKey"],
                "RowKey": question["RowKey"],
                "status": "approved",
            }
            try:
                self.client.update_entity(
                    status_update,
                    mode=UpdateMode.MERGE,
                    etag=question.metadata["etag"],
                    match_condition=MatchConditions.IfNotModified,
                )
                return self.moderation_question(updated)
            except HttpResponseError as exc:
                if exc.status_code != 412 or attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))
        raise AssertionError("unreachable approval retry state")

    def suggest(self, key: str, title: str, description: str) -> Receipt:
        entity = {
            "PartitionKey": f"{self.namespace}:suggestions",
            "RowKey": key,
            "id": key,
            "title": title,
            "description": description,
            "created_at": datetime.now(UTC),
        }
        try:
            self.client.create_entity(entity)
        except ResourceExistsError as exc:
            existing = self.client.get_entity(entity["PartitionKey"], key)
            if existing["title"] != title or existing["description"] != description:
                raise conflict() from exc
            entity = existing
        return Receipt(id=key, created_at=entity["created_at"])

    def close(self) -> None:
        self.client.close()


class SQLiteStore:
    """Explicit durable local-development store; never an Azure fallback."""

    def __init__(self, path: str, namespace: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.namespace = namespace
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS questions (
                    namespace TEXT, session_id TEXT, id TEXT, text TEXT,
                    votes INTEGER NOT NULL DEFAULT 0, created_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    PRIMARY KEY(namespace, session_id, id)
                );
                CREATE TABLE IF NOT EXISTS votes (
                    namespace TEXT, session_id TEXT, question_id TEXT, voter_id TEXT,
                    PRIMARY KEY(namespace, session_id, question_id, voter_id)
                );
                CREATE TABLE IF NOT EXISTS suggestions (
                    namespace TEXT, id TEXT, title TEXT, description TEXT, created_at TEXT,
                    PRIMARY KEY(namespace, id)
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(questions)")}
            if "status" not in columns:
                db.execute(
                    "ALTER TABLE questions ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
                )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def questions(self, session_id: str, cursor: str | None) -> QuestionPage:
        token = decode_cursor(cursor)
        if token and set(token) != {"created_at", "id"}:
            raise ApiError(400, "invalid_cursor", "The page cursor is invalid.")
        after = (token["created_at"], token["id"]) if token else ("", "")
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM questions WHERE namespace=? AND session_id=?
                   AND status='approved'
                   AND (created_at,id) > (?,?) ORDER BY created_at,id LIMIT 51""",
                (self.namespace, session_id, *after),
            ).fetchall()
        selected = rows[:50]
        next_cursor = None
        if len(rows) > 50:
            next_cursor = encode_cursor({k: selected[-1][k] for k in ("created_at", "id")})
        return QuestionPage(
            items=[Question(**dict(row)) for row in selected], next_cursor=next_cursor
        )

    def pending_questions(self, session_id: str, cursor: str | None) -> ModerationQuestionPage:
        token = decode_cursor(cursor)
        if token and set(token) != {"created_at", "id"}:
            raise ApiError(400, "invalid_cursor", "The page cursor is invalid.")
        after = (token["created_at"], token["id"]) if token else ("", "")
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM questions WHERE namespace=? AND session_id=? AND status='pending'
                   AND (created_at,id) > (?,?) ORDER BY created_at,id LIMIT 51""",
                (self.namespace, session_id, *after),
            ).fetchall()
        selected = rows[:50]
        return ModerationQuestionPage(
            items=[ModerationQuestion(**dict(row)) for row in selected],
            next_cursor=encode_cursor({k: selected[-1][k] for k in ("created_at", "id")})
            if len(rows) > 50
            else None,
        )

    def add_question(self, session_id: str, key: str, text: str) -> Question:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM questions WHERE namespace=? AND session_id=? AND id=?",
                (self.namespace, session_id, key),
            ).fetchone()
            if row:
                if row["text"] != text:
                    raise conflict()
                return Question(**dict(row))
            created = datetime.now(UTC)
            db.execute(
                "INSERT INTO questions VALUES (?,?,?,?,?,?,?)",
                (self.namespace, session_id, key, text, 0, created.isoformat(), "pending"),
            )
            return Question(id=key, session_id=session_id, text=text, votes=0, created_at=created)

    def vote(self, session_id: str, question_id: str, voter_id: str) -> Question:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM questions WHERE namespace=? AND session_id=? AND id=?",
                (self.namespace, session_id, question_id),
            ).fetchone()
            if not row or row["status"] != "approved":
                raise missing_question()
            added = db.execute(
                "INSERT OR IGNORE INTO votes VALUES (?,?,?,?)",
                (self.namespace, session_id, question_id, voter_id),
            ).rowcount
            if added:
                db.execute(
                    """UPDATE questions SET votes=votes+1
                       WHERE namespace=? AND session_id=? AND id=?""",
                    (self.namespace, session_id, question_id),
                )
            return Question(**{**dict(row), "votes": row["votes"] + added})

    def approve_question(self, session_id: str, question_id: str) -> ModerationQuestion:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM questions WHERE namespace=? AND session_id=? AND id=?",
                (self.namespace, session_id, question_id),
            ).fetchone()
            if not row:
                raise missing_question()
            if row["status"] == "pending":
                db.execute(
                    "UPDATE questions SET status='approved' "
                    "WHERE namespace=? AND session_id=? AND id=?",
                    (self.namespace, session_id, question_id),
                )
            return ModerationQuestion(**{**dict(row), "status": "approved"})

    def suggest(self, key: str, title: str, description: str) -> Receipt:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM suggestions WHERE namespace=? AND id=?", (self.namespace, key)
            ).fetchone()
            if row:
                if row["title"] != title or row["description"] != description:
                    raise conflict()
                return Receipt(id=key, created_at=row["created_at"])
            created = datetime.now(UTC)
            db.execute(
                "INSERT INTO suggestions VALUES (?,?,?,?,?)",
                (self.namespace, key, title, description, created.isoformat()),
            )
            return Receipt(id=key, created_at=created)

    def close(self) -> None:
        pass
