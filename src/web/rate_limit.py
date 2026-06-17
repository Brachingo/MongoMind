"""
Rate limiter de ventana deslizante en memoria (sin dependencias externas).

Indexado por identificador de cliente (IP). Cada cliente puede hacer como mucho
*max_requests* en *window_seconds*; el resto se rechaza hasta que la ventana
avanza. La lógica es pura y se le puede inyectar el reloj, así que se testea sin
FastAPI ni relojes reales.
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
        """Registra una petición de *client*; devuelve True si está dentro del límite."""
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
        """Segundos hasta que la petición más antigua de *client* salga de la ventana (0 si hay hueco)."""
        with self._lock:
            hits = self._hits[client]
            if len(hits) < self.max_requests or not hits:
                return 0.0
            return max(0.0, hits[0] + self.window_seconds - self._clock())
