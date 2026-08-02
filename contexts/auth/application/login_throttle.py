"""Login brute-force protection.

In-memory failed-attempt tracking per username (primary — blocks guessing a
known account's password, e.g. the seeded admin) and per client IP (secondary
— slows username-spraying). A username is locked out for ``lockout_seconds``
after ``max_failures`` consecutive failures; an IP is throttled once it exceeds
``max_ip_failures`` within ``ip_window_seconds``.

State is per-process: adequate for single-worker deployments; back it with a
shared store (Redis/DB) when scaling to multiple workers.
"""

from __future__ import annotations

import time

from contexts.shared.domain.exceptions import TooManyRequestsError


class LoginThrottler:
    def __init__(
        self,
        *,
        max_failures: int = 5,
        lockout_seconds: int = 300,
        max_ip_failures: int = 20,
        ip_window_seconds: int = 60,
    ) -> None:
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        self._max_ip_failures = max_ip_failures
        self._ip_window_seconds = ip_window_seconds
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}
        self._ip_attempts: dict[str, list[float]] = {}

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _remaining(self, key: str) -> float:
        return max(0.0, self._locked_until.get(key, 0.0) - self._now())

    def check(self, username: str, ip: str = "") -> None:
        """Raise TooManyRequestsError when the username or IP is throttled."""
        remaining = self._remaining(username)
        if remaining > 0:
            raise TooManyRequestsError(
                f"too many failed login attempts; try again in {int(remaining) + 1}s",
                retry_after=int(remaining) + 1,
            )
        if ip and self._ip_rate_exceeded(ip):
            raise TooManyRequestsError("too many login attempts from this address; try again later")

    def register_failure(self, username: str, ip: str = "") -> None:
        """Record a failed attempt; locks the username out at the threshold."""
        failures = self._failures.get(username, 0) + 1
        self._failures[username] = failures
        if failures >= self._max_failures:
            self._locked_until[username] = self._now() + self._lockout_seconds
            self._failures[username] = 0
        if ip:
            self._ip_attempts.setdefault(ip, []).append(self._now())

    def reset(self, username: str, ip: str = "") -> None:
        """Clear throttling state after a successful login."""
        self._failures.pop(username, None)
        self._locked_until.pop(username, None)
        if ip:
            self._ip_attempts.pop(ip, None)

    def _ip_rate_exceeded(self, ip: str) -> bool:
        now = self._now()
        attempts = [t for t in self._ip_attempts.get(ip, []) if now - t < self._ip_window_seconds]
        self._ip_attempts[ip] = attempts
        return len(attempts) >= self._max_ip_failures
