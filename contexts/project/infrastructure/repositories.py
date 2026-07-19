from __future__ import annotations

from tortoise.expressions import Q

from contexts.project.domain.project import Project
from contexts.project.domain.repositories import (
    ProjectRepository, ProjectDataCleanup, UserDirectory, ProjectNotificationPort,
    ProjectMetricsPort,
)
from contexts.project.infrastructure.tables import Project as OrmProject
from contexts.project.infrastructure.tables import ProjectUser, ProjectMilestone
from contexts.auth.infrastructure.tables import User as OrmUser, Notification
from contexts.parsing.infrastructure.data_cleanup import ParsedDataCleanup
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.shared.infrastructure.database.tables import (
    SETTLE_CONTRACT_PRICE,
    SETTLE_CUMULATIVE_COST,
    SETTLE_CUMULATIVE_OUTPUT,
    SETTLE_CURRENT_PROFIT,
    SETTLE_CURRENT_PROFIT_RATE,
    DataSettlementOutput,
)
from contexts.shared.domain.identifiers import ProjectId, UserId


def _to_entity(orm: OrmProject) -> Project:
    return Project(
        project_id=ProjectId(orm.id),
        code=orm.code,
        name=orm.name,
        created_by=UserId(orm.created_by) if orm.created_by else None,
        project_type=orm.project_type or "",
        capacity_mw=orm.capacity_mw,
        contract_price=orm.contract_price,
        start_date=orm.start_date,
        end_date=orm.end_date,
        manager_id=UserId(orm.manager_id) if orm.manager_id else None,
        stage=orm.stage,
        status=orm.status,
        progress=orm.progress,
        description=orm.description or "",
    )


class TortoiseProjectRepository(ProjectRepository):
    async def save(self, project: Project) -> None:
        values = {
            "code": project.code,
            "name": project.name,
            "project_type": project.project_type,
            "capacity_mw": project.capacity_mw,
            "contract_price": project.contract_price,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "manager_id": project.manager_id.value if project.manager_id else None,
            "stage": project.stage,
            "status": project.status,
            "progress": project.progress,
            "description": project.description,
            "created_by": project.created_by.value if project.created_by else None,
        }
        if project.id is None:
            orm = await OrmProject.create(**values)
            project.id = ProjectId(orm.id)
            return
        existing = await OrmProject.get_or_none(id=project.id.value)
        if existing is None:
            orm = OrmProject(id=project.id.value, **values)
            await orm.save(force_create=True)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            await existing.save(update_fields=list(values.keys()))

    async def find_by_id(self, project_id: ProjectId) -> Project | None:
        orm = await OrmProject.get_or_none(id=project_id.value)
        return _to_entity(orm) if orm else None

    async def find_by_code(self, code: str) -> Project | None:
        orm = await OrmProject.get_or_none(code=code)
        return _to_entity(orm) if orm else None

    async def list_all(self, *, keyword: str = "", status: str = "",
                       user_id: UserId | None = None,
                       offset: int = 0, limit: int = 20) -> tuple[list[Project], int]:
        query = OrmProject.all()
        if user_id is not None:
            project_ids = await ProjectUser.filter(user_id=user_id.value).values_list(
                "project_id", flat=True
            )
            query = query.filter(id__in=list(project_ids))
        if keyword:
            query = query.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
        if status:
            query = query.filter(status=status)
        total = await query.count()
        rows = await query.order_by("id").offset(offset).limit(limit)
        return [_to_entity(o) for o in rows], total

    async def delete(self, project_id: ProjectId) -> None:
        await ProjectUser.filter(project_id=project_id.value).delete()
        await ProjectMilestone.filter(project_id=project_id.value).delete()
        await OrmProject.filter(id=project_id.value).delete()

    async def assign_user(self, project_id: ProjectId, user_id: UserId,
                          is_primary: bool = False, role: str = "viewer") -> None:
        if is_primary:
            await ProjectUser.filter(user_id=user_id.value).update(is_primary=False)
        existing = await ProjectUser.get_or_none(
            project_id=project_id.value, user_id=user_id.value
        )
        if existing is None:
            await ProjectUser.create(
                project_id=project_id.value, user_id=user_id.value,
                is_primary=is_primary, role=role,
            )
        else:
            existing.is_primary = is_primary
            existing.role = role
            await existing.save(update_fields=["is_primary", "role"])

    async def remove_user(self, project_id: ProjectId, user_id: UserId) -> None:
        await ProjectUser.filter(
            project_id=project_id.value, user_id=user_id.value
        ).delete()


