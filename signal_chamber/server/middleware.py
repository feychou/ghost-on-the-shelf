from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from signal_chamber.server.access import access_token_is_valid
from signal_chamber.server.settings import Settings


def install_middlewares(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.middleware("http")
    async def production_request_guards(request: Request, call_next: Any):
        if _origin_must_be_checked(settings, request):
            origin = request.headers.get("origin", "").rstrip("/")

            if origin not in settings.allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origin is not allowed."},
                )

        if _access_must_be_checked(settings, request):
            if not settings.access_configured:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "Access gate is not configured."},
                )

            token = request.cookies.get(settings.access_cookie_name)

            if not access_token_is_valid(settings, token):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Access cookie is required."},
                )

        return await call_next(request)


def _origin_must_be_checked(settings: Settings, request: Request) -> bool:
    return (
        settings.enforce_origin
        and request.method != "OPTIONS"
        and request.url.path.startswith("/v1/")
    )


def _access_must_be_checked(settings: Settings, request: Request) -> bool:
    return (
        settings.access_required
        and request.method != "OPTIONS"
        and request.url.path in {"/v1/chat", "/v1/awakening"}
    )
