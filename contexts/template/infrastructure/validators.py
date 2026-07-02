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
