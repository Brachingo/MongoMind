"""Unit tests for the sliding-window rate limiter — time is injected, no real clock."""
import sys
sys.path.insert(0, ".")
from src.web.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_allows_up_to_limit():
    clock = FakeClock()
    rl = RateLimiter(max_requests=3, window_seconds=60, clock=clock)
    assert rl.allow("ip") is True
    assert rl.allow("ip") is True
    assert rl.allow("ip") is True


def test_blocks_over_limit():
    clock = FakeClock()
    rl = RateLimiter(max_requests=3, window_seconds=60, clock=clock)
    for _ in range(3):
        rl.allow("ip")
    assert rl.allow("ip") is False


def test_window_slides_and_frees_slots():
    clock = FakeClock()
    rl = RateLimiter(max_requests=2, window_seconds=60, clock=clock)
    rl.allow("ip")
    rl.allow("ip")
    assert rl.allow("ip") is False
    clock.advance(61)  # both hits leave the window
    assert rl.allow("ip") is True


def test_clients_are_independent():
    clock = FakeClock()
    rl = RateLimiter(max_requests=1, window_seconds=60, clock=clock)
    assert rl.allow("ip-a") is True
    assert rl.allow("ip-b") is True
    assert rl.allow("ip-a") is False


def test_retry_after_positive_when_blocked():
    clock = FakeClock()
    rl = RateLimiter(max_requests=1, window_seconds=60, clock=clock)
    rl.allow("ip")
    assert rl.allow("ip") is False
    assert 0 < rl.retry_after("ip") <= 60


def test_retry_after_zero_when_free():
    clock = FakeClock()
    rl = RateLimiter(max_requests=2, window_seconds=60, clock=clock)
    rl.allow("ip")
    assert rl.retry_after("ip") == 0.0
