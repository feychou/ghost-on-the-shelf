from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from openai import OpenAI, OpenAIError

from core.synapse.awakening import probe_openai_for_awakening
from core.synapse.ghost import GhostEngine, GhostResponseError
from core.synapse.retrieval import MemoryRetriever
from core.synapse.runtime import RuntimeArchive, load_runtime_archive
from signal_chamber.server.guards import GuardRejected, InMemoryGuards
from signal_chamber.server.schemas import (
    AwakeningResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RetrievedFragmentModel,
)
from signal_chamber.server.settings import Settings


security = HTTPBasic()


def create_app(
    settings: Settings | None = None,
    *,
    openai_client: Any | None = None,
    archive: RuntimeArchive | None = None,
    guards: InMemoryGuards | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Ghost on the Shelf",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.openai_client = openai_client
    app.state.guards = guards or InMemoryGuards(settings)

    if archive is None:
        try:
            app.state.archive = load_runtime_archive(
                settings.runtime_prompt_path,
                settings.memory_index_path,
            )
            app.state.archive_error = None
        except Exception as exc:  # Health should explain startup artifact problems.
            app.state.archive = None
            app.state.archive_error = str(exc)
    else:
        app.state.archive = archive
        app.state.archive_error = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def production_origin_guard(request: Request, call_next: Any):
        if _origin_must_be_checked(settings, request):
            origin = request.headers.get("origin", "").rstrip("/")

            if origin not in settings.allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origin is not allowed."},
                )

        return await call_next(request)

    def verify_docs_access(
        credentials: Annotated[HTTPBasicCredentials, Security(security)],
    ) -> None:
        if not settings.docs_credentials_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Documentation credentials are not configured.",
            )

        username_ok = secrets.compare_digest(credentials.username, settings.docs_username)
        password_ok = secrets.compare_digest(credentials.password, settings.docs_password)

        if not (username_ok and password_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid documentation credentials.",
                headers={"WWW-Authenticate": "Basic"},
            )

    @app.get("/docs", include_in_schema=False, dependencies=[Depends(verify_docs_access)])
    async def swagger_ui():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Ghost on the Shelf API Docs",
        )

    @app.get("/redoc", include_in_schema=False, dependencies=[Depends(verify_docs_access)])
    async def redoc_ui():
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="Ghost on the Shelf API Docs",
        )

    @app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(verify_docs_access)])
    async def openapi_schema():
        return get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        archive = _get_archive_or_none(app)

        return HealthResponse(
            status="ok" if archive else "degraded",
            runtime_loaded=bool(archive),
            memory_index_loaded=bool(archive),
            archive_error=app.state.archive_error,
            chunk_count=archive.memory_index.chunk_count if archive else 0,
        )

    @app.post("/v1/awakening", response_model=AwakeningResponse)
    async def awakening(request: Request) -> AwakeningResponse:
        guards = _get_guards(request)

        try:
            await guards.check_awakening(_client_key(request))
        except GuardRejected as exc:
            raise _limit_exception(exc) from exc

        archive = _get_archive_or_none(app)

        if archive is None:
            return _awakening_response(
                can_awaken=False,
                reason="archive_unavailable",
                message=f"The archive cannot awaken because runtime artifacts are unavailable: {app.state.archive_error}",
                archive_loaded=False,
                openai_ready=False,
            )

        if not _openai_is_configured(request):
            return _awakening_response(
                can_awaken=False,
                reason="openai_unconfigured",
                message="The archive cannot awaken because OPENAI_API_KEY is not configured.",
                archive_loaded=True,
                openai_ready=False,
            )

        try:
            probe_openai_for_awakening(_get_openai_client(request), settings.protocol, archive)
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

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
        message = payload.message.strip()
        session_summary = (payload.session_summary or "").strip()
        k = payload.k or settings.default_k

        _validate_chat_payload(settings, message, session_summary, k)

        archive = _require_archive(request)
        openai_client = _get_openai_client(request)
        guards = _get_guards(request)

        try:
            await guards.begin_chat(_client_key(request))
        except GuardRejected as exc:
            raise _limit_exception(exc) from exc

        try:
            retriever = MemoryRetriever(openai_client, archive.memory_index)
            fragments = retriever.retrieve(message, k=k)
            ghost = GhostEngine(settings.protocol, archive, openai_client)
            ghost_reply = ghost.answer(message, session_summary, fragments)
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
            await guards.finish_chat()

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

    return app


def _origin_must_be_checked(settings: Settings, request: Request) -> bool:
    return (
        settings.enforce_origin
        and request.method != "OPTIONS"
        and request.url.path.startswith("/v1/")
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


def _get_archive_or_none(app: FastAPI) -> RuntimeArchive | None:
    return app.state.archive


def _require_archive(request: Request) -> RuntimeArchive:
    archive = request.app.state.archive

    if archive is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Runtime archive is not loaded: {request.app.state.archive_error}",
        )

    return archive


def _get_openai_client(request: Request) -> Any:
    if request.app.state.openai_client is None:
        request.app.state.openai_client = OpenAI()

    return request.app.state.openai_client


def _openai_is_configured(request: Request) -> bool:
    return (
        request.app.state.openai_client is not None
        or request.app.state.settings.openai_api_key_configured
    )


def _get_guards(request: Request) -> InMemoryGuards:
    return request.app.state.guards


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def _limit_exception(exc: GuardRejected) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None

    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers=headers,
    )


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


app = create_app()
