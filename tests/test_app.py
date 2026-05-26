from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from core.synapse.ghost import GhostEngine
from core.synapse.protocol import SynapseProtocol
from core.synapse.runtime import MemoryChunk, MemoryIndex, RuntimeArchive
from signal_chamber.server.app import create_app
from signal_chamber.server.routes import _build_retrieval_query
from signal_chamber.server.settings import Settings


class EmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class EmbeddingResponse:
    def __init__(self, embedding: list[float]) -> None:
        self.data = [EmbeddingItem(embedding)]


class FakeEmbeddings:
    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return EmbeddingResponse([1.0, 0.0])


class ResponseText:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class FakeResponses:
    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) % 2 == 1:
            return ResponseText("ghost reply")

        return ResponseText("updated summary")


class FakeOpenAI:
    def __init__(self) -> None:
        self.embedding_calls: list[dict] = []
        self.response_calls: list[dict] = []
        self.embeddings = FakeEmbeddings(self.embedding_calls)
        self.responses = FakeResponses(self.response_calls)


def basic_auth_header(username: str = "docs", password: str = "secret") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def archive() -> RuntimeArchive:
    return RuntimeArchive(
        runtime_prompt="runtime prompt",
        memory_index=MemoryIndex(
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
                )
            ],
        ),
    )


def settings(**overrides) -> Settings:
    protocol_fields = set(SynapseProtocol.__dataclass_fields__)
    protocol_overrides = {
        key: overrides.pop(key)
        for key in list(overrides)
        if key in protocol_fields
    }
    defaults = {
        "environment": "production",
        "allowed_origins": ("https://ghost.example",),
        "enforce_origin": True,
        "docs_username": "docs",
        "docs_password": "secret",
        "docs_credentials_configured": True,
        "openai_api_key_configured": True,
        "awakening_rate_limit_per_minute": 10,
        "chat_rate_limit_per_minute": 10,
        "max_concurrent_chats": 2,
    }
    defaults["protocol"] = SynapseProtocol(**protocol_overrides)
    defaults.update(overrides)
    return Settings(**defaults)


def client(fake_openai: FakeOpenAI | None = None, **setting_overrides) -> TestClient:
    app = create_app(
        settings=settings(**setting_overrides),
        openai_client=fake_openai or FakeOpenAI(),
        archive=archive(),
    )
    return TestClient(app)


def test_health_reports_loaded_archive() -> None:
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json()["runtime_loaded"] is True
    assert response.json()["chunk_count"] == 1


def test_retrieval_query_uses_message_without_summary() -> None:
    query = _build_retrieval_query("Tell me about Alpha", "")

    assert query == "Tell me about Alpha"


def test_retrieval_query_anchors_follow_up_to_summary() -> None:
    query = _build_retrieval_query(
        "Say that more plainly.",
        "The user is discussing retrieval drift in vague follow-up questions.",
    )

    assert "retrieval drift" in query
    assert "vague follow-up questions" in query
    assert "Say that more plainly." in query


def test_docs_and_schema_are_basic_auth_protected() -> None:
    api = client()

    assert api.get("/docs").status_code == 401
    assert api.get("/redoc").status_code == 404
    assert api.get("/openapi.json").status_code == 401

    schema_response = api.get("/openapi.json", headers=basic_auth_header())

    assert schema_response.status_code == 200
    paths = schema_response.json()["paths"]
    assert "/v1/awakening" in paths
    assert "/v1/chat" in paths
    assert "/v1/introspection" not in paths


def test_awakening_requires_allowed_origin_and_checks_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    assert api.post("/v1/awakening").status_code == 403

    response = api.post(
        "/v1/awakening",
        headers={"Origin": "https://ghost.example"},
    )

    assert response.status_code == 200
    assert response.json()["can_awaken"] is True
    assert response.json()["archive_loaded"] is True
    assert response.json()["openai_ready"] is True
    assert len(fake_openai.embedding_calls) == 1
    assert len(fake_openai.response_calls) == 1
    assert fake_openai.response_calls[0]["store"] is False
    assert fake_openai.response_calls[0]["max_output_tokens"] == 64


def test_awakening_reports_unconfigured_openai_before_probe() -> None:
    app = create_app(
        settings=settings(openai_api_key_configured=False),
        openai_client=None,
        archive=archive(),
    )
    api = TestClient(app)

    response = api.post(
        "/v1/awakening",
        headers={"Origin": "https://ghost.example"},
    )

    assert response.status_code == 200
    assert response.json()["can_awaken"] is False
    assert response.json()["reason"] == "openai_unconfigured"


