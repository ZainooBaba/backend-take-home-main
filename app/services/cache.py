"""
Simple in-memory TTL cache for expensive computed responses.

Used by the leaderboard endpoint, which aggregates across potentially
tens of thousands of sighting rows on every request. A 60-second TTL
means callers always see data that is at most one minute stale, which
is acceptable for a leaderboard that updates as new sightings are logged.

Call `leaderboard_cache.invalidate()` anywhere a write makes the cached
data immediately stale (e.g. after confirming a sighting).
"""

import time
from typing import Any, Optional


class TTLCache:
    """Thread-unsafe but sufficient in-process TTL cache."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def invalidate(self) -> None:
        """Bust the entire cache (call after writes that affect rankings)."""
        self._store.clear()


# Shared singleton — imported by routers that read or write the leaderboard
leaderboard_cache = TTLCache(ttl_seconds=60)
