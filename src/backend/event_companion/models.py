from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestionInput(InputModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]
    idempotency_key: UUID


class SuggestionInput(InputModel):
    title: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    idempotency_key: UUID


class AssistantInput(InputModel):
    message: Annotated[str, Field(min_length=1, max_length=1000)]
    request_id: UUID


class Question(BaseModel):
    id: str
    session_id: str
    text: str
    votes: int
    created_at: datetime


class QuestionPage(BaseModel):
    items: list[Question]
    next_cursor: str | None


class ModerationQuestion(Question):
    status: Literal["pending", "approved"]


class ModerationQuestionPage(BaseModel):
    items: list[ModerationQuestion]
    next_cursor: str | None


class Receipt(BaseModel):
    id: str
    created_at: datetime


class Citation(BaseModel):
    source_id: str
    title: str


class AssistantAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Annotated[str, Field(min_length=1, max_length=8000)]
    citations: Annotated[list[Citation], Field(max_length=20)]
    refused: bool
    request_id: str


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
