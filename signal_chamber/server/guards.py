from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone

from signal_chamber.server.settings import Settings


class GuardRejected(Exception):
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class InMemoryGuards:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._rate_events: dict[str, dict[str, deque[float]]] = defaultdict(lambda: defaultdict(deque))
        self._active_chats = 0

    async def check_access(self, key: str) -> None:
        async with self._lock:
            now = self._now()
            self._commit_rate_or_reject(
                bucket="access",
                key=key,
                limit=self.settings.access_rate_limit_per_minute,
                now=now,
            )

    async def check_awakening(self, key: str) -> None:
        async with self._lock:
            now = self._now()
            self._commit_rate_or_reject(
                bucket="awakening",
                key=key,
                limit=self.settings.awakening_rate_limit_per_minute,
                now=now,
            )

    async def begin_chat(self, key: str, session_key: str | None = None) -> None:
        async with self._lock:
            now = self._now()
            self._commit_rate_or_reject(
                bucket="chat",
                key=key,
                limit=self.settings.chat_rate_limit_per_minute,
                now=now,
            )
            self._commit_rate_or_reject(
                bucket="chat_session",
                key=session_key or f"missing:{key}",
                limit=self.settings.chat_session_rate_limit_per_minute,
                now=now,
            )

            if self._active_chats >= self.settings.max_concurrent_chats:
                raise GuardRejected("Too many ghost conversations are active. Please retry shortly.", retry_after=5)

            self._active_chats += 1

    async def finish_chat(self) -> None:
        async with self._lock:
            self._active_chats = max(0, self._active_chats - 1)

    def _commit_rate_or_reject(self, bucket: str, key: str, limit: int, now: datetime) -> None:
        if limit <= 0:
            raise GuardRejected("Rate limit exceeded.", retry_after=60)

        events = self._rate_events[bucket][key]
        cutoff = now.timestamp() - 60

        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= limit:
            retry_after = max(1, int(events[0] + 60 - now.timestamp()))
            raise GuardRejected("Rate limit exceeded.", retry_after=retry_after)

        events.append(now.timestamp())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
