from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_domain_event import DomainEvent


@dataclass(frozen=True)
class UserRegistered(DomainEvent):
    username: str = ""
    real_name: str = ""


@dataclass(frozen=True)
class UserStatusChanged(DomainEvent):
    username: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class UserDeleted(DomainEvent):
    username: str = ""


@dataclass(frozen=True)
class UserProfileUpdated(DomainEvent):
    username: str = ""
    changed_fields: list[str] = ()


@dataclass(frozen=True)
class UserPasswordReset(DomainEvent):
    username: str = ""


@dataclass(frozen=True)
class UserRolesAssigned(DomainEvent):
    username: str = ""
    role_count: int = 0


@dataclass(frozen=True)
class RoleCreated(DomainEvent):
    code: str = ""
    name: str = ""


@dataclass(frozen=True)
class RolePermissionsChanged(DomainEvent):
    code: str = ""
    permission_count: int = 0
