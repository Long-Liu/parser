"""Typed wrappers around Tortoise .values() / .values_list() await.

Tortoise type stubs define ValuesQuery.__await__ → list[dict] | dict (the
union accounts for .first()) and ValuesListQuery without __await__ at all.
These helpers restore the correct return types so call sites don't need
per-line # type: ignore comments.
"""

from __future__ import annotations

from typing import Any

from tortoise.queryset import QuerySet, QuerySetSingle


async def fetch_values(
    qs: QuerySet | QuerySetSingle,
    *fields: str,
) -> list[dict[str, Any]]:
    """Await ``qs.values(*fields)`` with the correct return type."""
    return await qs.values(*fields)  # type: ignore[return-type]


async def fetch_values_list(
    qs: QuerySet | QuerySetSingle,
    *fields: str,
    flat: bool = False,
) -> list[Any]:
    """Await ``qs.values_list(*fields, flat=flat)`` with the correct return type."""
    return await qs.values_list(*fields, flat=flat)  # type: ignore[return-type]
