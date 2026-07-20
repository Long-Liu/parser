"""Typed services made available to request middleware."""

from dataclasses import dataclass

from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.application.project_access import ProjectAccessPolicy


@dataclass(frozen=True, slots=True)
class RequestServices:
    authorization: AuthorizationApplicationService
    project_access: ProjectAccessPolicy
