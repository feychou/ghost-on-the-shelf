from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from core.synapse.runtime import RuntimeArchive
from signal_chamber.server.docs import install_docs_routes
from signal_chamber.server.guards import InMemoryGuards
from signal_chamber.server.middleware import install_middlewares
from signal_chamber.server.routes import router
from signal_chamber.server.settings import Settings
from signal_chamber.server.state import configure_app_state


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

    configure_app_state(
        app,
        settings,
        openai_client=openai_client,
        archive=archive,
        guards=guards,
    )
    install_middlewares(app, settings)
    install_docs_routes(app, settings)
    app.include_router(router)

    return app


app = create_app()
