"""Typed request-scoped authentication context."""

from dataclasses import dataclass, field

from sanic.request import Request

from contexts.shared.domain.exceptions import AuthenticationError


@dataclass(frozen=True, slots=True)
class RequestAuth:
    user_id: int
    username: str
    permissions: frozenset[str]
    claims: dict = field(default_factory=dict)


def current_auth(request: Request) -> RequestAuth:
    """Return authenticated request state or fail explicitly."""
    auth = getattr(request.ctx, "auth", None)
    if not isinstance(auth, RequestAuth):
        raise AuthenticationError("request is not authenticated")
    return auth