class TortoiseProjectDataCleanup(ProjectDataCleanup):
    """Delegates parsed-data deletion to the parsing context's cleanup port."""

    def __init__(self, parsed_data_cleanup: ParsedDataCleanup) -> None:
        self._parsed_data_cleanup = parsed_data_cleanup

    async def delete_for_project(self, project_id: ProjectId) -> None:
        await self._parsed_data_cleanup.delete_for_project(project_id.value)


class TortoiseUserDirectory(UserDirectory):
    async def exists(self, user_id: UserId) -> bool:
        return await OrmUser.filter(id=user_id.value).exists()

    async def real_names(self, user_ids: list[int]) -> dict[int, str | None]:
        if not user_ids:
            return {}
        rows = await OrmUser.filter(id__in=list(user_ids)).values("id", "real_name")
        return {row["id"]: row["real_name"] for row in rows}


class TortoiseProjectMetrics(ProjectMetricsPort):
    """Batch read model over shared tables (no analytics-context import).

    Latest month per project = the successful upload batch with the max ym
    (ties broken by max batch id); metrics come from the data_settlement_output
    (表11 结算产值表) indicator rows of that batch, mirroring the analytics
    context's _profit_item current block.
    """

    async def latest_gross_profit(self, project_ids: list[int]) -> dict[int, dict]:
        if not project_ids:
            return {}
        batches = await UploadBatch.filter(
            project_id__in=list(project_ids), status="success",
        ).order_by("project_id", "-ym", "-id").values("id", "project_id", "ym")
        latest: dict[int, dict] = {}
        for batch in batches:
            latest.setdefault(batch["project_id"], batch)
        if not latest:
            return {}
        rows = await DataSettlementOutput.filter(
            batch_id__in=[b["id"] for b in latest.values()],
        ).values("batch_id", "indicator_name", "cumulative_value")
        by_batch: dict[int, dict] = {}
        for row in rows:
            if row["indicator_name"]:
                by_batch.setdefault(row["batch_id"], {})[
                    row["indicator_name"]] = row["cumulative_value"]
        return {
            project_id: {
                "latest_ym": batch["ym"],
                **self._settlement(by_batch.get(batch["id"])),
            }
            for project_id, batch in latest.items()
        }

    @staticmethod
    def _settlement(indicators: dict | None) -> dict:
        def number(*names: str) -> float | None:
            if not indicators:
                return None
            for name in names:
                value = indicators.get(name)
                if value is not None:
                    return float(value)
            return None

        revenue = number(SETTLE_CUMULATIVE_OUTPUT, SETTLE_CONTRACT_PRICE)
        profit = number(SETTLE_CURRENT_PROFIT)
        cost = number(SETTLE_CUMULATIVE_COST)
        if cost is None and revenue is not None and profit is not None:
            cost = revenue - profit
        # Rate indicators are stored as ratios (0.x); report percents.
        rate = number(SETTLE_CURRENT_PROFIT_RATE)
        if rate is not None:
            rate = round(rate * 100, 2)
        elif revenue and profit is not None:
            rate = round(profit / revenue * 100, 2)
        return {
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "profit_rate": rate,
        }


class ProjectNotificationAdapter(ProjectNotificationPort):
    async def publish_warning(self, project_id: ProjectId,
                              project_name: str) -> None:
        exists = await Notification.filter(
            notification_type="project_warning", project_id=project_id.value,
            title=project_name,
        ).exists()
        if not exists:
            await Notification.create(
                notification_type="project_warning", title=project_name,
                message="项目处于预警状态", project_id=project_id.value,
            )
