"""Type validation for extracted rows."""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# fields that are structural, not column data
NON_COLUMN_FIELDS = frozenset({"hierarchy_code", "monthly_data"})

DECIMAL_TYPE_RE = re.compile(r"^decimal\((\d+),\s*(\d+)\)$", re.IGNORECASE)


def _decimal_spec(col_type: str) -> tuple[int, int] | None:
    match = DECIMAL_TYPE_RE.match(col_type.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _cast_decimal(value, precision: int, scale: int) -> Decimal:
    dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    quant = Decimal(1).scaleb(-scale)
    dec = dec.quantize(quant, rounding=ROUND_HALF_UP)
    digits = dec.as_tuple().digits
    exponent = dec.as_tuple().exponent
    integer_digits = len(digits) + exponent if exponent < 0 else len(digits)
    integer_digits = max(integer_digits, 1 if dec != 0 else 0)
    if integer_digits > precision - scale:
        raise ValueError("decimal_precision_overflow")
    return dec


def validate(rows: list[dict], columns: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cast decimal fields and collect errors; returns (valid_rows, errors).

    Each row is shallow-copied before mutation so caller data is intact.
    """
    valid_rows = []
    errors = []

    col_types = {c["db_field"]: c.get("type", "varchar(255)") for c in columns}

    for i, row in enumerate(rows):
        row_errors = []
        row_copy = dict(row)

        for field, value in row_copy.items():
            if field in NON_COLUMN_FIELDS:
                continue
            col_type = col_types.get(field, "")
            decimal_spec = _decimal_spec(col_type)
            if decimal_spec and value is not None:
                try:
                    row_copy[field] = _cast_decimal(value, *decimal_spec)
                except (InvalidOperation, ValueError, TypeError):
                    row_errors.append({"row_index": i, "field": field, "value": value, "error": "invalid_decimal"})
                    row_copy[field] = None

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(row_copy)

    return valid_rows, errors
