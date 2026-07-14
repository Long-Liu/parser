"""Explicit application composition root.

This module defines the strongly typed application component graph, but
deliberately does not create it at import time. ``build_container`` is the only
place where production implementations and object lifetimes are selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.alert.composition import build_alert_service
from contexts.alert.domain.repositories import AlertPushDispatcher
from contexts.alert.infrastructure.push import AlertWebSocketHub, TortoiseAlertOutboxDispatcher
from contexts.alert.infrastructure.repositories import TortoiseAlertMetricProvider, TortoiseAlertRepository
from contexts.analytics.application.analytics_service import AnalyticsApplicationService
from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.analytics.infrastructure.ai_provider import HttpAIAnalysisProvider
from contexts.analytics.infrastructure.analytics_repository import TortoiseAnalyticsRepository
from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import AuthorizationApplicationService
from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.composition import build_auth_components
from contexts.auth.domain.repositories import UserRepository
from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.auth.infrastructure.project_access_repository import TortoiseProjectAccessRepository
from contexts.auth.infrastructure.repositories import RoleRepositoryImpl, UserRepositoryImpl
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.infrastructure.repositories import DataQueryRepositoryImpl
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.parsing.composition import build_upload_service
from contexts.parsing.application.file_storage import FileStorage
from contexts.parsing.infrastructure.data_writer import TortoiseParsedDataSink
from contexts.parsing.infrastructure.file_storage import LocalUploadFileStorage
from contexts.parsing.infrastructure.repositories import ParseJobRepositoryImpl, UploadPreviewRepositoryImpl
from contexts.parsing.infrastructure.workbook_reader import OpenPyxlWorkbookReader
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.composition import build_project_service
from contexts.project.infrastructure.repositories import (
    ProjectDataCleanupImpl,
    ProjectNotificationAdapter,
    ProjectRepositoryImpl,
    TortoiseUserDirectory,
)
from contexts.shared.infrastructure.config import Settings
from contexts.shared.infrastructure.database.transaction import TortoiseTransactionManager
from contexts.shared.application.transaction import TransactionManager
from contexts.shared.infrastructure.domain_event_bus import domain_event_bus
from contexts.template.application.template_app_service import TemplateApplicationService
from contexts.template.infrastructure.repositories import YamlTemplateCatalog
from contexts.parsing.domain.repositories import ParseJobRepository
from contexts.project.domain.repositories import ProjectRepository

if TYPE_CHECKING:
    from contexts.shared.interface.base_controller import BaseController

@dataclass(frozen=True, slots=True)
class ApplicationComponents:
    """Strongly typed application graph exposed to the outer composition layer."""

    password_hasher: BCryptPasswordHasher
    alert_dispatcher: AlertPushDispatcher
    alert_hub: AlertWebSocketHub
    authorization_service: AuthorizationApplicationService
    project_access_policy: ProjectAccessPolicy
    auth_service: AuthApplicationService
    user_service: UserApplicationService
    role_service: RoleApplicationService
    project_service: ProjectApplicationService
    template_service: TemplateApplicationService
    data_service: DataApplicationService
    upload_service: UploadApplicationService
    analytics_service: AnalyticsApplicationService
    alert_service: AlertApplicationService
    parse_job_repository: ParseJobRepository
    project_repository: ProjectRepository


@dataclass(frozen=True, slots=True)
class ComponentOverrides:
    """Typed test/deployment substitutions for external infrastructure."""

    transaction_manager: TransactionManager | None = None
    user_repository: UserRepository | None = None
    file_storage: FileStorage | None = None
    ai_provider: AIAnalysisPort | None = None

def build_container(
    settings: Settings,
    overrides: ComponentOverrides | None = None,
) -> ApplicationComponents:
    """Build the complete production dependency graph in one pass."""
    overrides = overrides or ComponentOverrides()
    transaction_manager = overrides.transaction_manager or TortoiseTransactionManager()

    password_hasher = BCryptPasswordHasher()
    jwt_service = JwtService(settings.jwt.secret, settings.jwt.expiry_hours)
    user_repo = overrides.user_repository or UserRepositoryImpl()
    role_repo = RoleRepositoryImpl()
    project_access_repo = TortoiseProjectAccessRepository()
    project_repo = ProjectRepositoryImpl()
    project_cleanup = ProjectDataCleanupImpl()
    user_directory = TortoiseUserDirectory()
    project_notifications = ProjectNotificationAdapter()
    template_catalog = YamlTemplateCatalog()
    data_repo = DataQueryRepositoryImpl()
    parse_job_repo = ParseJobRepositoryImpl()
    preview_repo = UploadPreviewRepositoryImpl()
    data_sink = TortoiseParsedDataSink()
    file_storage = overrides.file_storage or LocalUploadFileStorage(settings.upload)
    workbook_reader = OpenPyxlWorkbookReader()
    ai_provider = overrides.ai_provider or HttpAIAnalysisProvider(settings.ai_analysis)
    analytics_repo = TortoiseAnalyticsRepository(ai_provider)
    alert_repo = TortoiseAlertRepository()
    alert_metrics = TortoiseAlertMetricProvider()
    alert_hub = AlertWebSocketHub()
    alert_dispatcher = TortoiseAlertOutboxDispatcher(alert_hub)

    alert_service = build_alert_service(
        alert_repo, alert_metrics, alert_dispatcher, transaction_manager,
    )
    auth = build_auth_components(
        user_repo, role_repo, project_access_repo, password_hasher, jwt_service,
        domain_event_bus, transaction_manager,
    )
    project_service = build_project_service(
        project_repo, project_cleanup, user_directory, project_notifications, alert_service,
        transaction_manager,
    )
    template_service = TemplateApplicationService(template_catalog)
    data_service = DataApplicationService(data_repo, transaction_manager)
    upload_service = build_upload_service(
        parse_job_repo, template_catalog, data_sink, domain_event_bus,
        file_storage, workbook_reader, project_repo, preview_repo, alert_service,
        transaction_manager,
    )
    analytics_service = AnalyticsApplicationService(analytics_repo)

    return ApplicationComponents(
        password_hasher=password_hasher,
        alert_dispatcher=alert_dispatcher,
        alert_hub=alert_hub,
        authorization_service=auth.authorization,
        project_access_policy=auth.project_access,
        auth_service=auth.auth,
        user_service=auth.users,
        role_service=auth.roles,
        project_service=project_service,
        template_service=template_service,
        data_service=data_service,
        upload_service=upload_service,
        analytics_service=analytics_service,
        alert_service=alert_service,
        parse_job_repository=parse_job_repo,
        project_repository=project_repo,
    )


def build_controllers(components: ApplicationComponents) -> tuple["BaseController", ...]:
    """Explicitly compose the HTTP adapters; no scanning or reflection involved."""
    from contexts.alert.interface.alert_controller import AlertController
    from contexts.analytics.interface.analytics_controller import AnalyticsController
    from contexts.auth.interface.auth_controller import AuthController
    from contexts.auth.interface.role_controller import RolesController
    from contexts.auth.interface.user_controller import UsersController
    from contexts.data.interface.data_controller import DataController
    from contexts.parsing.interface.batch_controller import BatchesController
    from contexts.parsing.interface.upload_controller import UploadsController
    from contexts.project.interface.project_controller import ProjectsController
    from contexts.template.interface.template_controller import TemplatesController

    return (
        AnalyticsController(
            components.analytics_service,
            components.project_access_policy,
            components.alert_service,
        ),
        AlertController(
            components.alert_service,
            components.project_access_policy,
            components.authorization_service,
            components.alert_hub,
        ),
        AuthController(
            components.auth_service,
            components.user_service,
        ),
        RolesController(components.role_service),
        UsersController(components.user_service),
        DataController(
            components.data_service,
            components.project_access_policy,
        ),
        BatchesController(
            components.parse_job_repository,
            components.project_repository,
            components.project_access_policy,
        ),
        UploadsController(components.upload_service),
        ProjectsController(components.project_service),
        TemplatesController(components.template_service),
    )
