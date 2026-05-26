from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ANSWER_WORD_LIMIT = 150
DEFAULT_SUMMARY_WORD_LIMIT = 120
DEFAULT_MAX_OUTPUT_TOKENS = 1500
DEFAULT_SUMMARY_MAX_OUTPUT_TOKENS = 600
DEFAULT_AWAKENING_PROBE_OUTPUT_TOKENS = 64
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_SUMMARY_REASONING_EFFORT = "low"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class SynapseProtocol:
    chat_model: str = "gpt-5-mini"
    summary_model: str = "gpt-5-mini"
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    summary_reasoning_effort: str = DEFAULT_SUMMARY_REASONING_EFFORT

    default_k: int = 3
    max_k: int = 8

    max_message_chars: int = 100
    max_summary_chars: int = 3000

    answer_word_limit: int = DEFAULT_ANSWER_WORD_LIMIT
    summary_word_limit: int = DEFAULT_SUMMARY_WORD_LIMIT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    summary_max_output_tokens: int = DEFAULT_SUMMARY_MAX_OUTPUT_TOKENS
    awakening_probe_output_tokens: int = DEFAULT_AWAKENING_PROBE_OUTPUT_TOKENS

    @classmethod
    def from_env(cls, root: Path = ROOT) -> SynapseProtocol:
        load_dotenv(root / ".env", override=False)

        chat_model = os.getenv("GHOST_CHAT_MODEL", "gpt-5-mini")

        return cls(
            chat_model=chat_model,
            summary_model=os.getenv("GHOST_SUMMARY_MODEL", chat_model),
            reasoning_effort=os.getenv("GHOST_REASONING_EFFORT", DEFAULT_REASONING_EFFORT),
            summary_reasoning_effort=os.getenv(
                "GHOST_SUMMARY_REASONING_EFFORT",
                DEFAULT_SUMMARY_REASONING_EFFORT,
            ),
            default_k=_int_env("GHOST_DEFAULT_K", 3),
            max_k=_int_env("GHOST_MAX_K", 8),
            max_message_chars=_int_env("GHOST_MAX_MESSAGE_CHARS", 100),
            max_summary_chars=_int_env("GHOST_MAX_SUMMARY_CHARS", 3000),
            answer_word_limit=_int_env("GHOST_ANSWER_WORD_LIMIT", DEFAULT_ANSWER_WORD_LIMIT),
            summary_word_limit=_int_env("GHOST_SUMMARY_WORD_LIMIT", DEFAULT_SUMMARY_WORD_LIMIT),
            max_output_tokens=_int_env("GHOST_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS),
            summary_max_output_tokens=_int_env(
                "GHOST_SUMMARY_MAX_OUTPUT_TOKENS",
                DEFAULT_SUMMARY_MAX_OUTPUT_TOKENS,
            ),
            awakening_probe_output_tokens=_int_env(
                "GHOST_AWAKENING_PROBE_OUTPUT_TOKENS",
                DEFAULT_AWAKENING_PROBE_OUTPUT_TOKENS,
            ),
        )
