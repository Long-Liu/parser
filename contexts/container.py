from __future__ import annotations

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.auth.infrastructure.repositories import RoleRepositoryImpl, UserRepositoryImpl
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
    """Poor man's DI — stateless services are singletons; UoW factory is the class itself."""

    def __init__(self) -> None:
        # Stateless singletons
        self._password_hasher = BCryptPasswordHasher()
        self._user_repo = UserRepositoryImpl()
        self._role_repo = RoleRepositoryImpl()
        self._project_repo = ProjectRepositoryImpl()
        self._template_repo = YamlTemplateCatalog()
        self._data_repo = DataQueryRepositoryImpl()
        self._parse_job_repo = ParseJobRepositoryImpl()
        self._data_sink = SqlAlchemyParsedDataSink()
        self._file_storage = LocalUploadFileStorage()
        self._workbook_reader = OpenPyxlWorkbookReader()
        # JWT secret is set at startup
        self._jwt_service: JwtService | None = None

    def configure(self, secret_key: str) -> None:
        """Called once at startup with the application secret key."""
        self._jwt_service = JwtService(secret_key)

    def _require_jwt(self) -> JwtService:
        if self._jwt_service is None:
            raise RuntimeError("Container.configure() must be called at startup")
        return self._jwt_service

    def authentication_service(self) -> AuthApplicationService:
        return AuthApplicationService(
            user_repo=self._user_repo,
            auth_service=AuthenticationService(self._password_hasher),
            jwt_service=self._require_jwt(),
            password_hasher=self._password_hasher,
            uow_factory=SqlAlchemyUnitOfWork,
        )

    def request_authorization_service(self) -> AuthorizationApplicationService:
        return AuthorizationApplicationService(
            user_repo=self._user_repo,
            jwt_service=self._require_jwt(),
        )

    def project_service(self) -> ProjectApplicationService:
        return ProjectApplicationService(self._project_repo, SqlAlchemyUnitOfWork)

    def template_service(self) -> TemplateApplicationService:
        return TemplateApplicationService(self._template_repo)

    def data_service(self) -> DataApplicationService:
        return DataApplicationService(self._data_repo, SqlAlchemyUnitOfWork)

    def upload_service(self) -> UploadApplicationService:
        return UploadApplicationService(
            repo=self._parse_job_repo,
            template_repo=self._template_repo,
            data_sink=self._data_sink,
            event_publisher=domain_event_bus,
            uow_factory=SqlAlchemyUnitOfWork,
            file_storage=self._file_storage,
            workbook_reader=self._workbook_reader,
        )

    def role_service(self) -> RoleApplicationService:
        return RoleApplicationService(self._role_repo, SqlAlchemyUnitOfWork)

    def parse_job_repository(self) -> ParseJobRepositoryImpl:
        return self._parse_job_repo


container = Container()
