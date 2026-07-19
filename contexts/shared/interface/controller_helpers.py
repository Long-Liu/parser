"""Shared controller helpers — eliminate duplication across interface layer.

Usage in controllers::

    from contexts.shared.interface.controller_helpers import (
        parse_int, pagination_from,
    )

    pagination = pagination_from(request)
    page = parse_int(request.args.get("page"), 1)

Services are injected into controllers via the composition root
(``contexts.container.build_controllers``); these helpers only cover
query-parameter parsing.
"""

from __future__ import annotations

from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.pagination import Pagination


def parse_int(value: str | None, default: int) -> int:
    """Parse a query parameter to int. Raises ValidationError on non-integer input."""
    try:
        return default if value is None else int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"invalid integer: {value}") from None


def pagination_from(request, max_size: int = 100, default_size: int = 20) -> Pagination:
    """Extract a validated Pagination value object from request query params.

    Reads ``page`` (default 1) and ``size`` (default ``default_size``) from
    ``request.args``.
    """
    return Pagination(
        page=parse_int(request.args.get("page"), 1),
        size=parse_int(request.args.get("size"), default_size),
        max_size=max_size,
    )
