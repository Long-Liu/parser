from decimal import Decimal, InvalidOperation


def validate(rows: list[dict], columns: list[dict]) -> tuple[list[dict], list[dict]]:
    valid_rows = []
    errors = []

    col_types = {c["db_field"]: c.get("type", "varchar(255)") for c in columns}

    for i, row in enumerate(rows):
        row_errors = []
        for field, value in row.items():
            if field in ("hierarchy_code", "monthly_data"):
                continue
            col_type = col_types.get(field, "")
            if col_type.startswith("decimal") and value is not None:
                try:
                    row[field] = Decimal(str(value)) if not isinstance(value, Decimal) else value
                except (InvalidOperation, ValueError, TypeError):
                    row_errors.append({"row_index": i, "field": field, "value": value, "error": "invalid_decimal"})
                    row[field] = None

        valid_rows.append(row)
        if row_errors:
            errors.extend(row_errors)

    return valid_rows, errors
