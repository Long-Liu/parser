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
