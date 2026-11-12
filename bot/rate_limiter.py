"""
rate_limiter.py — Client-side throttle for VirusTotal's free tier
(4 requests/minute, 500/day by default, both set at the top of bot/main.py).

VirusTotal enforces its own limits server-side (HTTP 429), so this is a
courtesy layer that proactively spaces requests out and fails fast on the
daily cap, rather than a hard cross-process guarantee. Counts live in memory
and reset when the bot process restarts.
"""
import asyncio
import time
from collections import deque


class DailyQuotaExceeded(Exception):
    """Raised when the configured daily VirusTotal request budget is used up."""


class AsyncRateLimiter:
    def __init__(self, max_per_minute: int, max_per_day: int):
        self._max_per_minute = max_per_minute
        self._max_per_day = max_per_day
        self._minute_hits: deque = deque()
        self._day_hits: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is free, or raise DailyQuotaExceeded."""
        async with self._lock:
            while True:
                now = time.monotonic()
                self._evict(self._minute_hits, now, 60)
                self._evict(self._day_hits, now, 86400)

                if len(self._day_hits) >= self._max_per_day:
                    raise DailyQuotaExceeded(
                        "VirusTotal daily quota reached for this bot, try again tomorrow"
                    )

                if len(self._minute_hits) < self._max_per_minute:
                    self._minute_hits.append(now)
                    self._day_hits.append(now)
                    return

                wait_for = 60 - (now - self._minute_hits[0])
                await asyncio.sleep(max(wait_for, 0.1))

    @staticmethod
    def _evict(hits: deque, now: float, window_seconds: int) -> None:
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
