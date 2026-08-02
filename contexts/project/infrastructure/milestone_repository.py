"""Milestone read/write repository — project context owner of ProjectMilestone.

Moved here from the analytics context: milestones are project lifecycle data
owned by the project context.
"""

from __future__ import annotations

from decimal import Decimal

from contexts.project.infrastructure.tables import Project, ProjectMilestone
from contexts.shared.application.transaction import (
    NoopTransactionManager,
    TransactionManager,
)
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination


def _number(value) -> float:
    return float(value) if value is not None else 0.0


def _milestone_dict(row) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "ym": row.ym,
        "progress": _number(row.progress),
        "title": row.title,
        "description": row.description or "",
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


class TortoiseMilestoneRepository:
    def __init__(self, transaction_manager: TransactionManager | None = None) -> None:
        self._tx = transaction_manager or NoopTransactionManager()

    @staticmethod
    async def _project(project_id: int):
        project = await Project.get_or_none(id=project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    async def milestones(self, project_id: int, pagination: Pagination) -> dict:
        await self._project(project_id)
        query = ProjectMilestone.filter(project_id=project_id)
        total = await query.count()
        rows = await query.order_by("-ym", "-id").offset(pagination.offset).limit(pagination.size)
        return {
            "milestones": [_milestone_dict(row) for row in rows],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def project_progress(self, project_id: int, pagination: Pagination) -> dict:
        result = await self.milestones(project_id, pagination)
        return {
            "progress": [
                {
                    "id": row["id"],
                    "ym": row["ym"],
                    "progress": row["progress"],
                    "completion": row["description"],
                    "latest_milestone": row["title"],
                    "completed_at": row["completed_at"],
                }
                for row in result["milestones"]
            ],
            "pagination": result["pagination"],
        }

    async def create_milestone(self, project_id: int, data: dict) -> dict:
        async with self._tx.transaction():
            await self._project(project_id)
            if not data.get("ym") or not data.get("title"):
                raise ValidationError("ym and title are required")
            row = await ProjectMilestone.create(
                project_id=project_id,
                ym=data["ym"],
                title=data["title"].strip(),
                progress=Decimal(str(data.get("progress", 0))),
                description=data.get("description", ""),
                completed_at=data.get("completed_at") or None,
            )
            return _milestone_dict(row)

    async def update_milestone(self, project_id: int, milestone_id: int, data: dict) -> dict:
        async with self._tx.transaction():
            row = await ProjectMilestone.get_or_none(
                id=milestone_id,
                project_id=project_id,
            )
            if row is None:
                raise NotFoundError(f"milestone {milestone_id} not found")
            for field in ("ym", "title", "description", "completed_at"):
                if field in data:
                    setattr(row, field, data[field] or None)
            if "progress" in data:
                row.progress = Decimal(str(data["progress"]))
            await row.save()
            return _milestone_dict(row)

    async def delete_milestone(self, project_id: int, milestone_id: int) -> None:
        async with self._tx.transaction():
            deleted = await ProjectMilestone.filter(
                id=milestone_id,
                project_id=project_id,
            ).delete()
            if not deleted:
                raise NotFoundError(f"milestone {milestone_id} not found")
