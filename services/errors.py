"""Typed service errors — used by services/ and caught by api/ for HTTP status mapping."""


class ServiceError(Exception):
    """Base error with an HTTP status code for the API layer."""
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


class ConflictError(ServiceError):
    """409 — duplicate resource."""
    def __init__(self, message: str = "resource already exists"):
        super().__init__(message, http_status=409)
