from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from event_companion.models import ApiError
from event_companion.storage import SQLiteStore


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(str(tmp_path / "events.sqlite3"), "test-event")


def test_question_is_idempotent_and_durable(store):
    key = str(uuid4())
    first = store.add_question("session", key, "How do tools work?")
    assert store.add_question("session", key, first.text) == first
    reopened = SQLiteStore(store.path, store.namespace)
    assert reopened.questions("session", None).items == [first]
    with pytest.raises(ApiError, match="different text") as failure:
        store.add_question("session", key, "Different text")
    assert failure.value.status == 409


def test_concurrent_duplicate_votes_are_counted_once(store):
    question = store.add_question("session", str(uuid4()), "A concurrent question")
    voters = [str(uuid4()) for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda voter: store.vote("session", question.id, voter), voters * 3))
    assert store.questions("session", None).items[0].votes == 12


def test_question_pages_are_ordered_and_isolated(store):
    for index in range(65):
        store.add_question("session", str(uuid4()), f"Question {index:02d}")
    first = store.questions("session", None)
    second = store.questions("session", first.next_cursor)
    assert len(first.items) == 50
    assert len(second.items) == 15
    assert second.next_cursor is None
    assert [q.text for q in first.items + second.items] == [f"Question {i:02d}" for i in range(65)]
    assert store.questions("another-session", None).items == []
    other = SQLiteStore(store.path, "preview")
    assert other.questions("session", None).items == []


def test_suggestion_idempotency_and_private_partition(store):
    key = str(uuid4())
    first = store.suggest(key, "Better rooms", "A map would help.")
    assert store.suggest(key, "Better rooms", "A map would help.") == first
    assert store.questions("session", None).items == []
    with pytest.raises(ApiError):
        store.suggest(key, "Changed title", "A map would help.")


def test_bad_cursor_and_missing_question_fail_explicitly(store):
    for cursor in ("!", "W10=", "e30="):
        with pytest.raises(ApiError):
            store.questions("session", cursor)
    with pytest.raises(ApiError) as failure:
        store.vote("missing", str(uuid4()), str(uuid4()))
    assert failure.value.status == 404
