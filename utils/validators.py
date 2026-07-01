"""Shared validation helpers used across API and utility layers."""

import re

# Allow alphanumeric + underscore for template IDs (used in table names)
TEMPLATE_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")

# Allowed MIME types for file upload
ALLOWED_MIME_TYPES = frozenset({
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
ALLOWED_EXTENSIONS = frozenset({".xlsx"})
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def is_valid_template_id(value: str) -> bool:
    """Check if *value* is safe for use in dynamic table names."""
    return bool(TEMPLATE_ID_RE.match(value))


def get_query_int(args: dict, key: str, default: int | None = None) -> int | None:
    """Parse an integer from query args, returning *default* if missing.

    Raises ValueError with a user-facing message on unparseable values.
    """
    raw = args.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValueError(f"{key} must be an integer") from None


def require_json_field(data: dict | None, field: str) -> str:
    """Extract a required string field from a JSON body.

    Raises ValueError with a user-facing message on missing/invalid input.
    """
    if data is None:
        raise ValueError("request body must be JSON")
    value = data.get(field)
    if not value or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()
