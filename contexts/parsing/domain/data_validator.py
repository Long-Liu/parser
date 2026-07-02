from __future__ import annotations

from contexts.parsing.domain.parse_job import ParsedRow, RowError
from contexts.template.domain.template import Template


class DataValidator:
    """Validate extracted rows against template column type specs."""

    def validate(
        self, rows: list[ParsedRow], template: Template
    ) -> tuple[list[ParsedRow], list[RowError]]:
        valid: list[ParsedRow] = []
        errors: list[RowError] = []
        for row in rows:
            row_errors = self._validate_row(row, template)
            if row_errors:
                errors.extend(row_errors)
            else:
                valid.append(row)
        return valid, errors

    def _validate_row(
        self, row: ParsedRow, template: Template
    ) -> list[RowError]:
        errs: list[RowError] = []
        for col in template.fixed_columns:
            if col.db_field in row.fields:
                value = row.fields[col.db_field]
                if value is not None and col.db_type.startswith("decimal"):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errs.append(RowError(
                            row_index=row.row_index,
                            field=col.db_field,
                            value=str(value),
                            reason="expected decimal",
                        ))
        return errs
