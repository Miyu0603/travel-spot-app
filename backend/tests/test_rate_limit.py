"""Tests for the extraction rate limiter.

Runs standalone so it needs no test framework installed:

    python tests/test_rate_limit.py

The limiter takes an injectable clock, so these advance time instead of sleeping.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rate_limit import HOUR, SlidingWindowLimiter  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def limiter_with_clock():
    clock = FakeClock()
    return SlidingWindowLimiter(clock=clock), clock


def test_allows_calls_up_to_the_limit():
    limiter, _ = limiter_with_clock()
    rules = [("ip:1.2.3.4", 3, HOUR)]
    assert [limiter.acquire(rules) for _ in range(3)] == [None, None, None]


def test_blocks_once_the_limit_is_reached():
    limiter, _ = limiter_with_clock()
    rules = [("ip:1.2.3.4", 2, HOUR)]
    limiter.acquire(rules)
    limiter.acquire(rules)
    retry_after = limiter.acquire(rules)
    assert retry_after is not None
    assert retry_after == HOUR  # no time has passed, so the full window remains


def test_a_blocked_call_consumes_no_quota():
    """Otherwise every rejected retry would push the window further out and a
    blocked caller could never recover."""
    limiter, clock = limiter_with_clock()
    rules = [("ip:1.2.3.4", 1, HOUR)]
    limiter.acquire(rules)

    clock.advance(HOUR / 2)
    assert limiter.acquire(rules) is not None  # blocked halfway through

    clock.advance(HOUR / 2)
    assert limiter.acquire(rules) is None  # the original hit expired on schedule


def test_slot_frees_up_after_the_window():
    limiter, clock = limiter_with_clock()
    rules = [("ip:1.2.3.4", 1, HOUR)]
    limiter.acquire(rules)
    clock.advance(HOUR - 1)
    assert limiter.acquire(rules) is not None
    clock.advance(2)
    assert limiter.acquire(rules) is None


def test_limits_are_tracked_per_key():
    limiter, _ = limiter_with_clock()
    assert limiter.acquire([("ip:1.1.1.1", 1, HOUR)]) is None
    assert limiter.acquire([("ip:2.2.2.2", 1, HOUR)]) is None
    assert limiter.acquire([("ip:1.1.1.1", 1, HOUR)]) is not None


def test_global_rule_blocks_even_when_the_ip_rule_has_room():
    limiter, _ = limiter_with_clock()
    limiter.acquire([("ip:1.1.1.1", 10, HOUR), ("global", 1, HOUR)])
    # A different IP with plenty of personal quota still hits the global cap
    assert limiter.acquire([("ip:9.9.9.9", 10, HOUR), ("global", 1, HOUR)]) is not None


def test_a_global_rejection_does_not_charge_the_ip_rule():
    limiter, _ = limiter_with_clock()
    limiter.acquire([("ip:1.1.1.1", 10, HOUR), ("global", 1, HOUR)])
    limiter.acquire([("ip:9.9.9.9", 1, HOUR), ("global", 1, HOUR)])  # rejected globally
    # 9.9.9.9 was never charged, so it succeeds once the global rule is lifted
    assert limiter.acquire([("ip:9.9.9.9", 1, HOUR), ("global", 0, HOUR)]) is None


def test_a_limit_of_zero_disables_the_rule():
    limiter, _ = limiter_with_clock()
    rules = [("ip:1.2.3.4", 0, HOUR)]
    assert all(limiter.acquire(rules) is None for _ in range(50))


def test_no_rules_at_all_is_allowed():
    limiter, _ = limiter_with_clock()
    assert limiter.acquire([]) is None


def test_expired_keys_are_swept_so_memory_stays_bounded():
    limiter, clock = limiter_with_clock()
    for i in range(1100):  # past the sweep threshold
        limiter.acquire([(f"ip:10.0.{i // 256}.{i % 256}", 5, HOUR)])
    clock.advance(HOUR * 2)
    limiter.acquire([("ip:1.2.3.4", 5, HOUR)])
    remaining = len(limiter._hits)
    assert remaining < 1100, f"stale keys were not swept: {remaining} left"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
