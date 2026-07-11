from __future__ import annotations

import typing
from typing import Generic, TypeVar, get_origin

from contexts.analytics.application.analytics_service import AnalyticsApplicationService
from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.analytics.infrastructure.ai_provider import HttpAIAnalysisProvider
from contexts.analytics.infrastructure.analytics_repository import TortoiseAnalyticsRepository
from contexts.analytics.domain.repositories import AnalyticsRepository
from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.application.security import PasswordHasher, TokenService
from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.application.project_access import ProjectAccessPolicy, ProjectAccessRepository
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.auth.infrastructure.repositories import (
    RoleRepositoryImpl,
    UserRepositoryImpl,
)
from contexts.auth.infrastructure.project_access_repository import TortoiseProjectAccessRepository
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.infrastructure.repositories import DataQueryRepositoryImpl
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.parsing.infrastructure.data_writer import TortoiseParsedDataSink
from contexts.parsing.infrastructure.file_storage import LocalUploadFileStorage
from contexts.parsing.infrastructure.repositories import (
    ParseJobRepositoryImpl,
    UploadPreviewRepositoryImpl,
)
from contexts.parsing.infrastructure.workbook_reader import OpenPyxlWorkbookReader
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.infrastructure.repositories import (
    ProjectDataCleanupImpl,
    ProjectNotificationAdapter,
    ProjectRepositoryImpl,
    TortoiseUserDirectory,
)
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.infrastructure.domain_event_bus import domain_event_bus
from contexts.shared.application.transaction import configure_transaction_manager
from contexts.shared.infrastructure.database.transaction import TortoiseTransactionManager
from contexts.template.application.template_app_service import (
    TemplateApplicationService,
)
from contexts.template.infrastructure.repositories import YamlTemplateCatalog

T = TypeVar("T")


class CircularDependencyError(RuntimeError):
    """Raised when auto-wire detects unresolvable dependencies."""


class Container:
    """Stdlib-only DI container — Spring-style ``get(Cls)`` with auto-wiring.

    Constructor params are resolved by type from the registry via
    ``inspect.signature``.  Non-class values (module singletons, factories)
    are pre-registered explicitly.

    Usage::

        # register singletons & interface bindings
        container.register_instance(my_instance)
        container.bind(AbstractRepo, MyRepoImpl)

        # queue a class for auto-wire construction
        container.register_factory(MyApplicationService)

        # build everything at startup
        container.wire()

        # retrieve anywhere
        svc = container.get(MyApplicationService)
    """

    def __init__(self) -> None:
        self._registry: dict[type, object] = {}
        self._pending: list[type] = []

    # ── public API ────────────────────────────────────────────────────────

    def register_instance(self, instance: object) -> None:
        """Register *instance* under its concrete type."""
        self._registry[type(instance)] = instance

    def bind(self, abstract: type, instance: object) -> None:
        """Register *instance* under an abstract type or interface."""
        self._registry[abstract] = instance

    def register_factory(self, cls: type) -> None:
        """Queue *cls* for auto-wire construction during ``wire()``."""
        self._pending.append(cls)

    def wire(self) -> None:
        """Construct all pending factories, resolving constructor deps from the registry.

        Iterates until all are built or no progress is made (circular dep).
        """
        remaining = list(self._pending)
        self._pending.clear()
        while remaining:
            progress = False
            retry = []
            for cls in remaining:
                if self._try_construct(cls):
                    progress = True
                else:
                    retry.append(cls)
            if not progress:
                names = ", ".join(c.__name__ for c in retry)
                raise CircularDependencyError(
                    f"Cannot resolve dependencies for: {names}"
                )
            remaining = retry

    def configure(self, secret_key: str) -> None:
        """Called once at startup — registers JWT-dependent services and wires them."""
        jwt = JwtService(secret_key)
        self.register_instance(jwt)
        self.bind(TokenService, jwt)
        for cls in _container_auth:
            self.register_factory(cls)
        self.wire()

    def get(self, cls: type[T]) -> T:
        """Return the singleton registered for *cls*."""
        try:
            return self._registry[cls]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"{cls.__name__} not registered. "
                f"Ensure container.wire() has been called."
            ) from None

    def resolve(self, cls: type[T]) -> T:
        """Auto-wire and return an instance of *cls*.

        Unlike ``get()``, this constructs *cls* on the spot, resolving its
        constructor arguments from the registry.  The instance is cached so
        repeated calls return the same singleton.
        """
        existing = self._registry.get(cls)
        if existing is not None:
            return existing  # type: ignore[return-value]
        if not self._try_construct(cls):
            raise KeyError(
                f"Cannot resolve {cls.__name__} — missing dependencies"
            )
        return self._registry[cls]  # type: ignore[return-value]

    # ── internal ──────────────────────────────────────────────────────────

    def _try_construct(self, cls: type) -> bool:
        """Attempt to build *cls*; return True on success, False if deps missing."""
        try:
            kwargs = self._resolve_deps(cls)
        except _Missing:
            return False
        self._registry[cls] = cls(**kwargs)
        return True

    def _resolve_deps(self, cls: type) -> dict[str, object]:
        """Return kwargs dict for *cls*'s ``__init__``, resolved from registry.

        Uses ``typing.get_type_hints`` to resolve string annotations (PEP 563).
        """
        kwargs: dict[str, object] = {}
        try:
            hints = typing.get_type_hints(cls.__init__, include_extras=True)
        except Exception:
            hints = {}
        for name, ann in hints.items():
            if name == "return":
                continue
            dep = self._lookup(ann)
            if dep is None:
                raise _Missing(ann)
            kwargs[name] = dep
        return kwargs

    def _lookup(self, ann: type) -> object | None:
        """Resolve a type annotation to a registered instance.

        1. Exact match.
        2. Union ``X | None`` — take the non-None arm.
        """
        # 1. Exact match
        result = self._registry.get(ann)
        if result is not None:
            return result

        # 2. Union X | None → try X
        origin = get_origin(ann)
        if origin is not None and origin is not Generic:
            args = getattr(ann, "__args__", ())
            for arg in args:
                if arg is not type(None):  # noqa: E721
                    result = self._registry.get(arg)
                    if result is not None:
                        return result
        return None


