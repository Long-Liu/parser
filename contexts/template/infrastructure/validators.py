"""Shared validation helpers used across API and utility layers."""

import re

# Allow alphanumeric + underscore for template IDs (used in table names)
TEMPLATE_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
