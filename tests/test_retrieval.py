from __future__ import annotations

from core.synapse.retrieval import MemoryRetriever
from core.synapse.runtime import MemoryChunk, MemoryIndex


class EmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class EmbeddingResponse:
    def __init__(self, embedding: list[float]) -> None:
        self.data = [EmbeddingItem(embedding)]


class FakeEmbeddings:
    def create(self, **kwargs):
        return EmbeddingResponse([1.0, 0.0])


class FakeClient:
    embeddings = FakeEmbeddings()


def test_retriever_returns_highest_cosine_match_first() -> None:
    memory_index = MemoryIndex(
        embedding_model="test-embedding",
        embedding_dimensions=2,
        chunks=[
            MemoryChunk(
                id="beta",
                source="beta.md",
                module="field",
                title="Beta",
                text="Beta text",
                embedding=[0.0, 1.0],
            ),
            MemoryChunk(
                id="alpha",
                source="alpha.md",
                module="field",
                title="Alpha",
                text="Alpha text",
                embedding=[1.0, 0.0],
            ),
        ],
    )

    matches = MemoryRetriever(FakeClient(), memory_index).retrieve("alpha", k=2)

    assert [match.id for match in matches] == ["alpha", "beta"]
    assert matches[0].score == 1.0
