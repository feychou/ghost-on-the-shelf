from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetrievedFragmentModel(BaseModel):
    id: str
    title: str
    source: str
    score: float


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What do you remember about Chibo?",
                    "session_summary": "The user is asking about Fey's learning tools.",
                    "k": 3,
                }
            ]
        }
    )

    message: str = Field(description="The user's current message.")
    session_summary: str | None = Field(
        default=None,
        description=(
            "Client-held rolling summary for continuity and contextual memory retrieval "
            "in this chat thread."
        ),
    )
    k: int | None = Field(
        default=None,
        ge=1,
        description="Optional number of memory fragments to retrieve.",
    )


class ChatResponse(BaseModel):
    reply: str
    session_summary: str
    retrieved: list[RetrievedFragmentModel]


class AwakeningResponse(BaseModel):
    can_awaken: bool
    reason: Literal[
        "archive_unavailable",
        "openai_unconfigured",
        "openai_unavailable",
    ] | None = None
    message: str
    archive_loaded: bool
    openai_ready: bool


class HealthResponse(BaseModel):
    status: str
    runtime_loaded: bool
    memory_index_loaded: bool
    archive_error: str | None = None
    chunk_count: int = 0
