from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.auth.domain.events import UserRegistered, UserStatusChanged


@dataclass(frozen=True)
class RoleRef(ValueObject):
    role_id: int
    code: str


class User(AggregateRoot[UserId]):
    def __init__(self, user_id: UserId | None, username: str, password_hash: str,
                 real_name: str = "", email: str = "", phone: str = "",
                 roles: list[RoleRef] | None = None, is_active: bool = True) -> None:
        super().__init__()
        self.id = user_id
        self._username = username
        self._password_hash = password_hash
        self.real_name = real_name
        self._email = email
        self.phone = phone
        self.roles: list[RoleRef] = roles or []
        self.is_active = is_active

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def email(self) -> str:
        return self._email

    def disable(self) -> None:
        self.is_active = False
        self.record(UserStatusChanged(
            aggregate_id=self.id.value if self.id else None,
            username=self._username, is_active=False,
        ))

    def enable(self) -> None:
        self.is_active = True
        self.record(UserStatusChanged(
            aggregate_id=self.id.value if self.id else None,
            username=self._username, is_active=True,
        ))

    def assign_roles(self, roles: list[RoleRef]) -> None:
        self.roles = roles

    @classmethod
    def create(cls, user_id: UserId | None, username: str, password_hash: str,
               real_name: str = "", email: str = "", phone: str = "") -> "User":
        username = username.strip()
        email = email.strip()
        if not username:
            raise ValidationError("username must not be empty")
        if not password_hash:
            raise ValidationError("password hash must not be empty")
        if email and "@" not in email:
            raise ValidationError("email must be valid")
        user = cls(user_id=user_id, username=username, password_hash=password_hash,
                   real_name=real_name.strip(), email=email, phone=phone.strip(),
                   roles=[], is_active=True)
        user.record(UserRegistered(
            aggregate_id=user_id.value if user_id else None,
            username=username, real_name=real_name.strip(),
        ))
        return user


def _demo():
    uid = UserId(1)
    user = User.create(uid, "alice", "hash123", real_name="Alice")
    assert user.username == "alice"
    assert user.is_active is True
    assert len(user.pull_events()) == 1  # UserRegistered
    user.disable()
    assert user.is_active is False
    assert len(user.pull_events()) == 1  # UserStatusChanged
    assert len(user.pull_events()) == 0  # drained
    print("user: OK")


if __name__ == "__main__":
    _demo()
