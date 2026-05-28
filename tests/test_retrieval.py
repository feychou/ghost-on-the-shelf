from __future__ import annotations

from core.synapse.retrieval import MemoryRetriever, build_contextual_retrieval_query
from core.synapse.runtime import MemoryChunk, MemoryIndex


class EmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class EmbeddingResponse:
    def __init__(self, embedding: list[float]) -> None:
        self.data = [EmbeddingItem(embedding)]


class FakeEmbeddings:
    def __init__(self, vectors_by_input: dict[str, list[float]] | None = None) -> None:
        self.calls: list[dict] = []
        self.vectors_by_input = vectors_by_input or {}

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return EmbeddingResponse(self.vectors_by_input.get(kwargs["input"], [1.0, 0.0]))


class FakeClient:
    def __init__(self, vectors_by_input: dict[str, list[float]] | None = None) -> None:
        self.embeddings = FakeEmbeddings(vectors_by_input)


def memory_index() -> MemoryIndex:
    return MemoryIndex(
        embedding_model="test-embedding",
        embedding_dimensions=2,
        chunks=[
            MemoryChunk(
                id="alpha",
                source="alpha.md",
                module="field",
                title="Alpha",
                text="Alpha text",
                embedding=[1.0, 0.0],
            ),
            MemoryChunk(
                id="beta",
                source="beta.md",
                module="field",
                title="Beta",
                text="Beta text",
                embedding=[0.0, 1.0],
            ),
        ],
    )


def test_retriever_returns_highest_cosine_match_first() -> None:
    matches = MemoryRetriever(FakeClient(), memory_index()).retrieve("alpha", k=2)

    assert [match.id for match in matches] == ["alpha", "beta"]
    assert matches[0].score == 1.0


def test_contextual_retrieval_keeps_current_message_first_for_clear_queries() -> None:
    message = "Tell me about Beta"
    session_summary = "The user was discussing Alpha."
    vectors_by_input = {
        message: [0.0, 1.0],
        build_contextual_retrieval_query(message, session_summary): [1.0, 0.0],
    }
    client = FakeClient(vectors_by_input)

    matches = MemoryRetriever(client, memory_index()).retrieve_with_context(
        message,
        session_summary,
        k=1,
    )

    assert [match.id for match in matches] == ["beta"]
    assert [call["input"] for call in client.embeddings.calls] == [
        message,
        build_contextual_retrieval_query(message, session_summary),
    ]


def test_contextual_retrieval_uses_summary_for_vague_follow_ups() -> None:
    message = "Say that more plainly."
    session_summary = "The user was discussing Alpha."
    vectors_by_input = {
        message: [0.0, 1.0],
        build_contextual_retrieval_query(message, session_summary): [1.0, 0.0],
    }

    matches = MemoryRetriever(FakeClient(vectors_by_input), memory_index()).retrieve_with_context(
        message,
        session_summary,
        k=1,
    )

    assert [match.id for match in matches] == ["alpha"]
