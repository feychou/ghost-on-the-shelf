from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from openai import OpenAIError

from core.synapse.awakening import probe_openai_for_awakening
from core.synapse.ghost import GhostEngine, GhostResponseError
from core.synapse.retrieval import MemoryRetriever, build_contextual_retrieval_query
from signal_chamber.server.access import create_access_token, invite_code_is_valid
from signal_chamber.server.dependencies import (
    access_request_session_id,
    archive_or_none,
    client_key,
    guards,
    limit_exception,
    openai_client,
    openai_is_configured,
    require_archive,
)
from signal_chamber.server.guards import GuardRejected
from signal_chamber.server.moderation import message_is_flagged
from signal_chamber.server.schemas import (
    AccessRequest,
    AccessResponse,
    AwakeningResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RetrievedFragmentModel,
)
from signal_chamber.server.settings import Settings


router = APIRouter()

BLOCKED_CHAT_REPLY = (
    "I can't help with that request, but I can stay with safer questions about the archive."
)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    archive = archive_or_none(request)

    return HealthResponse(
        status="ok" if archive else "degraded",
        runtime_loaded=bool(archive),
        memory_index_loaded=bool(archive),
        archive_error=request.app.state.archive_error,
        chunk_count=archive.memory_index.chunk_count if archive else 0,
    )


@router.post("/v1/access", response_model=AccessResponse)
async def access(request: Request, payload: AccessRequest) -> AccessResponse:
    settings = request.app.state.settings
    request_guards = guards(request)

    if not settings.access_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Access gate is not configured.",
        )

    try:
        await request_guards.check_access(client_key(request))
    except GuardRejected as exc:
        raise limit_exception(exc) from exc

    if not invite_code_is_valid(settings, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access code.",
        )

    return AccessResponse(
        access_granted=True,
        access_token=create_access_token(settings),
        expires_in=settings.access_token_max_age_seconds,
    )


@router.post("/v1/awakening", response_model=AwakeningResponse)
async def awakening(request: Request) -> AwakeningResponse:
    settings = request.app.state.settings
    request_guards = guards(request)

    try:
        await request_guards.check_awakening(client_key(request))
    except GuardRejected as exc:
        raise limit_exception(exc) from exc

    archive = archive_or_none(request)

    if archive is None:
        return _awakening_response(
            can_awaken=False,
            reason="archive_unavailable",
            message=f"The archive cannot awaken because runtime artifacts are unavailable: {request.app.state.archive_error}",
            archive_loaded=False,
            openai_ready=False,
        )

    if not openai_is_configured(request):
        return _awakening_response(
            can_awaken=False,
            reason="openai_unconfigured",
            message="The archive cannot awaken because OPENAI_API_KEY is not configured.",
            archive_loaded=True,
            openai_ready=False,
        )

    try:
        probe_openai_for_awakening(openai_client(request), settings.protocol, archive)
    except OpenAIError:
        return _awakening_response(
            can_awaken=False,
            reason="openai_unavailable",
            message=(
                "The archive cannot awaken because OpenAI access is unavailable. "
                "Check credentials, billing, quota, or rate limits."
            ),
            archive_loaded=True,
            openai_ready=False,
        )

    return _awakening_response(
        can_awaken=True,
        reason=None,
        message="The archive is ready to awaken.",
        archive_loaded=True,
        openai_ready=True,
    )


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    settings = request.app.state.settings
    message = payload.message.strip()
    session_summary = (payload.session_summary or "").strip()
    k = payload.k or settings.default_k

    _validate_chat_payload(settings, message, session_summary, k)

    if not settings.chat_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat is currently disabled.",
        )

    archive = require_archive(request)
    client = openai_client(request)
    request_guards = guards(request)
    client_rate_key = client_key(request)
    session_id = access_request_session_id(request)
    session_rate_key = f"access:{session_id}" if session_id else f"client:{client_rate_key}"

    try:
        await request_guards.begin_chat(client_rate_key, session_rate_key)
    except GuardRejected as exc:
        raise limit_exception(exc) from exc

    try:
        if message_is_flagged(client, settings, message):
            return ChatResponse(
                reply=BLOCKED_CHAT_REPLY,
                session_summary=session_summary,
                retrieved=[],
            )

        retriever = MemoryRetriever(client, archive.memory_index)
        fragments = retriever.retrieve_with_context(message, session_summary, k=k)
        ghost = GhostEngine(settings.protocol, archive, client)
        ghost_reply = ghost.answer(
            message,
            session_summary,
            fragments,
            safety_identifier=session_id,
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The ghost could not reach OpenAI.",
        ) from exc
    except GhostResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    finally:
        await request_guards.finish_chat()

    return ChatResponse(
        reply=ghost_reply.reply,
        session_summary=ghost_reply.session_summary,
        retrieved=[
            RetrievedFragmentModel(
                id=fragment.id,
                title=fragment.title,
                source=fragment.source,
                score=fragment.score,
            )
            for fragment in ghost_reply.retrieved
        ],
    )


def _validate_chat_payload(settings: Settings, message: str, session_summary: str, k: int) -> None:
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    if len(message) > settings.max_message_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds {settings.max_message_chars} characters.",
        )

    if len(session_summary) > settings.max_summary_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session summary exceeds {settings.max_summary_chars} characters.",
        )

    if k > settings.max_k:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"k cannot exceed {settings.max_k}.",
        )


def _build_retrieval_query(message: str, session_summary: str) -> str:
    return build_contextual_retrieval_query(message, session_summary)


def _awakening_response(
    *,
    can_awaken: bool,
    reason: str | None,
    message: str,
    archive_loaded: bool,
    openai_ready: bool,
) -> AwakeningResponse:
    return AwakeningResponse(
        can_awaken=can_awaken,
        reason=reason,
        message=message,
        archive_loaded=archive_loaded,
        openai_ready=openai_ready,
    )
