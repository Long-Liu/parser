"""Project bounded-context composition."""

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.domain.repositories import (
    ProjectDataCleanup, ProjectMetricsPort, ProjectNotificationPort,
    ProjectRepository, UserDirectory,
)
from contexts.shared.application.transaction import TransactionManager


def build_project_service(
    repository: ProjectRepository,
    cleanup: ProjectDataCleanup,
    users: UserDirectory,
    notifications: ProjectNotificationPort,
    alerts: AlertApplicationService,
    transactions: TransactionManager,
    metrics: ProjectMetricsPort | None = None,
) -> ProjectApplicationService:
    if metrics is None:
        from contexts.project.infrastructure.repositories import (
            TortoiseProjectMetrics,
        )
        metrics = TortoiseProjectMetrics()
    return ProjectApplicationService(
        repository, cleanup, users, notifications, alerts, transactions,
        metrics=metrics,
    )
