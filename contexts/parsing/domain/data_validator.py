from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from contexts.parsing.domain.parse_job import ParsedRow, RowError
from contexts.parsing.domain.template_spec import TemplateSpec


class DataValidator:
    """Validate extracted rows against template column type specs."""

    def validate(self, rows: list[ParsedRow], template: TemplateSpec) -> tuple[list[ParsedRow], list[RowError]]:
        valid: list[ParsedRow] = []
        errors: list[RowError] = []
        for row in rows:
            row_errors = self._validate_row(row, template)
            if row_errors:
                errors.extend(row_errors)
            else:
                valid.append(row)
        return valid, errors

    @staticmethod
    def _validate_row(row: ParsedRow, template: TemplateSpec) -> list[RowError]:
        errs: list[RowError] = []
        for col in template.fixed_columns:
            if col.db_field not in row.fields:
                continue
            value = row.fields[col.db_field]
            if value is None:
                continue
            db_type = col.db_type or ""
            if db_type.startswith("decimal"):
                if not DataValidator._is_decimal(value):
                    errs.append(
                        RowError(
                            row_index=row.row_index,
                            field=col.db_field,
                            value=str(value),
                            reason="expected decimal",
                        )
                    )
            elif db_type in ("date", "datetime"):
                normalized = DataValidator._normalize_datetime(value, db_type)
                if normalized is None:
                    errs.append(
                        RowError(
                            row_index=row.row_index,
                            field=col.db_field,
                            value=str(value),
                            reason=f"expected {db_type}",
                        )
                    )
                else:
                    # Store the normalized ISO string so the write path
                    # (Tortoise DateField/DatetimeField) and the preview JSON
                    # payload both receive a value they can handle.
                    row.fields[col.db_field] = normalized
        return errs

    @staticmethod
    def _is_decimal(value: Any) -> bool:
        """Accept only finite, float-convertible values.

        Strings that float() accepts but Decimal cannot safely quantize
        (``1e999`` -> inf, ``inf``, ``nan``) must be rejected here so validation
        and the write path (Decimal(str(value)).quantize) agree."""
        try:
            return math.isfinite(float(value))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _normalize_datetime(value: Any, db_type: str) -> str | None:
        """Normalize a date/datetime column value to a Tortoise-parseable ISO string.

        Native date/datetime cells are ISO-serialized (the same conversion the
        preview JSON path applies); text is parsed with the lenient formats the
        validator accepts and normalized to the ISO string Tortoise
        DateField/DatetimeField can parse. Returns None when the value cannot be
        normalized, so validation and the write path stay consistent — a raw
        non-ISO string (e.g. ``2026/07/15``, ``2026年7月15日``) would otherwise
        pass validation but abort the whole batch insert in MySQL strict mode.
        """
        if isinstance(value, datetime):
            return (value.date() if db_type == "date" else value).isoformat()
        if isinstance(value, date):
            # A bare date in a datetime column is stored at midnight, matching
            # the string path (_parse_datetime on "YYYY-MM-DD").
            if db_type == "date":
                return value.isoformat()
            return datetime(value.year, value.month, value.day).isoformat()
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        parsed = DataValidator._parse_date(text) if db_type == "date" else DataValidator._parse_datetime(text)
        return parsed.isoformat() if parsed is not None else None

    @staticmethod
    def _parse_date(text: str) -> date | None:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        # ISO datetime strings are accepted by Tortoise's DateField.
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    @staticmethod
    def _parse_datetime(text: str) -> datetime | None:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
            return None
