from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from signal_chamber.server.settings import Settings


security = HTTPBasic()


def install_docs_routes(app: FastAPI, settings: Settings) -> None:
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

    @app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(verify_docs_access)])
    async def openapi_schema():
        return get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
