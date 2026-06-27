import sqlalchemy as sa

from db.connection import execute, fetch_all, Transaction
from db.tables import users, user_roles, roles, role_permissions, permissions
from repositories.base import BaseRepo


class UserRepo(BaseRepo):
    table = users

    @classmethod
    async def get_by_username(cls, username: str) -> dict | None:
        return await cls.get(users.c.username == username)

    @classmethod
    async def get_by_id(cls, user_id: int) -> dict | None:
        return await cls.get(users.c.id == user_id)

    @classmethod
    async def register(cls, username: str, password: str,
                       real_name: str | None = None, email: str | None = None,
                       phone: str | None = None) -> tuple[int, str]:
        """Create a user and assign a role in one transaction.

        Returns (user_id, role_code). First user becomes admin; all others viewer.
        """
        async with Transaction():
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
        rows = await fetch_all(
            sa.select(permissions.c.code)
            .select_from(
                user_roles
                .join(role_permissions, user_roles.c.role_id == role_permissions.c.role_id)
                .join(permissions, role_permissions.c.permission_id == permissions.c.id)
            )
            .where(user_roles.c.user_id == user_id)
        )
        return frozenset(r["code"] for r in rows)

    @classmethod
    async def _count_for_update(cls) -> int:
        """Count all users with FOR UPDATE lock — internal, use inside Transaction."""
        row = await (await execute(
            sa.select(sa.func.count().label("cnt")).select_from(users).with_for_update()
        )).fetchone()
        return row[0] if row else 0


class RoleRepo(BaseRepo):
    table = roles


class PermissionRepo(BaseRepo):
    table = permissions


class UserRoleRepo(BaseRepo):
    table = user_roles

    @classmethod
    async def grant(cls, user_id: int, role_code: str):
        """Assign a role to a user via INSERT IGNORE ... SELECT."""
        sel = sa.select(
            sa.literal(user_id).label("user_id"), roles.c.id.label("role_id")
        ).where(roles.c.code == role_code)
        await execute(
            user_roles.insert().prefix_with("IGNORE").from_select(
                ["user_id", "role_id"], sel
            )
        )

    @classmethod
    async def grant_to_user(cls, username: str, role_code: str):
        """Grant a role by username and role code."""
        sel = sa.select(users.c.id, roles.c.id).where(
            sa.and_(users.c.username == username, roles.c.code == role_code)
        )
        await execute(
            user_roles.insert().prefix_with("IGNORE").from_select(
                ["user_id", "role_id"], sel
            )
        )


class RolePermissionRepo(BaseRepo):
    table = role_permissions

    @classmethod
    async def grant(cls, role_code: str, perm_code: str):
        """Grant a permission to a role via INSERT IGNORE ... SELECT."""
        sel = sa.select(roles.c.id, permissions.c.id).where(
            sa.and_(roles.c.code == role_code, permissions.c.code == perm_code)
        )
        await execute(
            role_permissions.insert().prefix_with("IGNORE").from_select(
                ["role_id", "permission_id"], sel
            )
        )
