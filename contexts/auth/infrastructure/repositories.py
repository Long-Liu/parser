from __future__ import annotations

import sqlalchemy as sa

from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.models import User as OrmUser
from contexts.shared.infrastructure.database.models import Role as OrmRole
from contexts.shared.infrastructure.database.models import (
    UserRole,
    RolePermission,
    Permission as OrmPermission,
)
from contexts.shared.domain.identifiers import UserId, RoleId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.auth.domain.user import User, RoleRef
from contexts.auth.domain.role import Role, PermissionRef
from contexts.auth.domain.repositories import UserRepository, RoleRepository


def _user_to_entity(orm: OrmUser, roles: list[dict]) -> User:
    return User(
        user_id=UserId(orm.id), username=orm.username, password_hash=orm.password,
        real_name=orm.real_name or "", email=orm.email or "", phone=orm.phone or "",
        roles=[RoleRef(role_id=r["id"], code=r["code"]) for r in roles],
        is_active=bool(orm.is_active),
    )


def _role_to_entity(orm: OrmRole, perms: list[OrmPermission]) -> Role:
    return Role(
        role_id=RoleId(orm.id), code=orm.code, name=orm.name,
        permissions=[PermissionRef(code=p.code, name=p.name) for p in perms],
    )


def _get_session():
    """Return active session or create a new one."""
    s = current_session()
    if s is not None:
        return s, False
    return get_sessionmaker()(), True


class UserRepositoryImpl(UserRepository):
    async def save(self, user: User) -> None:
        session, owns = _get_session()
        try:
            values = {
                "username": user.username,
                "password": user.password_hash,
                "real_name": user.real_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": 1 if user.is_active else 0,
            }
            if user.id is None:
                orm = OrmUser(**values)
                session.add(orm)
                await session.flush()
                user.id = UserId(orm.id)
                return
            existing = await session.execute(
                sa.select(OrmUser.id).where(OrmUser.id == user.id.value)
            )
            if existing.first() is None:
                session.add(OrmUser(id=user.id.value, **values))
            else:
                await session.execute(
                    sa.update(OrmUser)
                    .where(OrmUser.id == user.id.value)
                    .values(**values)
                )
            await session.flush()
        finally:
            if owns:
                await session.close()

    async def find_by_id(self, user_id: UserId) -> User | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmUser).where(OrmUser.id == user_id.value))
            orm = result.scalars().first()
            if orm is None:
                return None
            roles = await self._load_roles(orm.id)
            return _user_to_entity(orm, roles)
        finally:
            if owns:
                await session.close()

    async def find_by_username(self, username: str) -> User | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmUser).where(OrmUser.username == username))
            orm = result.scalars().first()
            if orm is None:
                return None
            roles = await self._load_roles(orm.id)
            return _user_to_entity(orm, roles)
        finally:
            if owns:
                await session.close()

    async def get_permissions(self, user_id: UserId) -> set[str]:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmPermission.code)
                .select_from(OrmUser)
                .join(UserRole, UserRole.user_id == OrmUser.id)
                .join(RolePermission, RolePermission.role_id == UserRole.role_id)
                .join(OrmPermission, OrmPermission.id == RolePermission.permission_id)
                .where(OrmUser.id == user_id.value)
            )
            return {row[0] for row in result.all()}
        finally:
            if owns:
                await session.close()

    async def _load_roles(self, user_id: int) -> list[dict]:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmRole.id, OrmRole.code, OrmRole.name)
                .select_from(OrmRole)
                .join(UserRole, UserRole.role_id == OrmRole.id)
                .where(UserRole.user_id == user_id)
            )
            return [{"id": r[0], "code": r[1], "name": r[2]} for r in result.all()]
        finally:
            if owns:
                await session.close()


class RoleRepositoryImpl(RoleRepository):
    async def find_by_id(self, role_id: RoleId) -> Role | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmRole).where(OrmRole.id == role_id.value))
            orm = result.scalars().first()
            if orm is None:
                return None
            perms = await self._load_permissions(orm.id)
            return _role_to_entity(orm, perms)
        finally:
            if owns:
                await session.close()

    async def find_all(self) -> list[Role]:
        session, owns = _get_session()
        try:
            result = await session.execute(sa.select(OrmRole))
            orms = result.scalars().all()
            roles = []
            for orm in orms:
                perms = await self._load_permissions(orm.id)
                roles.append(_role_to_entity(orm, perms))
            return roles
        finally:
            if owns:
                await session.close()

    async def find_by_code(self, code: str) -> Role | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmRole).where(OrmRole.code == code))
            orm = result.scalars().first()
            if orm is None:
                return None
            perms = await self._load_permissions(orm.id)
            return _role_to_entity(orm, perms)
        finally:
            if owns:
                await session.close()

    async def _load_permissions(self, role_id: int) -> list[OrmPermission]:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmPermission)
                .select_from(OrmPermission)
                .join(RolePermission, RolePermission.permission_id == OrmPermission.id)
                .where(RolePermission.role_id == role_id)
            )
            return list(result.scalars().all())
        finally:
            if owns:
                await session.close()
