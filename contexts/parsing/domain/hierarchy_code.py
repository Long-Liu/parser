from __future__ import annotations

import re
from datetime import date, datetime

# Full-width ASCII variants (Ａ-ｚ０-９（）．etc.) → half-width, plus ideographic space.
_FULLWIDTH_TRANS = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}
_FULLWIDTH_TRANS[0x3000] = 0x20

_CN_NUMERALS = "一二三四五六七八九十百千万零〇两"

# One hierarchy segment: an alphanumeric token ("1", "12", "1AA", "GT1"),
# a parenthesized Chinese numeral ("(一)"), a bare Chinese numeral ("一", "十二"),
# or a short CJK label ending in a Chinese numeral ("标段一").
_SEGMENT_RE = (
    r"(?:"
    r"[A-Za-z0-9]+"
    r"|\([" + _CN_NUMERALS + r"]+\)"
    r"|[" + _CN_NUMERALS + r"]+"
    r"|[一-鿿]{1,8}[" + _CN_NUMERALS + r"]+"
    r")"
)

# Trailing decoration stripped before validation: "一、" → "一", "1." → "1".
_TRAILING_PUNCT = "、.。．-－—:： "

# data_*.hierarchy_code is varchar(50); longer text is not a serial number.
MAX_CODE_LENGTH = 50

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_serial_text(value: object) -> str | None:
    """Stringify a raw cell value into candidate serial text, or None."""
    if value is None or isinstance(value, (datetime, date, bool)):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).translate(_FULLWIDTH_TRANS).strip()
    return text or None


def strip_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub("", text)


def parse_hierarchy_code(value: object, separator: str) -> str | None:
    """Parse a hierarchy-column cell into a hierarchy code.

    Returns the normalized serial text ("1", "1.2", "一", "(一)", "1-1",
    "标段一"), or None when the cell is empty, a date, or not serial-shaped.
    With an empty separator the column is a dedicated code column, so any
    non-empty normalized text is accepted. Never raises.
    """
    text = normalize_serial_text(value)
    if text is None:
        return None
    if not separator:
        return text if len(text) <= MAX_CODE_LENGTH else None
    text = text.rstrip(_TRAILING_PUNCT)
    if not text or len(text) > MAX_CODE_LENGTH:
        return None
    pattern = rf"^{_SEGMENT_RE}(?:{re.escape(separator)}{_SEGMENT_RE})*$"
    return text if re.match(pattern, text) else None
