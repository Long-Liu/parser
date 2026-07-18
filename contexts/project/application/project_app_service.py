from __future__ import annotations

from contexts.shared.domain.exceptions import ConflictError, NotFoundError, ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.pagination import Pagination
from contexts.shared.application.transaction import TransactionManager, TransactionalService, transactional
from contexts.shared.domain.base_domain_event import DomainEvent
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.project.domain.events import ProjectCreated, ProjectDeleted, ProjectUpdated
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import (
    ProjectRepository, ProjectDataCleanup, UserDirectory, ProjectNotificationPort,
)


class _NullEventPublisher(EventPublisher):
    """Default publisher for tests/adapters that do not wire domain events."""

    async def publish(self, events: list[DomainEvent]) -> None:
        return None


class ProjectApplicationService(TransactionalService):
    def __init__(self, repo: ProjectRepository,
                 cleanup: ProjectDataCleanup | None = None,
                 users: UserDirectory | None = None,
                 notifications: ProjectNotificationPort | None = None,
                 event_publisher: EventPublisher | None = None,
                 transaction_manager: TransactionManager | None = None) -> None:
        super().__init__(transaction_manager)
        self._repo = repo
        self._cleanup = cleanup
        self._users = users
        self._notifications = notifications
        self._event_publisher = event_publisher or _NullEventPublisher()

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
        # Alert evaluation is event-driven: the alert context subscribes to
        # ProjectCreated and evaluates after this transaction commits.
        project.record(ProjectCreated(
            aggregate_id=project.id.value, code=project.code, name=project.name,
        ))
        await self._event_publisher.publish(project.pull_events())
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
        return {
            "projects": [self._serialize(p) for p in projects],
            "pagination": {"page": pagination.page, "size": pagination.size, "total": total},
        }

    async def get_by_id(self, project_id: ProjectId) -> dict:
        p = await self._repo.find_by_id(project_id)
        if not p:
            raise NotFoundError(f"project {project_id} not found")
        return self._serialize(p)

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
        project.record(ProjectUpdated(
            aggregate_id=project_id, changed_fields=tuple(sorted(details)),
        ))
        await self._event_publisher.publish(project.pull_events())
        return self._serialize(project)

    @transactional
    async def delete(self, project_id: int) -> None:
        project = await self._repo.find_by_id(ProjectId(project_id))
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        pid = ProjectId(project_id)
        # ProjectDeleted is published after commit; the alert context subscribes
        # to it and cleans up its own alert data for this project.
        project.record(ProjectDeleted(aggregate_id=project_id, code=project.code))
        if self._cleanup:
            await self._cleanup.delete_for_project(pid)
        await self._repo.delete(pid)
        await self._event_publisher.publish(project.pull_events())

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
    def _serialize(project: Project) -> dict:
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
            "stage": project.stage,
            "status": project.status,
            "progress": float(project.progress),
            "description": project.description,
        }
