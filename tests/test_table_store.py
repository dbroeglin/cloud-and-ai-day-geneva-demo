from unittest.mock import Mock
from uuid import uuid4

import pytest
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode
from event_companion.storage import TableStore


class Entity(dict):
    metadata = {"etag": 'W/"version-1"'}


def entity(key):
    return Entity(
        PartitionKey="demo:session:one",
        RowKey=f"q:2026-09-21T10:00:00Z:{key}",
        id=key,
        session_id="one",
        text="How does this work?",
        votes=0,
        created_at="2026-09-21T10:00:00Z",
        status="approved",
    )


def test_table_question_and_idempotency_index_are_one_atomic_transaction():
    client = Mock(spec=TableClient)
    store = TableStore(client, "demo")
    key = str(uuid4())
    result = store.add_question("one", key, "Question")
    operations = client.submit_transaction.call_args.args[0]
    assert len(operations) == 2
    index, question = operations
    assert index[0] == question[0] == "create"
    assert index[1]["PartitionKey"] == question[1]["PartitionKey"]
    assert index[1]["question_key"] == question[1]["RowKey"]
    assert question[1]["status"] == "pending"
    assert result.id == key


def test_table_vote_retries_etag_conflict_without_nonatomic_increments():
    client = Mock(spec=TableClient)
    key, voter = str(uuid4()), str(uuid4())
    question = entity(key)

    def get(_partition, row):
        if row.startswith("i:"):
            return {"question_key": question["RowKey"]}
        if row.startswith("v:"):
            raise ResourceNotFoundError()
        return question

    client.get_entity.side_effect = get
    conflict = HttpResponseError("etag conflict")
    conflict.status_code = 412
    client.submit_transaction.side_effect = [conflict, None]
    result = TableStore(client, "demo").vote("one", key, voter)
    assert result.votes == 1
    assert client.submit_transaction.call_count == 2
    operations = client.submit_transaction.call_args.args[0]
    assert operations[0][0] == "create"
    assert operations[0][1]["RowKey"] == f"v:{key}:{voter}"
    assert operations[1][0] == "update"
    assert operations[1][2] == {
        "mode": UpdateMode.MERGE,
        "etag": 'W/"version-1"',
        "match_condition": MatchConditions.IfNotModified,
    }


def test_table_duplicate_vote_does_not_increment_again():
    client = Mock(spec=TableClient)
    key = str(uuid4())
    question = entity(key)
    question["votes"] = 7
    client.get_entity.side_effect = [
        {"question_key": question["RowKey"]},
        question,
        {},
        {"question_key": question["RowKey"]},
        question,
    ]
    result = TableStore(client, "demo").vote("one", key, str(uuid4()))
    assert result.votes == 7
    client.submit_transaction.assert_not_called()


def test_table_storage_failure_is_not_retried_as_a_conflict():
    client = Mock(spec=TableClient)
    failure = HttpResponseError("service down")
    failure.status_code = 503
    client.submit_transaction.side_effect = failure
    with pytest.raises(HttpResponseError):
        TableStore(client, "demo").add_question("one", str(uuid4()), "Question")
    assert client.submit_transaction.call_count == 1
