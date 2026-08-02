"""Shared stop-rule value types (shared kernel).

Used by both the template context (defines the stop rules in a template spec)
and the parsing context (interprets them while extracting rows). Pure value
types with no logic, so sharing them avoids coupling the parsing algorithm to
the template context's aggregate.
"""

from __future__ import annotations

from enum import StrEnum


class StopRuleType(StrEnum):
    CELL_MATCH = "cell_match"
    CONSECUTIVE_EMPTY = "consecutive_empty_rows"


class StopRuleAction(StrEnum):
    # EXCLUDE: drop the matched row and stop (default).
    # LAST: keep the matched row as the final data row, then stop.
    EXCLUDE = "exclude"
    LAST = "last"
