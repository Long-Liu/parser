from __future__ import annotations

from contexts.shared.domain.exceptions import ConflictError, NotFoundError, ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.pagination import Pagination
from contexts.shared.application.transaction import TransactionManager, TransactionalService, transactional
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import (
    ProjectRepository, ProjectDataCleanup, UserDirectory, ProjectNotificationPort,
    ProjectMetricsPort,
)
from contexts.alert.application.alert_app_service import AlertApplicationService


class ProjectApplicationService(TransactionalService):
    def __init__(self, repo: ProjectRepository,
                 cleanup: ProjectDataCleanup | None = None,
                 users: UserDirectory | None = None,
                 notifications: ProjectNotificationPort | None = None,
                 alert_svc: AlertApplicationService | None = None,
                 transaction_manager: TransactionManager | None = None,
                 metrics: ProjectMetricsPort | None = None) -> None:
        super().__init__(transaction_manager)
        self._repo = repo
        self._cleanup = cleanup
        self._users = users
        self._notifications = notifications
        self._alert_svc = alert_svc
        self._metrics = metrics

    @transactional
    async def create(self, code: str, name: str, created_by: UserId | None = None,
                     **details) -> dict:
        existing = await self._repo.find_by_code(code)
        if existing:
            raise ConflictError("project code already exists")
        project = Project.create(project_id=None, code=code, name=name,
                                 created_by=created_by, **details)
        await self._repo.save(project)
        if project.status == "warning" and self._notifications and project.id:
            await self._notifications.publish_warning(project.id, project.name)
        if project.id is None:
            raise RuntimeError("project repository did not assign an id")
        if self._alert_svc:
            await self._alert_svc.evaluate(project.id.value)
        return self._serialize(project)

    async def list_all(self, *, keyword: str = "", status: str = "",
                       pagination: Pagination,
                       user_id: UserId | None = None) -> dict:
        query = {
            "keyword": keyword.strip(), "status": status.strip(),
            "offset": pagination.offset, "limit": pagination.size,
        }
        if user_id is not None:
            query["user_id"] = user_id
        projects, total = await self._repo.list_all(**query)
        extras = await self._enrichment(projects)
        return {
            "projects": [self._serialize(p, extras.get(p.id.value) if p.id else None)
                         for p in projects],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def get_by_id(self, project_id: ProjectId) -> dict:
        p = await self._repo.find_by_id(project_id)
        if not p:
            raise NotFoundError(f"project {project_id} not found")
        extras = await self._enrichment([p])
        return self._serialize(p, extras.get(project_id.value))

    async def _enrichment(self, projects: list[Project]) -> dict[int, dict]:
        """Batch-load manager names and latest-month gross profit metrics.

        Both lookups run at most once per call (keyed by id sets), so list
        serialization never triggers N+1 queries.
        """
        ids = [p.id.value for p in projects if p.id is not None]
        if not ids:
            return {}
        names: dict[int, str | None] = {}
        if self._users is not None:
            manager_ids = sorted(
                {p.manager_id.value for p in projects if p.manager_id is not None}
            )
            if manager_ids:
                names = await self._users.real_names(manager_ids)
        metrics: dict[int, dict] = {}
        if self._metrics is not None:
            metrics = await self._metrics.latest_gross_profit(ids)
        extras: dict[int, dict] = {}
        for p in projects:
            if p.id is None:
                continue
            entry: dict = {
                "manager_name": names.get(p.manager_id.value) if p.manager_id else None,
            }
            entry.update(metrics.get(p.id.value) or {
                "latest_ym": None, "revenue": None, "cost": None,
                "profit": None, "profit_rate": None,
            })
            extras[p.id.value] = entry
        return extras

    @transactional
    async def update(self, project_id: int, **details) -> dict:
        project = await self._repo.find_by_id(ProjectId(project_id))
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        details.pop("code", None)
        project.update_details(**details)
        await self._repo.save(project)
        if project.status == "warning" and self._notifications:
            await self._notifications.publish_warning(project.id, project.name)
        if self._alert_svc:
            await self._alert_svc.evaluate(project_id)
        return self._serialize(project)

    @transactional
    async def delete(self, project_id: int) -> None:
        if await self._repo.find_by_id(ProjectId(project_id)) is None:
            raise NotFoundError(f"project {project_id} not found")
        pid = ProjectId(project_id)
        if self._alert_svc:
            await self._alert_svc.delete_project(project_id)
        if self._cleanup:
            await self._cleanup.delete_for_project(pid)
        await self._repo.delete(pid)

    @transactional
    async def assign_user(self, project_id: int, user_id: int,
                          is_primary: bool = False, role: str = "viewer") -> None:
        if await self._repo.find_by_id(ProjectId(project_id)) is None:
            raise NotFoundError(f"project {project_id} not found")
        if role not in {"manager", "viewer"}:
            raise ValidationError("role must be manager or viewer")
        if self._users and not await self._users.exists(UserId(user_id)):
            raise NotFoundError(f"user {user_id} not found")
        await self._repo.assign_user(
            ProjectId(project_id), UserId(user_id), is_primary, role,
        )

    @transactional
    async def remove_user(self, project_id: int, user_id: int) -> None:
        await self._repo.remove_user(ProjectId(project_id), UserId(user_id))

    @staticmethod
    def _serialize(project: Project, extra: dict | None = None) -> dict:
        extra = extra or {}
        return {
            "id": project.id.value if project.id else None,
            "code": project.code,
            "name": project.name,
            "project_type": project.project_type,
            "capacity_mw": float(project.capacity_mw) if project.capacity_mw is not None else None,
            "contract_price": float(project.contract_price) if project.contract_price is not None else None,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "manager_id": project.manager_id.value if project.manager_id else None,
            "manager_name": extra.get("manager_name"),
            "latest_ym": extra.get("latest_ym"),
            "revenue": extra.get("revenue"),
            "cost": extra.get("cost"),
            "profit": extra.get("profit"),
            "profit_rate": extra.get("profit_rate"),
            "stage": project.stage,
            "status": project.status,
            "progress": float(project.progress),
            "description": project.description,
        }
