from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from signal_chamber.server.settings import Settings


TOKEN_VERSION = "v1"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def invite_code_is_valid(settings: Settings, code: str) -> bool:
    candidate = code.strip()

    if not candidate:
        return False

    if settings.access_code_hash:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        return secrets.compare_digest(digest, settings.access_code_hash)

    if settings.access_code:
        return secrets.compare_digest(candidate, settings.access_code)

    return False


def create_access_token(settings: Settings, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    session_id = secrets.token_urlsafe(24)
    payload = f"{TOKEN_VERSION}.{issued_at}.{session_id}"
    signature = _sign(settings, payload)

    return f"{payload}.{signature}"


def access_token_is_valid(settings: Settings, token: str | None, now: int | None = None) -> bool:
    return access_session_id(settings, token, now=now) is not None


def access_session_id(settings: Settings, token: str | None, now: int | None = None) -> str | None:
    if not token or not settings.access_configured:
        return None

    parts = token.split(".")

    if len(parts) != 4:
        return None

    version, issued_at_raw, session_id, signature = parts
    payload = f"{version}.{issued_at_raw}.{session_id}"

    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return None

    if version != TOKEN_VERSION:
        return None

    expected_signature = _sign(settings, payload)

    if not secrets.compare_digest(signature, expected_signature):
        return None

    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return None

    current_time = int(time.time() if now is None else now)

    if not 0 <= current_time - issued_at <= settings.access_cookie_max_age_seconds:
        return None

    return session_id


def _sign(settings: Settings, payload: str) -> str:
    return hmac.new(
        settings.access_cookie_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
