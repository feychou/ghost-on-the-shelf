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
DEFAULT_ACCESS_TOKEN_MAX_AGE_SECONDS = 60 * 60


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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)

    if raw is None:
        return default

    value = raw.strip().lower()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    environment: str = "development"
    allowed_origins: tuple[str, ...] = LOCAL_ORIGINS
    enforce_origin: bool = False

    docs_username: str = ""
    docs_password: str = ""
    docs_credentials_configured: bool = False

    access_code: str = ""
    access_code_hash: str = ""
    access_token_secret: str = ""
    access_token_max_age_seconds: int = DEFAULT_ACCESS_TOKEN_MAX_AGE_SECONDS

    protocol: SynapseProtocol = field(default_factory=SynapseProtocol)

    openai_api_key_configured: bool = False
    chat_enabled: bool = True
    moderation_enabled: bool | None = None
    moderation_model: str = "omni-moderation-latest"
    access_rate_limit_per_minute: int = 5
    awakening_rate_limit_per_minute: int = 10
    chat_rate_limit_per_minute: int = 6
    chat_session_rate_limit_per_minute: int = 6
    max_concurrent_chats: int = 2

    runtime_prompt_path: Path = ROOT / "core" / "shelf" / "ghost_runtime.md"
    memory_index_path: Path = ROOT / "core" / "shelf" / "indexes" / "memory_index.json"

    def __post_init__(self) -> None:
        if self.moderation_enabled is None:
            object.__setattr__(self, "moderation_enabled", self.production)

    @property
    def production(self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def access_required(self) -> bool:
        return self.production or bool(self.access_code or self.access_code_hash)

    @property
    def access_configured(self) -> bool:
        return bool((self.access_code or self.access_code_hash) and self.access_token_secret)

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

        docs_username = os.getenv("GHOST_DOCS_USERNAME", "").strip()
        docs_password = os.getenv("GHOST_DOCS_PASSWORD", "").strip()
        docs_credentials_configured = bool(docs_username and docs_password)
        access_code = os.getenv("GHOST_ACCESS_CODE", "").strip()
        access_code_hash = os.getenv("GHOST_ACCESS_CODE_HASH", "").strip().lower()
        access_token_secret = os.getenv("GHOST_ACCESS_TOKEN_SECRET", "")
        access_token_max_age_seconds = _int_env(
            "GHOST_ACCESS_TOKEN_MAX_AGE_SECONDS",
            DEFAULT_ACCESS_TOKEN_MAX_AGE_SECONDS,
        )

        return cls(
            environment=environment,
            allowed_origins=allowed_origins,
            enforce_origin=production,
            docs_username=docs_username,
            docs_password=docs_password,
            docs_credentials_configured=docs_credentials_configured,
            access_code=access_code,
            access_code_hash=access_code_hash,
            access_token_secret=access_token_secret,
            access_token_max_age_seconds=access_token_max_age_seconds,
            protocol=protocol,
            openai_api_key_configured=bool(os.getenv("OPENAI_API_KEY")),
            chat_enabled=_bool_env("GHOST_CHAT_ENABLED", True),
            moderation_enabled=_bool_env("GHOST_MODERATION_ENABLED", production),
            moderation_model=os.getenv("GHOST_MODERATION_MODEL", "omni-moderation-latest").strip()
            or "omni-moderation-latest",
            access_rate_limit_per_minute=_int_env("GHOST_ACCESS_RATE_LIMIT_PER_MINUTE", 5),
            awakening_rate_limit_per_minute=_int_env("GHOST_AWAKENING_RATE_LIMIT_PER_MINUTE", 10),
            chat_rate_limit_per_minute=_int_env("GHOST_CHAT_RATE_LIMIT_PER_MINUTE", 6),
            chat_session_rate_limit_per_minute=_int_env("GHOST_CHAT_SESSION_RATE_LIMIT_PER_MINUTE", 6),
            max_concurrent_chats=_int_env("GHOST_MAX_CONCURRENT_CHATS", 2),
        )
