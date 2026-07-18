from __future__ import annotations

from dataclasses import dataclass

from contexts.auth.domain.events import (
    UserPasswordReset,
    UserProfileUpdated,
    UserRegistered,
    UserRolesAssigned,
    UserStatusChanged,
    UserDeleted,
)
from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.auth.domain.email import Email
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.auth.domain.phone import Phone


@dataclass(frozen=True)
class RoleRef(ValueObject):
    role_id: int
    code: str
    name: str = ""


class User(AggregateRoot[UserId]):
    def __init__(self, user_id: UserId | None, username: str, password_hash: str,
                 real_name: str = "", email: str = "", phone: str = "",
                 department: str = "",
                 roles: list[RoleRef] | None = None, is_active: bool = True) -> None:
        super().__init__()
        self.id = user_id
        self._username = username
        self._password_hash = password_hash
        self._real_name = real_name
        self._email = Email(email)
        self._phone = Phone(phone)
        self._department = department
        self._roles: list[RoleRef] = roles or []
        self._is_active = is_active

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def email(self) -> str:
        return str(self._email)

    @property
    def real_name(self) -> str:
        return self._real_name

    @property
    def phone(self) -> str:
        return str(self._phone)

    @property
    def department(self) -> str:
        return self._department

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def roles(self) -> list[RoleRef]:
        return list(self._roles)

    def disable(self) -> None:
        self._is_active = False
        self.record(UserStatusChanged(
            aggregate_id=self.id.value if self.id else None,
            username=self._username, is_active=False,
        ))

    def enable(self) -> None:
        self._is_active = True
        self.record(UserStatusChanged(
            aggregate_id=self.id.value if self.id else None,
            username=self._username, is_active=True,
        ))

    def mark_deleted(self) -> None:
        self.record(UserDeleted(
            aggregate_id=self.id.value if self.id else None,
            username=self._username,
        ))

    def assign_roles(self, roles: list[RoleRef]) -> None:
        self._roles = list(roles)
        self.record(UserRolesAssigned(
            aggregate_id=self.id.value if self.id else None,
            username=self._username, role_count=len(roles),
        ))

    def update_profile(self, *, real_name: str | None = None,
                       email: str | None = None, phone: str | None = None,
                       department: str | None = None,
                       is_active: bool | None = None) -> None:
        changed = []
        if real_name is not None:
            self._real_name = real_name.strip()
            changed.append("real_name")
        if email is not None:
            self._email = Email(email)
            changed.append("email")
        if phone is not None:
            self._phone = Phone(phone)
            changed.append("phone")
        if department is not None:
            self._department = department.strip()
            changed.append("department")
        if is_active is not None:
            self.enable() if is_active else self.disable()
            changed.append("is_active")
        if changed:
            self.record(UserProfileUpdated(
                aggregate_id=self.id.value if self.id else None,
                username=self._username, changed_fields=changed,
            ))

    def reset_password(self, password_hash: str) -> None:
        if not password_hash:
            raise ValidationError("password hash must not be empty")
        self._password_hash = password_hash
        self.record(UserPasswordReset(
            aggregate_id=self.id.value if self.id else None,
            username=self._username,
        ))

    @classmethod
    def create(cls, user_id: UserId | None, username: str, password_hash: str,
               real_name: str = "", email: str = "", phone: str = "",
               department: str = "") -> "User":
        username = username.strip()
        email = email.strip()
        if not username:
            raise ValidationError("username must not be empty")
        if not password_hash:
            raise ValidationError("password hash must not be empty")
        user = cls(user_id=user_id, username=username, password_hash=password_hash,
                   real_name=real_name.strip(), email=email, phone=phone.strip(),
                   department=department.strip(),
                   roles=[], is_active=True)
        user.record(UserRegistered(
            aggregate_id=user_id.value if user_id else None,
            username=username, real_name=real_name.strip(),
        ))
        return user
