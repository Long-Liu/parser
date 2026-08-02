"""Shared analytics test factories (make_project / make_batch / make_settlement).

These seeding helpers were duplicated across the analytics test modules; they
live here so each module imports one implementation instead of re-defining it.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import count

from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import Project
from contexts.shared.infrastructure.database.tables import DataSettlementOutput

_seq = count(1)


async def make_project(**kwargs) -> Project:
    n = next(_seq)
    defaults = {
        "code": f"P{int(n):04d}",
        "name": f"项目{n}",
        "contract_price": Decimal("1000"),
        "progress": Decimal("80"),
        "status": "normal",
    }
    defaults.update(kwargs)
    return await Project.create(**defaults)


async def make_batch(project_id: int, ym: str = "2026-07", file_name: str = "cost.xlsx") -> UploadBatch:
    return await UploadBatch.create(
        batch_no=f"T{int(next(_seq)):06d}",
        project_id=project_id,
        ym=ym,
        file_name=file_name,
        status="success",
    )


async def make_settlement(batch_id: int, **indicators) -> None:
    """Create 表11 settlement rows: one vertical row per indicator name."""
    for name, value in indicators.items():
        await DataSettlementOutput.create(
            batch_id=batch_id,
            indicator_name=name,
            cumulative_value=Decimal(str(value)),
        )
