"""Project bounded-context composition."""

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.domain.repositories import (
    ProjectDataCleanup, ProjectNotificationPort, ProjectRepository, UserDirectory,
)
from contexts.shared.application.transaction import TransactionManager


def build_project_service(
    repository: ProjectRepository,
    cleanup: ProjectDataCleanup,
    users: UserDirectory,
    notifications: ProjectNotificationPort,
    alerts: AlertApplicationService,
    transactions: TransactionManager,
) -> ProjectApplicationService:
    return ProjectApplicationService(
        repository, cleanup, users, notifications, alerts, transactions,
    )
