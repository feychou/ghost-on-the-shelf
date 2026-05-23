from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from core.synapse.protocol import SynapseProtocol


ROOT = Path(__file__).resolve().parents[2]

LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()

    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    environment: str = "development"
    allowed_origins: tuple[str, ...] = LOCAL_ORIGINS
    enforce_origin: bool = False

    docs_username: str = "ghost"
    docs_password: str = "shelf"
    docs_credentials_configured: bool = True

    protocol: SynapseProtocol = field(default_factory=SynapseProtocol)

    openai_api_key_configured: bool = False
    awakening_rate_limit_per_minute: int = 10
    chat_rate_limit_per_minute: int = 6
    max_concurrent_chats: int = 2

    runtime_prompt_path: Path = ROOT / "core" / "shelf" / "ghost_runtime.md"
    memory_index_path: Path = ROOT / "core" / "shelf" / "indexes" / "memory_index.json"

    @property
    def production(self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def chat_model(self) -> str:
        return self.protocol.chat_model

    @property
    def summary_model(self) -> str:
        return self.protocol.summary_model

    @property
    def reasoning_effort(self) -> str:
        return self.protocol.reasoning_effort

    @property
    def default_k(self) -> int:
        return self.protocol.default_k

    @property
    def max_k(self) -> int:
        return self.protocol.max_k

    @property
    def max_message_chars(self) -> int:
        return self.protocol.max_message_chars

    @property
    def max_summary_chars(self) -> int:
        return self.protocol.max_summary_chars

    @property
    def max_output_tokens(self) -> int:
        return self.protocol.max_output_tokens

    @property
    def summary_max_output_tokens(self) -> int:
        return self.protocol.summary_max_output_tokens

    @property
    def awakening_probe_output_tokens(self) -> int:
        return self.protocol.awakening_probe_output_tokens

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(ROOT / ".env", override=False)
        protocol = SynapseProtocol.from_env(ROOT)

        environment = os.getenv("GHOST_ENV", "development").strip().lower()
        production = environment in {"production", "prod"}
        env_origins = _csv(os.getenv("GHOST_ALLOWED_ORIGINS"))
        allowed_origins = env_origins if env_origins else (() if production else LOCAL_ORIGINS)

        docs_username = os.getenv("GHOST_DOCS_USERNAME", "ghost")
        docs_password = os.getenv("GHOST_DOCS_PASSWORD", "shelf")
        docs_credentials_configured = not production or (
            bool(os.getenv("GHOST_DOCS_USERNAME")) and bool(os.getenv("GHOST_DOCS_PASSWORD"))
        )

        return cls(
            environment=environment,
            allowed_origins=allowed_origins,
            enforce_origin=production,
            docs_username=docs_username,
            docs_password=docs_password,
            docs_credentials_configured=docs_credentials_configured,
            protocol=protocol,
            openai_api_key_configured=bool(os.getenv("OPENAI_API_KEY")),
            awakening_rate_limit_per_minute=_int_env("GHOST_AWAKENING_RATE_LIMIT_PER_MINUTE", 10),
            chat_rate_limit_per_minute=_int_env("GHOST_CHAT_RATE_LIMIT_PER_MINUTE", 6),
            max_concurrent_chats=_int_env("GHOST_MAX_CONCURRENT_CHATS", 2),
        )
