class DomainError(Exception):
    """Base domain exception."""


class NotFoundError(DomainError):
    """Entity not found by identity."""


class ValidationError(DomainError):
    """Domain rule violated."""


class ConflictError(DomainError):
    """Duplicate or conflicting state."""


class AuthenticationError(DomainError):
    """Invalid credentials."""


class AuthorizationError(DomainError):
    """Insufficient permissions."""


class TooManyRequestsError(DomainError):
    """Request rate limit or lockout exceeded (HTTP 429)."""

    def __init__(self, message: str = "too many requests", *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
