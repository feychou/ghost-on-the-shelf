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


ORIGIN = "https://ghost.example"
ACCESS_CODE = "open sesame"


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


class ModerationResult:
    def __init__(self, flagged: bool) -> None:
        self.flagged = flagged


class ModerationResponse:
    def __init__(self, flagged: bool) -> None:
        self.results = [ModerationResult(flagged)]


class FakeModerations:
    def __init__(self, calls: list[dict], flagged: bool) -> None:
        self.calls = calls
        self.flagged = flagged

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return ModerationResponse(self.flagged)


class FakeOpenAI:
    def __init__(self, *, moderation_flagged: bool = False) -> None:
        self.embedding_calls: list[dict] = []
        self.response_calls: list[dict] = []
        self.moderation_calls: list[dict] = []
        self.embeddings = FakeEmbeddings(self.embedding_calls)
        self.responses = FakeResponses(self.response_calls)
        self.moderations = FakeModerations(self.moderation_calls, moderation_flagged)


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
        "access_code": ACCESS_CODE,
        "access_cookie_secret": "test-cookie-secret",
        "openai_api_key_configured": True,
        "moderation_enabled": True,
        "access_rate_limit_per_minute": 10,
        "awakening_rate_limit_per_minute": 10,
        "chat_rate_limit_per_minute": 10,
        "chat_session_rate_limit_per_minute": 10,
        "max_concurrent_chats": 2,
    }
    defaults["protocol"] = SynapseProtocol(**protocol_overrides)
    defaults.update(overrides)
    return Settings(**defaults)


def test_moderation_default_follows_environment() -> None:
    assert Settings(environment="production").moderation_enabled is True
    assert Settings(environment="development").moderation_enabled is False
    assert Settings(environment="production", moderation_enabled=False).moderation_enabled is False


def grant_access(api: TestClient) -> None:
    response = api.post(
        "/v1/access",
        headers={"Origin": ORIGIN},
        json={"code": ACCESS_CODE},
    )

    assert response.status_code == 200


def client(
    fake_openai: FakeOpenAI | None = None,
    *,
    auto_access: bool = True,
    **setting_overrides,
) -> TestClient:
    app = create_app(
        settings=settings(**setting_overrides),
        openai_client=fake_openai or FakeOpenAI(),
        archive=archive(),
    )
    api = TestClient(app, base_url="https://testserver")

    if auto_access:
        grant_access(api)

    return api


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
    api = client(auto_access=False)

    assert api.get("/docs").status_code == 401
    assert api.get("/redoc").status_code == 404
    assert api.get("/openapi.json").status_code == 401

    schema_response = api.get("/openapi.json", headers=basic_auth_header())

    assert schema_response.status_code == 200
    paths = schema_response.json()["paths"]
    assert "/v1/awakening" in paths
    assert "/v1/chat" in paths
    assert "/v1/introspection" not in paths


def test_health_and_docs_do_not_require_access_cookie() -> None:
    api = client(auto_access=False)

    assert api.get("/health").status_code == 200
    assert api.get("/docs").status_code == 401
    assert api.get("/openapi.json", headers=basic_auth_header()).status_code == 200


def test_chat_requires_access_cookie_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, auto_access=False)

    response = api.post(
        "/v1/chat",
        headers={"Origin": ORIGIN},
        json={"message": "Hello"},
    )

    assert response.status_code == 401
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_chat_rejects_invalid_access_cookie_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, auto_access=False)
    api.cookies.set("ghost_access", "invalid")

    response = api.post(
        "/v1/chat",
        headers={"Origin": ORIGIN},
        json={"message": "Hello"},
    )

    assert response.status_code == 401
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_chat_fails_closed_when_access_gate_is_not_configured() -> None:
    fake_openai = FakeOpenAI()
    api = client(
        fake_openai,
        auto_access=False,
        access_code="",
        access_cookie_secret="",
    )

    response = api.post(
        "/v1/chat",
        headers={"Origin": ORIGIN},
        json={"message": "Hello"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Access gate is not configured."
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_awakening_requires_access_cookie_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, auto_access=False)

    response = api.post("/v1/awakening", headers={"Origin": ORIGIN})

    assert response.status_code == 401
    assert fake_openai.response_calls == []
    assert fake_openai.embedding_calls == []


def test_access_accepts_valid_code_and_unlocks_chat() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, auto_access=False)

    access_response = api.post(
        "/v1/access",
        headers={"Origin": ORIGIN},
        json={"code": ACCESS_CODE},
    )
    chat_response = api.post(
        "/v1/chat",
        headers={"Origin": ORIGIN},
        json={"message": "Tell me about Alpha"},
    )

    assert access_response.status_code == 200
    assert access_response.json() == {"access_granted": True}
    assert "ghost_access" in access_response.cookies
    set_cookie = access_response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Max-Age=2592000" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" in set_cookie
    assert chat_response.status_code == 200
    assert len(fake_openai.embedding_calls) == 1
    assert len(fake_openai.response_calls) == 2


