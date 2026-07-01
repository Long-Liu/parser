import sqlalchemy as sa
from sqlalchemy.dialects.mysql import insert as mysql_insert

from db.engine import get_sessionmaker
from db.models import Permission, Role, RolePermission, User, UserRole
from db.primitives import current_session, transactional
from db.tables import users, user_roles, roles, role_permissions, permissions
from repositories.base import BaseRepo


class UserRepo(BaseRepo):
    model = User

    @staticmethod
    async def _read(stmt):
        session = current_session()
        if session is not None:
            return await session.execute(stmt)
        async with get_sessionmaker()() as session:
            return await session.execute(stmt)

    @staticmethod
    async def _write(stmt, params=None):
        session = current_session()
        if session is not None:
            return await session.execute(stmt, params if params is not None else {})
        async with get_sessionmaker().begin() as session:
            return await session.execute(stmt, params if params is not None else {})

    @classmethod
    async def get_by_username(cls, username: str) -> dict | None:
        return await cls.get(users.c.username == username)

    @classmethod
    @transactional
    async def register(cls, username: str, password: str,
                       real_name: str | None = None, email: str | None = None,
                       phone: str | None = None) -> tuple[int, str]:
        """Create a user and assign a role in one transaction.

        Returns (user_id, role_code). First user becomes admin; all others viewer.
        """
        uid = await cls.insert(
            username=username, password=password,
            real_name=real_name, email=email, phone=phone,
        )
        user_count = await cls._count_for_update()
        role_code = "admin" if user_count == 1 else "viewer"
        await UserRoleRepo.grant(uid, role_code)
        return uid, role_code

    @classmethod
    async def get_permissions(cls, user_id: int) -> frozenset[str]:
        """Return the set of permission codes for a user (3-table JOIN)."""
        result = await cls._read(
            sa.select(permissions.c.code)
            .select_from(
                user_roles
                .join(role_permissions, user_roles.c.role_id == role_permissions.c.role_id)
                .join(permissions, role_permissions.c.permission_id == permissions.c.id)
            )
            .where(user_roles.c.user_id == user_id)
        )
        return frozenset(result.scalars().all())

    @classmethod
    async def _count_for_update(cls) -> int:
        """Count all users with FOR UPDATE lock — internal, use inside Transaction."""
        stmt = sa.select(sa.func.count().label("cnt")).select_from(users).with_for_update()
        result = await cls._read(stmt)
        return result.scalar() or 0


class RoleRepo(BaseRepo):
    model = Role


class PermissionRepo(BaseRepo):
    model = Permission


class UserRoleRepo(BaseRepo):
    model = UserRole

    @classmethod
    async def grant(cls, user_id: int, role_code: str):
        """Assign a role to a user via INSERT IGNORE ... SELECT."""
        sel = sa.select(
            sa.literal(user_id).label("user_id"), roles.c.id.label("role_id")
        ).where(roles.c.code == role_code)
        await cls._write(
            mysql_insert(user_roles).prefix_with("IGNORE").from_select(
                ["user_id", "role_id"], sel
            )
        )

    @classmethod
    async def grant_to_user(cls, username: str, role_code: str):
        """Grant a role by username and role code."""
        sel = sa.select(users.c.id, roles.c.id).where(
            sa.and_(users.c.username == username, roles.c.code == role_code)
        )
        await cls._write(
            mysql_insert(user_roles).prefix_with("IGNORE").from_select(
                ["user_id", "role_id"], sel
            )
        )


class RolePermissionRepo(BaseRepo):
    model = RolePermission

    @classmethod
    async def grant(cls, role_code: str, perm_code: str):
        """Grant a permission to a role via INSERT IGNORE ... SELECT."""
        sel = sa.select(roles.c.id, permissions.c.id).where(
            sa.and_(roles.c.code == role_code, permissions.c.code == perm_code)
        )
        await cls._write(
            mysql_insert(role_permissions).prefix_with("IGNORE").from_select(
                ["role_id", "permission_id"], sel
            )
        )