def test_awakening_reports_missing_archive_before_openai() -> None:
    fake_openai = FakeOpenAI()
    app = create_app(
        settings=settings(
            runtime_prompt_path=Path("/tmp/missing-ghost-runtime.md"),
            memory_index_path=Path("/tmp/missing-memory-index.json"),
        ),
        openai_client=fake_openai,
    )
    api = TestClient(app)

    response = api.post(
        "/v1/awakening",
        headers={"Origin": "https://ghost.example"},
    )

    assert response.status_code == 200
    assert response.json()["can_awaken"] is False
    assert response.json()["reason"] == "archive_unavailable"
    assert fake_openai.embedding_calls == []
    assert fake_openai.response_calls == []


def test_awakening_rate_limit_blocks_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, awakening_rate_limit_per_minute=0)

    response = api.post(
        "/v1/awakening",
        headers={"Origin": "https://ghost.example"},
    )

    assert response.status_code == 429
    assert fake_openai.embedding_calls == []
    assert fake_openai.response_calls == []


def test_chat_returns_reply_updated_summary_and_retrieved_fragments() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Tell me about Alpha", "session_summary": "old summary"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "ghost reply"
    assert body["session_summary"] == "updated summary"
    assert body["retrieved"][0]["id"] == "alpha"
    assert "budget" not in body
    assert "can_chat" not in body
    assert len(fake_openai.response_calls) == 2
    assert fake_openai.embedding_calls[0]["input"] == (
        "SESSION SUMMARY:\n"
        "old summary\n\n"
        "CURRENT USER MESSAGE:\n"
        "Tell me about Alpha"
    )
    assert "old summary" in fake_openai.response_calls[0]["input"]
    assert fake_openai.response_calls[0]["instructions"] == "runtime prompt"
    assert fake_openai.response_calls[0]["reasoning"] == {"effort": "medium"}
    assert fake_openai.response_calls[0]["max_output_tokens"] == 1500
    assert fake_openai.response_calls[1]["reasoning"] == {"effort": "low"}
    assert fake_openai.response_calls[1]["max_output_tokens"] == 600


def test_chat_uses_summary_for_vague_follow_up_retrieval() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={
            "message": "Say that more plainly.",
            "session_summary": (
                "The user is discussing memory retrieval drift when brief follow-ups "
                "lose the prior topic."
            ),
        },
    )

    assert response.status_code == 200
    embedding_input = fake_openai.embedding_calls[0]["input"]
    assert "memory retrieval drift" in embedding_input
    assert "brief follow-ups" in embedding_input
    assert "Say that more plainly." in embedding_input


def test_chat_does_not_store_session_summary_server_side() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    first = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "First", "session_summary": "client summary"},
    )
    second = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Second"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "client summary" in fake_openai.response_calls[0]["input"]
    assert "No prior session summary." in fake_openai.response_calls[2]["input"]
    assert "updated summary" not in fake_openai.response_calls[2]["input"]


def test_chat_blocks_disallowed_origin_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://wrong.example"},
        json={"message": "Hello"},
    )

    assert response.status_code == 403
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_chat_rejects_invalid_input_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, max_message_chars=5)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "too long"},
    )

    assert response.status_code == 400
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_chat_rejects_messages_over_default_limit_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "x" * 101},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Message exceeds 100 characters."
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_chat_rate_limit_blocks_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, chat_rate_limit_per_minute=1)

    first = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "First"},
    )
    second = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Second"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert len(fake_openai.embedding_calls) == 1
    assert len(fake_openai.response_calls) == 2


def test_concurrency_limit_blocks_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, max_concurrent_chats=0)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Hello"},
    )

    assert response.status_code == 429
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_ghost_input_includes_context_use_rules() -> None:
    ghost = GhostEngine(SynapseProtocol(), archive(), FakeOpenAI())

    ghost_input = ghost._build_ghost_input(
        "Say that more plainly.",
        "The user is discussing contextual retrieval for vague follow-ups.",
        "Fragment about smart contracts.",
    )

    assert "CONTEXT USE RULES:" in ghost_input
    assert "Use the session summary as the continuity anchor" in ghost_input
    assert "optional evidence" in ghost_input
    assert "Do not introduce a retrieved fragment's topic" in ghost_input


def test_summary_instructions_preserve_follow_up_context() -> None:
    ghost = GhostEngine(SynapseProtocol(), archive(), FakeOpenAI())

    instructions = ghost._summary_instructions()

    assert "Preserve the current topic" in instructions
    assert "brief follow-ups understandable" in instructions