def test_access_rate_limit_blocks_unlock_attempts() -> None:
    api = client(auto_access=False, access_rate_limit_per_minute=1)

    first = api.post(
        "/v1/access",
        headers={"Origin": ORIGIN},
        json={"code": "wrong"},
    )
    second = api.post(
        "/v1/access",
        headers={"Origin": ORIGIN},
        json={"code": ACCESS_CODE},
    )

    assert first.status_code == 401
    assert second.status_code == 429
    assert "ghost_access" not in second.cookies


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
    api = TestClient(app, base_url="https://testserver")
    grant_access(api)

    response = api.post(
        "/v1/awakening",
        headers={"Origin": ORIGIN},
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
    api = TestClient(app, base_url="https://testserver")
    grant_access(api)

    response = api.post(
        "/v1/awakening",
        headers={"Origin": ORIGIN},
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
    assert fake_openai.moderation_calls == [
        {"model": "omni-moderation-latest", "input": "Tell me about Alpha"}
    ]
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
    safety_identifier = fake_openai.response_calls[0]["safety_identifier"]
    assert isinstance(safety_identifier, str)
    assert len(safety_identifier) >= 16
    assert fake_openai.response_calls[1]["safety_identifier"] == safety_identifier
    assert "safety_identifier" not in fake_openai.embedding_calls[0]


def test_chat_blocks_flagged_input_before_retrieval_answer_or_summary() -> None:
    fake_openai = FakeOpenAI(moderation_flagged=True)
    api = client(fake_openai)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Tell me about Alpha", "session_summary": "old summary"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "I can't help with that request, but I can stay with safer questions about the archive.",
        "session_summary": "old summary",
        "retrieved": [],
    }
    assert fake_openai.moderation_calls == [
        {"model": "omni-moderation-latest", "input": "Tell me about Alpha"}
    ]
    assert fake_openai.embedding_calls == []
    assert fake_openai.response_calls == []


def test_chat_skips_moderation_when_disabled_and_continues_normally() -> None:
    fake_openai = FakeOpenAI(moderation_flagged=True)
    api = client(fake_openai, moderation_enabled=False)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Tell me about Alpha"},
    )

    assert response.status_code == 200
    assert fake_openai.moderation_calls == []
    assert len(fake_openai.embedding_calls) == 1
    assert len(fake_openai.response_calls) == 2


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


def test_chat_disabled_returns_503_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(fake_openai, chat_enabled=False)

    response = api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Hello"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Chat is currently disabled."
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


def test_chat_session_rate_limit_blocks_before_openai() -> None:
    fake_openai = FakeOpenAI()
    api = client(
        fake_openai,
        chat_rate_limit_per_minute=10,
        chat_session_rate_limit_per_minute=1,
    )

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


def test_different_access_sessions_are_metered_separately() -> None:
    fake_openai = FakeOpenAI()
    app = create_app(
        settings=settings(
            chat_rate_limit_per_minute=10,
            chat_session_rate_limit_per_minute=1,
        ),
        openai_client=fake_openai,
        archive=archive(),
    )
    first_api = TestClient(app, base_url="https://testserver")
    second_api = TestClient(app, base_url="https://testserver")
    grant_access(first_api)
    grant_access(second_api)

    first = first_api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "First"},
    )
    second = second_api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Second"},
    )
    first_again = first_api.post(
        "/v1/chat",
        headers={"Origin": "https://ghost.example"},
        json={"message": "Again"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_again.status_code == 429
    assert len(fake_openai.embedding_calls) == 2
    assert len(fake_openai.response_calls) == 4


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
