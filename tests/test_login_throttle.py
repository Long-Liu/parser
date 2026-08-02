"""Login brute-force protection: unit tests for LoginThrottler."""

from __future__ import annotations

import pytest

from contexts.auth.application.login_throttle import LoginThrottler
from contexts.shared.domain.exceptions import TooManyRequestsError


def test_no_lock_below_threshold():
    throttler = LoginThrottler(max_failures=5)
    for _ in range(4):
        throttler.register_failure("admin", "1.2.3.4")
    throttler.check("admin", "1.2.3.4")  # no raise


def test_locks_username_at_threshold():
    throttler = LoginThrottler(max_failures=3, lockout_seconds=60)
    for _ in range(3):
        throttler.register_failure("admin", "1.2.3.4")
    with pytest.raises(TooManyRequestsError) as exc_info:
        throttler.check("admin", "9.9.9.9")  # locked regardless of IP
    assert exc_info.value.retry_after is not None
    assert "too many failed" in str(exc_info.value)


def test_username_lock_is_independent_of_ip():
    throttler = LoginThrottler(max_failures=1)
    throttler.register_failure("admin", "1.1.1.1")
    with pytest.raises(TooManyRequestsError):
        throttler.check("admin", "2.2.2.2")


def test_reset_clears_username_state():
    throttler = LoginThrottler(max_failures=2)
    throttler.register_failure("admin", "")
    throttler.register_failure("admin", "")
    throttler.reset("admin", "")
    throttler.check("admin", "")  # no raise


def test_ip_throttle_is_independent_of_username():
    throttler = LoginThrottler(max_ip_failures=3, ip_window_seconds=60)
    for name in ("a", "b", "c"):
        throttler.register_failure(name, "9.9.9.9")
    with pytest.raises(TooManyRequestsError):
        throttler.check("fresh", "9.9.9.9")


def test_ip_counter_expires_out_of_window():
    throttler = LoginThrottler(max_ip_failures=2, ip_window_seconds=1)
    throttler.register_failure("a", "9.9.9.9")
    throttler.register_failure("b", "9.9.9.9")
    throttler._ip_attempts["9.9.9.9"] = [0.0]  # simulate stale attempts
    throttler.check("fresh", "9.9.9.9")  # stale attempts pruned, no raise
