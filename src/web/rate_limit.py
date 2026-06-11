"""
In-memory sliding-window rate limiter (no external dependency).

Keyed by client identifier (IP). Each client may issue at most *max_requests*
within *window_seconds*; further requests are rejected until the window slides
forward. The logic is pure and time-injectable so it can be unit-tested without
FastAPI or real clocks.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Callable


class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        """Register a request from *client*; return True if within the limit."""
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[client]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def retry_after(self, client: str) -> float:
        """Seconds until *client*'s oldest hit leaves the window (0 if free)."""
        with self._lock:
            hits = self._hits[client]
            if len(hits) < self.max_requests or not hits:
                return 0.0
            return max(0.0, hits[0] + self.window_seconds - self._clock())
