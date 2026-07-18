"""Small value helpers shared across infrastructure adapters."""

from __future__ import annotations


def or_default(value, default):
    """Return value if it is not None, otherwise default.

    Unlike ``or``, treats 0/0.0/Decimal('0') as real values.
    """
    return value if value is not None else default
