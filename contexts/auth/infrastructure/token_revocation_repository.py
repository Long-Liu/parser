"""Tortoise-backed JWT blacklist (revoked_tokens table).

Revocation scheme
-----------------
- ``revoke(jti=...)``: blacklists exactly one token — used by logout.
- ``revoke_all_for_user``: upserts a sentinel row whose ``jti`` is
  ``user:{user_id}``. Any token (including legacy ones without a ``jti``)
  whose ``iat`` is at or before that row's ``revoked_at`` counts as revoked —
  used by change-password to invalidate every outstanding session. The
  sentinel is a single upserted row, so repeated password changes simply move
  the cutoff forward.
- ``is_revoked`` lazily deletes rows whose ``expires_at`` has passed; no
  scheduled cleanup job is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tortoise.exceptions import IntegrityError

from contexts.auth.domain.repositories import TokenRevocationRepository
from contexts.auth.infrastructure.tables import RevokedToken
from contexts.shared.domain.identifiers import UserId


def _user_marker(user_id: UserId) -> str:
    return f"user:{user_id.value}"


def _epoch(value: datetime) -> float:
    """Epoch seconds; Tortoise may return naive datetimes (treated as UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).timestamp()
    return value.timestamp()


class TortoiseTokenRevocationRepository(TokenRevocationRepository):
    async def revoke(self, *, jti: str, user_id: UserId, expires_at: datetime) -> None:
        try:
            await RevokedToken.create(
                jti=jti, user_id=user_id.value, expires_at=expires_at,
            )
        except IntegrityError:
            # Already blacklisted (e.g. double logout) — revoking is idempotent.
            return

    async def revoke_all_for_user(self, *, user_id: UserId, expires_at: datetime) -> None:
        marker = _user_marker(user_id)
        # Re-create so auto_now_add stamps revoked_at with a fresh cutoff.
        await RevokedToken.filter(jti=marker).delete()
        await RevokedToken.create(
            jti=marker, user_id=user_id.value, expires_at=expires_at,
        )

    async def is_revoked(self, *, jti: str | None, user_id: UserId,
                         issued_at: float | None) -> bool:
        # Lazy purge: rows past expires_at cover only naturally-expired tokens.
        await RevokedToken.filter(
            expires_at__lte=datetime.now(timezone.utc),
        ).delete()
        candidates = [_user_marker(user_id)]
        if jti:
            candidates.append(jti)
        rows = await RevokedToken.filter(jti__in=candidates)
        for row in rows:
            if jti and row.jti == jti:
                return True
            if (row.jti == candidates[0] and issued_at is not None
                    and _epoch(row.revoked_at) >= issued_at):
                return True
        return False
