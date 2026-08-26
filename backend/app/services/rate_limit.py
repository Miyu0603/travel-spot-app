"""Rate limiting for the endpoints that spend money on our behalf.

Counters live in this process, not Redis: the API runs as a single Render
instance, so process-local counts are accurate and there is no extra service to
host. The trade-off is that counters reset whenever Render puts the service to
sleep — fine for protecting an API budget, not enough for anything stricter.

Two limits apply together:
  * per client IP — stops one caller hammering the endpoint
  * global        — caps total spend even if the caller rotates IPs
"""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request

from app.config import settings

HOUR = 3600.0
DAY = 86400.0

# Above this many tracked keys, sweep expired entries so a stream of distinct
# client IPs cannot grow the dict without bound.
_SWEEP_THRESHOLD = 1024


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        # Injectable so tests can advance time without sleeping.
        self._clock = clock

    def acquire(self, rules: list[tuple[str, int, float]]) -> float | None:
        """Try to consume one slot against every rule at once.

        `rules` is a list of (key, limit, window_seconds); a limit <= 0 disables
        that rule. Returns None when allowed, otherwise the seconds until the
        first slot frees up. A rejected call consumes no quota, so being blocked
        never pushes the window further out.
        """
        active = [rule for rule in rules if rule[1] > 0]
        if not active:
            return None

        now = self._clock()
        with self._lock:
            for key, limit, window in active:
                hits = self._hits[key]
                while hits and now - hits[0] >= window:
                    hits.popleft()
                if len(hits) >= limit:
                    return window - (now - hits[0])

            for key, _, _ in active:
                self._hits[key].append(now)

            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(now, max(window for _, _, window in active))
            return None

    def _sweep(self, now: float, max_window: float) -> None:
        """Drop entries older than the longest window, then any empty keys.

        Using the longest window is safe: anything older than that has already
        expired for every rule, whatever its own window was.
        """
        for key in list(self._hits):
            hits = self._hits[key]
            while hits and now - hits[0] >= max_window:
                hits.popleft()
            if not hits:
                del self._hits[key]


_limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # Render terminates TLS upstream, so request.client is the proxy — the real
    # caller is the first hop in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_extraction_limit(request: Request) -> None:
    """FastAPI dependency for the AI extraction endpoints."""
    retry_after = _limiter.acquire(
        [
            (f"ip:{client_ip(request)}", settings.rate_limit_per_ip_hourly, HOUR),
            ("global", settings.rate_limit_global_daily, DAY),
        ]
    )
    if retry_after is None:
        return

    minutes = max(1, round(retry_after / 60))
    raise HTTPException(
        status_code=429,
        detail=f"萃取次數已達上限，請於約 {minutes} 分鐘後再試。",
        headers={"Retry-After": str(int(retry_after) + 1)},
    )
