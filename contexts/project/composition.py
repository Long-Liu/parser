"""Project bounded-context composition."""

from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.domain.repositories import (
    ProjectDataCleanup, ProjectNotificationPort, ProjectRepository, UserDirectory,
)
from contexts.shared.application.transaction import TransactionManager
from contexts.shared.domain.event_publisher import EventPublisher


def build_project_service(
    repository: ProjectRepository,
    cleanup: ProjectDataCleanup,
    users: UserDirectory,
    notifications: ProjectNotificationPort,
    events: EventPublisher,
    transactions: TransactionManager,
) -> ProjectApplicationService:
    return ProjectApplicationService(
        repository, cleanup, users, notifications, events, transactions,
    )
