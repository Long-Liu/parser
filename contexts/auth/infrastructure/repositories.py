from __future__ import annotations

import sqlalchemy as sa
from contexts.shared.infrastructure.database.engine import get_sessionmaker
from contexts.shared.infrastructure.database.tables import User as OrmUser
from contexts.shared.infrastructure.database.tables import Role as OrmRole
from contexts.shared.infrastructure.database.tables import (
    UserRole,
    RolePermission,
    Permission as OrmPermission,
)
from contexts.shared.domain.identifiers import RoleId, UserId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.auth.domain.user import User, RoleRef
from contexts.auth.domain.role import PermissionRef, Role
from contexts.auth.domain.repositories import RoleRepository, UserRepository


def _user_to_entity(orm: OrmUser, roles: list[dict]) -> User:
    return User(
        user_id=UserId(orm.id), username=orm.username, password_hash=orm.password,
        real_name=orm.real_name or "", email=orm.email or "", phone=orm.phone or "",
        roles=[RoleRef(role_id=r["id"], code=r["code"]) for r in roles],
        is_active=bool(orm.is_active),
    )


def _get_session():
    """Return active session or create a new one."""
    s = current_session()
    if s is not None:
        return s, False
    return get_sessionmaker()(), True


async def _load_roles(session, user_id: int) -> list[dict]:
    result = await session.execute(
        sa.select(OrmRole.id, OrmRole.code, OrmRole.name)
        .select_from(OrmRole)
        .join(UserRole, UserRole.role_id == OrmRole.id)
        .where(UserRole.user_id == user_id)
    )
    return [{"id": r[0], "code": r[1], "name": r[2]} for r in result.all()]


# ── User repository ──────────────────────────────────────────────────

class UserRepositoryImpl(UserRepository):
    async def save(self, user: User) -> None:
        session = current_session()
        if session is None:
            raise RuntimeError("UserRepository.save requires an active UnitOfWork")
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

    async def find_by_id(self, user_id: UserId) -> User | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmUser).where(OrmUser.id == user_id.value))
            orm = result.scalars().first()
            if orm is None:
                return None
            roles = await _load_roles(session, orm.id)
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
            roles = await _load_roles(session, orm.id)
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


# ── Role repository ──────────────────────────────────────────────────

class RoleRepositoryImpl(RoleRepository):
    async def save(self, role: Role) -> None:
        session = current_session()
        if session is None:
            raise RuntimeError("RoleRepository.save requires an active UnitOfWork")
        values = {"code": role.code, "name": role.name,
                   "description": role.description}
        if role.id is None:
            orm = OrmRole(**values)
            session.add(orm)
            await session.flush()
            role.id = orm.id
        else:
            await session.execute(
                sa.update(OrmRole).where(OrmRole.id == role.id).values(**values)
            )
            await session.execute(
                sa.delete(RolePermission.__table__).where(
                    RolePermission.__table__.c.role_id == role.id
                )
            )
        await session.flush()

        for perm in role.permissions:
            perm_id = await _ensure_permission(session, perm.code, perm.name)
            await session.execute(
                sa.insert(RolePermission.__table__).values(
                    role_id=role.id, permission_id=perm_id,
                ).prefix_with("IGNORE")
            )

    async def find_by_id(self, role_id: RoleId) -> Role | None:
        session, owns = _get_session()
        try:
            result = await session.execute(
                sa.select(OrmRole).where(OrmRole.id == role_id.value)
            )
            orm = result.scalars().first()
            if orm is None:
                return None
            perms = await _load_permissions(session, orm.id)
            return Role(
                role_id=orm.id, code=orm.code, name=orm.name,
                description=orm.description or "",
                permissions=[PermissionRef(code=p.code, name=p.name) for p in perms],
            )
        finally:
            if owns:
                await session.close()

    async def find_all(self) -> list[Role]:
        session, owns = _get_session()
        try:
            result = await session.execute(sa.select(OrmRole))
            roles = []
            for orm in result.scalars().all():
                perms = await _load_permissions(session, orm.id)
                roles.append(Role(
                    role_id=orm.id, code=orm.code, name=orm.name,
                    description=orm.description or "",
                    permissions=[
                        PermissionRef(code=p.code, name=p.name) for p in perms
                    ],
                ))
            return roles
        finally:
            if owns:
                await session.close()

    async def delete(self, role_id: RoleId) -> None:
        session = current_session()
        if session is None:
            raise RuntimeError("RoleRepository.delete requires an active UnitOfWork")
        await session.execute(
            sa.delete(RolePermission.__table__).where(
                RolePermission.__table__.c.role_id == role_id.value
            )
        )
        await session.execute(
            sa.delete(UserRole.__table__).where(
                UserRole.__table__.c.role_id == role_id.value
            )
        )
        await session.execute(
            sa.delete(OrmRole.__table__).where(
                OrmRole.__table__.c.id == role_id.value
            )
        )

    async def assign_to_user(self, user_id: UserId, role_id: RoleId) -> None:
        session = current_session()
        if session is None:
            raise RuntimeError(
                "RoleRepository.assign_to_user requires an active UnitOfWork"
            )
        await session.execute(
            sa.insert(UserRole.__table__).values(
                user_id=user_id.value, role_id=role_id.value,
            ).prefix_with("IGNORE")
        )

    async def remove_from_user(self, user_id: UserId, role_id: RoleId) -> None:
        session = current_session()
        if session is None:
            raise RuntimeError(
                "RoleRepository.remove_from_user requires an active UnitOfWork"
            )
        await session.execute(
            sa.delete(UserRole.__table__).where(
                sa.and_(
                    UserRole.__table__.c.user_id == user_id.value,
                    UserRole.__table__.c.role_id == role_id.value,
                )
            )
        )


async def _ensure_permission(session, code: str, name: str) -> int:
    """Get or create a permission row; return its id."""
    result = await session.execute(
        sa.select(OrmPermission.id).where(OrmPermission.code == code)
    )
    row = result.first()
    if row is not None:
        return row[0]
    result = await session.execute(
        sa.insert(OrmPermission.__table__).values(code=code, name=name)
    )
    return result.lastrowid


async def _load_permissions(session, role_id: int) -> list[OrmPermission]:
    result = await session.execute(
        sa.select(OrmPermission)
        .select_from(OrmPermission)
        .join(RolePermission, RolePermission.permission_id == OrmPermission.id)
        .where(RolePermission.role_id == role_id)
    )
    return list(result.scalars().all())
