"""Regression tests for role management (role creation was broken by a dead
raise in TortoiseRoleRepository.save)."""

import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.auth.application.role_app_service import RoleApplicationService
from contexts.auth.infrastructure.repositories import TortoiseRoleRepository, TortoiseUserRepository
from contexts.auth.infrastructure.tables import (
    Permission as OrmPermission,
)
from contexts.auth.infrastructure.tables import (
    Role as OrmRole,
)
from contexts.auth.infrastructure.tables import (
    User as OrmUser,
)
from contexts.auth.infrastructure.tables import (
    RolePermission,
)
from contexts.auth.infrastructure.tables import (
    UserRole,
)
from contexts.shared.domain.exceptions import ConflictError
from contexts.shared.domain.identifiers import RoleId, UserId

# noinspection PyProtectedMember
from contexts.shared.infrastructure.database.engine import _MODEL_MODULES


@pytest.fixture
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": list(_MODEL_MODULES)},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


async def _service() -> RoleApplicationService:
    return RoleApplicationService(repo=TortoiseRoleRepository())


async def test_create_role_persists_and_assigns_id(db):
    service = await _service()
    result = await service.create(
        code="editor",
        name="Editor",
        description="can edit data",
        permission_codes=["data:read", "data:write"],
    )
    assert result["id"] is not None
    assert result["code"] == "editor"

    orm = await OrmRole.get(code="editor")
    assert orm.name == "Editor"
    assert orm.description == "can edit data"

    # Permissions are created and linked to the role.
    perm_ids = await RolePermission.filter(role_id=orm.id).values_list("permission_id", flat=True)
    codes = {
        code
        for code in await OrmPermission.filter(id__in=list(perm_ids)).values_list("code", flat=True)
    }
    assert codes == {"data:read", "data:write"}


async def test_create_role_duplicate_code_raises_conflict(db):
    service = await _service()
    await service.create(code="admin", name="Admin")
    with pytest.raises(ConflictError):
        await service.create(code="admin", name="Another Admin")


async def test_create_role_roundtrip_via_repo(db):
    service = await _service()
    created = await service.create(
        code="viewer",
        name="Viewer",
        permission_codes=["data:read"],
    )
    repo = TortoiseRoleRepository()
    found = await repo.find_by_id(RoleId(created["id"]))
    assert found is not None
    assert found.code == "viewer"
    assert {p.code for p in found.permissions} == {"data:read"}


async def test_set_user_roles_replaces_role_set_in_bulk(db):
    role_a = await OrmRole.create(code="editor", name="Editor")
    role_b = await OrmRole.create(code="reviewer", name="Reviewer")
    user = await OrmUser.create(username="dave", password="hash")

    repo = TortoiseRoleRepository()
    await repo.set_user_roles(UserId(user.id), [role_a.id, role_b.id])
    ids = set(
        await UserRole.filter(user_id=user.id).values_list("role_id", flat=True)
    )
    assert ids == {role_a.id, role_b.id}

    # Replacing shrinks the set (delete + create, not accumulation).
    await repo.set_user_roles(UserId(user.id), [role_b.id])
    ids = set(
        await UserRole.filter(user_id=user.id).values_list("role_id", flat=True)
    )
    assert ids == {role_b.id}

    # Empty assignment clears all roles.
    await repo.set_user_roles(UserId(user.id), [])
    assert await UserRole.filter(user_id=user.id).count() == 0


async def test_role_write_invalidates_shared_permission_cache(db):
    """Role changes must take effect immediately for cached permission lookups:
    the user and role repositories share one permission cache in production."""
    user = await OrmUser.create(username="erin", password="hash")
    role = await OrmRole.create(code="admin", name="admin")
    await UserRole.create(user_id=user.id, role_id=role.id)
    permission = await OrmPermission.create(code="user:manage", name="User manage")
    await RolePermission.create(role_id=role.id, permission_id=permission.id)

    cache: dict = {}
    user_repo = TortoiseUserRepository(cache)
    role_repo = TortoiseRoleRepository(cache)

    assert await user_repo.get_permissions(UserId(user.id)) == {"user:manage"}

    # Removing the role must invalidate the cached permissions immediately.
    await role_repo.remove_from_user(UserId(user.id), RoleId(role.id))
    assert await user_repo.get_permissions(UserId(user.id)) == set()

    # Re-assign via the bulk path — cache must reflect it right away.
    await role_repo.set_user_roles(UserId(user.id), [role.id])
    assert await user_repo.get_permissions(UserId(user.id)) == {"user:manage"}
