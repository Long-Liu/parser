from __future__ import annotations

from contexts.shared.domain.exceptions import ValidationError

#: Columns that must never be overwritten by a client-driven row update.
PROTECTED_FIELDS = frozenset({"id", "batch_id"})


def build_updates(field_types: dict[str, str], requested: dict) -> dict:
    """Validate and normalize a client ``{"fields": {...}}`` update payload.

    Whitelist policy: unknown keys are REJECTED with a 400 ValidationError
    instead of being silently ignored. This mirrors the repository's filter
    field validation (unknown filter field -> 400) and avoids silent frontend
    typos being dropped on the floor.

    ``field_types`` maps real model column names to a coarse kind tag
    ("decimal" / "other") supplied by the infrastructure layer.
    """
    if not requested:
        raise ValidationError("no fields to update")
    updates: dict = {}
    for name, value in requested.items():
        if name in PROTECTED_FIELDS:
            raise ValidationError(
                f"field {name!r} is protected and cannot be updated"
            )
        kind = field_types.get(name)
        if kind is None:
            raise ValidationError(f"unknown field: {name}")
        if name == "monthly_data":
            if not isinstance(value, dict):
                raise ValidationError(
                    "monthly_data must be an object of key/value pairs"
                )
            updates[name] = dict(value)
        elif kind == "decimal" and value is not None:
            # Same conversion rule as parsing.domain.data_validator: decimal
            # columns must be float-convertible, otherwise reject with the
            # offending field name.
            try:
                updates[name] = float(value)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"field {name!r} expects a decimal value, got {value!r}"
                ) from None
        else:
            updates[name] = value
    return updates
