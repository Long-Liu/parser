from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class PermissionRef(ValueObject):
    code: str
    name: str = ""


class Role(AggregateRoot):
    """Role aggregate — owns a set of permissions."""

    def __init__(
        self,
        role_id: int | None,
        code: str,
        name: str,
        description: str = "",
        permissions: list[PermissionRef] | None = None,
    ) -> None:
        super().__init__()
        self.id = role_id
        self._code = code
        self._name = name
        self.description = description
        self._permissions: dict[str, PermissionRef] = {
            p.code: p for p in (permissions or [])
        }

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def permissions(self) -> list[PermissionRef]:
        return list(self._permissions.values())

    @classmethod
    def create(
        cls, code: str, name: str, description: str = "",
        permissions: list[PermissionRef] | None = None,
    ) -> "Role":
        code = code.strip()
        name = name.strip()
        if not code:
            raise ValidationError("role code must not be empty")
        if not name:
            raise ValidationError("role name must not be empty")
        return cls(
            role_id=None, code=code, name=name,
            description=description.strip(), permissions=permissions,
        )

    def rename(self, name: str, description: str = "") -> None:
        name = name.strip()
        if not name:
            raise ValidationError("role name must not be empty")
        self._name = name
        self.description = description.strip()

    def has_permission(self, perm_code: str) -> bool:
        return perm_code in self._permissions

    def assign_permissions(self, permissions: list[PermissionRef]) -> None:
        self._permissions = {p.code: p for p in permissions}

    def add_permission(self, perm: PermissionRef) -> None:
        self._permissions[perm.code] = perm

    def remove_permission(self, perm_code: str) -> None:
        self._permissions.pop(perm_code, None)
