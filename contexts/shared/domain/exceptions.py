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


def _demo():
    e = ValidationError("amount must be positive")
    assert isinstance(e, DomainError)
    assert str(e) == "amount must be positive"
    try:
        raise NotFoundError("user 42")
    except DomainError:
        pass
    print("exceptions: OK")


if __name__ == "__main__":
    _demo()
