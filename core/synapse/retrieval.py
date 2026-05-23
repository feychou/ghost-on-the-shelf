from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from core.synapse.runtime import MemoryChunk, MemoryIndex


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
