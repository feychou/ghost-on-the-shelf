from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from core.synapse.runtime import MemoryChunk, MemoryIndex


CONTEXT_QUERY_WEIGHT = 0.35
VAGUE_CURRENT_QUERY_WEIGHT = 0.35
VAGUE_CONTEXT_QUERY_WEIGHT = 0.9

VAGUE_FOLLOW_UPS = {
    "say that more plainly",
    "tell me more",
    "expand on that",
    "can you expand",
    "what about that",
    "what about it",
    "how so",
    "why",
    "go on",
    "continue",
}


@dataclass(frozen=True)
class RetrievedFragment:
    id: str
    source: str
    module: str
    title: str
    text: str
    score: float


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


class MemoryRetriever:
    def __init__(self, client: Any, memory_index: MemoryIndex) -> None:
        self.client = client
        self.memory_index = memory_index

    def embed_text(self, text: str) -> np.ndarray:
        kwargs: dict[str, Any] = {
            "model": self.memory_index.embedding_model,
            "input": text,
        }

        if self.memory_index.embedding_dimensions:
            kwargs["dimensions"] = self.memory_index.embedding_dimensions

        response = self.client.embeddings.create(**kwargs)
        return np.array(response.data[0].embedding, dtype=np.float32)

    def retrieve(self, question: str, k: int) -> list[RetrievedFragment]:
        if not self.memory_index.chunks:
            return []

        question_embedding = self.embed_text(question)
        scored_chunks = [
            self._score_chunk(question_embedding, chunk)
            for chunk in self.memory_index.chunks
        ]

        return sorted(scored_chunks, key=lambda item: item.score, reverse=True)[:k]

    def retrieve_with_context(
        self,
        message: str,
        session_summary: str,
        k: int,
    ) -> list[RetrievedFragment]:
        primary_weight = VAGUE_CURRENT_QUERY_WEIGHT if is_vague_follow_up(message) else 1.0
        primary_matches = self.retrieve(message, k=k)

        if not session_summary.strip():
            return primary_matches

        context_weight = (
            VAGUE_CONTEXT_QUERY_WEIGHT
            if is_vague_follow_up(message)
            else CONTEXT_QUERY_WEIGHT
        )
        contextual_query = build_contextual_retrieval_query(message, session_summary)
        contextual_matches = self.retrieve(contextual_query, k=k)

        return merge_retrieved_fragments(
            primary_matches,
            contextual_matches,
            k=k,
            primary_weight=primary_weight,
            context_weight=context_weight,
        )

    def _score_chunk(self, question_embedding: np.ndarray, chunk: MemoryChunk) -> RetrievedFragment:
        chunk_embedding = np.array(chunk.embedding, dtype=np.float32)
        score = cosine_similarity(question_embedding, chunk_embedding)

        return RetrievedFragment(
            id=chunk.id,
            source=chunk.source,
            module=chunk.module,
            title=chunk.title,
            text=chunk.text,
            score=score,
        )


def build_contextual_retrieval_query(message: str, session_summary: str) -> str:
    if not session_summary:
        return message

    return f"""SESSION SUMMARY:
{session_summary}

CURRENT USER MESSAGE:
{message}"""


def is_vague_follow_up(message: str) -> bool:
    normalized = _normalize_query_text(message)

    if normalized in VAGUE_FOLLOW_UPS:
        return True

    return any(normalized.startswith(f"{phrase} ") for phrase in VAGUE_FOLLOW_UPS)


def merge_retrieved_fragments(
    primary_matches: list[RetrievedFragment],
    contextual_matches: list[RetrievedFragment],
    *,
    k: int,
    primary_weight: float,
    context_weight: float,
) -> list[RetrievedFragment]:
    candidates: dict[str, RetrievedFragment] = {}

    for matches, weight in (
        (primary_matches, primary_weight),
        (contextual_matches, context_weight),
    ):
        for match in matches:
            weighted = replace(match, score=match.score * weight)
            existing = candidates.get(match.id)

            if existing is None or weighted.score > existing.score:
                candidates[match.id] = weighted

    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:k]


def _normalize_query_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return normalized.strip()


def format_memory_fragments(matches: list[RetrievedFragment]) -> str:
    if not matches:
        return "No memory fragments retrieved."

    formatted = []

    for index, match in enumerate(matches, start=1):
        formatted.append(
            f"""## Fragment {index}
Source: {match.source}
Module: {match.module}
Title: {match.title}
Score: {match.score:.3f}

{match.text}"""
        )

    return "\n\n---\n\n".join(formatted)