class _Missing(Exception):
    """Internal sentinel — dependency not yet available."""


# ── module-level singleton ───────────────────────────────────────────────

container = Container()
configure_transaction_manager(TortoiseTransactionManager())


def _reg(instance: object) -> None:
    container.register_instance(instance)


def _bind(abstract: type, concrete: object) -> None:
    container.bind(abstract, concrete)


# ── infrastructure singletons ────────────────────────────────────────────

_container_pw = BCryptPasswordHasher()
_reg(_container_pw)
_bind(PasswordHasher, _container_pw)
_reg(AuthenticationService(_container_pw))
_reg(_user_repo := UserRepositoryImpl())
_reg(_role_repo := RoleRepositoryImpl())
_reg(_project_access_repo := TortoiseProjectAccessRepository())
_reg(_project_repo := ProjectRepositoryImpl())
_reg(_project_cleanup := ProjectDataCleanupImpl())
_reg(_user_directory := TortoiseUserDirectory())
_reg(_project_notifications := ProjectNotificationAdapter())
_reg(_template_catalog := YamlTemplateCatalog())
_reg(_data_repo := DataQueryRepositoryImpl())
_reg(_parse_job_repo := ParseJobRepositoryImpl())
_reg(_preview_repo := UploadPreviewRepositoryImpl())
_reg(_data_sink := TortoiseParsedDataSink())
_reg(_file_storage := LocalUploadFileStorage())
_reg(_workbook_reader := OpenPyxlWorkbookReader())
_reg(_ai_provider := HttpAIAnalysisProvider())
_reg(_analytics_repo := TortoiseAnalyticsRepository(_ai_provider))

# ── interface bindings (abstract → concrete) ─────────────────────────────

from contexts.auth.domain.repositories import (  # noqa: E402
    RoleRepository,
    UserRepository,
)
from contexts.data.domain.repositories import DataQueryRepository  # noqa: E402
from contexts.parsing.application.file_storage import FileStorage  # noqa: E402
from contexts.parsing.domain.data_sink import ParsedDataSink  # noqa: E402
from contexts.parsing.domain.repositories import (  # noqa: E402
    ParseJobRepository,
    UploadPreviewRepository,
)
from contexts.parsing.domain.workbook import WorkbookReader  # noqa: E402
from contexts.project.domain.repositories import (  # noqa: E402
    ProjectDataCleanup,
    ProjectNotificationPort,
    ProjectRepository,
    UserDirectory,
)
from contexts.template.domain.repositories import TemplateCatalog  # noqa: E402

_bind(UserRepository, _user_repo)
_bind(RoleRepository, _role_repo)
_bind(ProjectAccessRepository, _project_access_repo)
_bind(ProjectRepository, _project_repo)
_bind(ProjectDataCleanup, _project_cleanup)
_bind(UserDirectory, _user_directory)
_bind(ProjectNotificationPort, _project_notifications)
_bind(TemplateCatalog, _template_catalog)
_bind(DataQueryRepository, _data_repo)
_bind(ParseJobRepository, _parse_job_repo)
_bind(UploadPreviewRepository, _preview_repo)
_bind(ParsedDataSink, _data_sink)
_bind(FileStorage, _file_storage)
_bind(WorkbookReader, _workbook_reader)
_bind(EventPublisher, domain_event_bus)
_bind(AIAnalysisPort, _ai_provider)
_bind(AnalyticsRepository, _analytics_repo)

# ── application services (auto-wired via inspect) ────────────────────────

container.register_factory(ProjectApplicationService)
container.register_factory(TemplateApplicationService)
container.register_factory(DataApplicationService)
container.register_factory(UploadApplicationService)
container.register_factory(RoleApplicationService)
container.register_factory(UserApplicationService)
container.register_factory(ProjectAccessPolicy)
container.register_factory(AnalyticsApplicationService)

# Jwt-dependent — deferred to configure()
_container_auth: list[type] = [AuthApplicationService, AuthorizationApplicationService]

container.wire()
