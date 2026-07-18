"""Auth bounded-context composition."""

from dataclasses import dataclass

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import AuthorizationApplicationService
from contexts.auth.application.project_access import ProjectAccessPolicy, ProjectAccessRepository
from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.domain.ports import PasswordHasher, TokenService
from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.repositories import RoleRepository, UserRepository
from contexts.shared.application.transaction import TransactionManager
from contexts.shared.domain.event_publisher import EventPublisher


@dataclass(frozen=True, slots=True)
class AuthComponents:
    auth: AuthApplicationService
    authorization: AuthorizationApplicationService
    users: UserApplicationService
    roles: RoleApplicationService
    project_access: ProjectAccessPolicy


def build_auth_components(
    users: UserRepository,
    roles: RoleRepository,
    project_access: ProjectAccessRepository,
    password_hasher: PasswordHasher,
    tokens: TokenService,
    events: EventPublisher,
    transactions: TransactionManager,
) -> AuthComponents:
    authentication = AuthenticationService(password_hasher)
    return AuthComponents(
        auth=AuthApplicationService(
            users, authentication, tokens, password_hasher, events, transactions,
        ),
        authorization=AuthorizationApplicationService(users, tokens),
        users=UserApplicationService(users, password_hasher, events, transactions),
        roles=RoleApplicationService(roles, events, users, transactions),
        project_access=ProjectAccessPolicy(project_access),
    )
