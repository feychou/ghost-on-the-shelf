from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from openai import OpenAI

from core.synapse.runtime import RuntimeArchive
from signal_chamber.server.access import access_session_id, access_token_from_authorization
from signal_chamber.server.guards import GuardRejected, InMemoryGuards


def archive_or_none(request: Request) -> RuntimeArchive | None:
    return request.app.state.archive


def require_archive(request: Request) -> RuntimeArchive:
    archive = request.app.state.archive

    if archive is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Runtime archive is not loaded: {request.app.state.archive_error}",
        )

    return archive


def openai_client(request: Request) -> Any:
    if request.app.state.openai_client is None:
        request.app.state.openai_client = OpenAI()

    return request.app.state.openai_client


def openai_is_configured(request: Request) -> bool:
    return (
        request.app.state.openai_client is not None
        or request.app.state.settings.openai_api_key_configured
    )


def guards(request: Request) -> InMemoryGuards:
    return request.app.state.guards


def client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def access_request_session_id(request: Request) -> str | None:
    settings = request.app.state.settings
    token = access_token_from_authorization(request.headers.get("authorization"))
    session_id = access_session_id(settings, token)

    return session_id or None


def limit_exception(exc: GuardRejected) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None

    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers=headers,
    )
