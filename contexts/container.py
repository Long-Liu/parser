from __future__ import annotations

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.auth.infrastructure.repositories import UserRepositoryImpl
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.infrastructure.repositories import DataQueryRepositoryImpl
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.parsing.infrastructure.data_writer import SqlAlchemyParsedDataSink
from contexts.parsing.infrastructure.file_storage import LocalUploadFileStorage
from contexts.parsing.infrastructure.repositories import ParseJobRepositoryImpl
from contexts.parsing.infrastructure.workbook_reader import OpenPyxlWorkbookReader
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.infrastructure.repositories import ProjectRepositoryImpl
from contexts.shared.infrastructure.domain_event_bus import domain_event_bus
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.template.application.template_app_service import TemplateApplicationService
from contexts.template.infrastructure.repositories import YamlTemplateCatalog


class Container:
    def authentication_service(self, secret_key: str) -> AuthApplicationService:
        password_hasher = BCryptPasswordHasher()
        return AuthApplicationService(
            user_repo=UserRepositoryImpl(),
            auth_service=AuthenticationService(password_hasher),
            jwt_service=JwtService(secret_key),
            password_hasher=password_hasher,
            uow_factory=SqlAlchemyUnitOfWork,
        )

    def request_authorization_service(
        self, secret_key: str
    ) -> AuthorizationApplicationService:
        return AuthorizationApplicationService(
            user_repo=UserRepositoryImpl(),
            jwt_service=JwtService(secret_key),
        )

    def project_service(self) -> ProjectApplicationService:
        return ProjectApplicationService(ProjectRepositoryImpl(), SqlAlchemyUnitOfWork)

    def template_service(self) -> TemplateApplicationService:
        return TemplateApplicationService(YamlTemplateCatalog())

    def data_service(self) -> DataApplicationService:
        return DataApplicationService(DataQueryRepositoryImpl(), SqlAlchemyUnitOfWork)

    def upload_service(self) -> UploadApplicationService:
        return UploadApplicationService(
            repo=ParseJobRepositoryImpl(),
            template_repo=YamlTemplateCatalog(),
            data_sink=SqlAlchemyParsedDataSink(),
            event_publisher=domain_event_bus,
            uow_factory=SqlAlchemyUnitOfWork,
            file_storage=LocalUploadFileStorage(),
            workbook_reader=OpenPyxlWorkbookReader(),
        )

    def parse_job_repository(self) -> ParseJobRepositoryImpl:
        return ParseJobRepositoryImpl()


container = Container()
