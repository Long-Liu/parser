from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import RoleId


@dataclass(frozen=True)
class PermissionRef(ValueObject):
    code: str
    name: str


class Role(AggregateRoot):
    def __init__(self, role_id: RoleId, code: str, name: str,
                 permissions: list[PermissionRef] | None = None) -> None:
        super().__init__()
        self.id = role_id
        self.code = code
        self.name = name
        self.permissions: list[PermissionRef] = permissions or []

    def has_permission(self, perm_code: str) -> bool:
        return any(p.code == perm_code for p in self.permissions)

    def assign_permissions(self, permissions: list[PermissionRef]) -> None:
        self.permissions = permissions
