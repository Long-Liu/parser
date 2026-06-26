"""Shared validation helpers used across API and utility layers."""

import re

# Allow alphanumeric + underscore for template IDs (used in table names)
TEMPLATE_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")

# SQL-safe identifier: must start with letter/underscore, then alphanumeric/underscore
IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def is_valid_template_id(value: str) -> bool:
    """Check if *value* is safe for use in dynamic table names."""
    return bool(TEMPLATE_ID_RE.match(value))


def is_valid_identifier(value: str) -> bool:
    """Check if *value* is safe for use as an SQL identifier."""
    return bool(IDENTIFIER_RE.match(value))
