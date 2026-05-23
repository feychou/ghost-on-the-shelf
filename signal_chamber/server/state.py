from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from core.synapse.runtime import RuntimeArchive, load_runtime_archive
from signal_chamber.server.guards import InMemoryGuards
from signal_chamber.server.settings import Settings


def configure_app_state(
    app: FastAPI,
    settings: Settings,
    *,
    openai_client: Any | None,
    archive: RuntimeArchive | None,
    guards: InMemoryGuards | None,
) -> None:
    app.state.settings = settings
    app.state.openai_client = openai_client
    app.state.guards = guards or InMemoryGuards(settings)

    if archive is not None:
        app.state.archive = archive
        app.state.archive_error = None
        return

    try:
        app.state.archive = load_runtime_archive(
            settings.runtime_prompt_path,
            settings.memory_index_path,
        )
        app.state.archive_error = None
    except Exception as exc:  # Health should explain startup artifact problems.
        app.state.archive = None
        app.state.archive_error = str(exc)
