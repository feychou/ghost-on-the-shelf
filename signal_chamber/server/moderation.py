from __future__ import annotations

from typing import Any

from signal_chamber.server.settings import Settings


def message_is_flagged(client: Any, settings: Settings, message: str) -> bool:
    if not settings.moderation_enabled:
        return False

    response = client.moderations.create(
        model=settings.moderation_model,
        input=message,
    )
    results = getattr(response, "results", [])

    if not results:
        return False

    return bool(getattr(results[0], "flagged", False))
