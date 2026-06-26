"""Decimal-cast validation for extracted rows."""

from decimal import Decimal, InvalidOperation

# fields that are structural, not column data
NON_COLUMN_FIELDS = frozenset({"hierarchy_code", "monthly_data"})


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
            if col_type.startswith("decimal") and value is not None:
                try:
                    row_copy[field] = Decimal(str(value)) if not isinstance(value, Decimal) else value
                except (InvalidOperation, ValueError, TypeError):
                    row_errors.append({"row_index": i, "field": field, "value": value, "error": "invalid_decimal"})
                    row_copy[field] = None

        valid_rows.append(row_copy)
        if row_errors:
            errors.extend(row_errors)

    return valid_rows, errors
