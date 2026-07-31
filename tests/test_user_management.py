import pytest

# noinspection PyPackageRequirements
from tortoise import Tortoise

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.domain.user import RoleRef, User
from contexts.auth.infrastructure.repositories import TortoiseUserRepository
from contexts.auth.infrastructure.tables import (
    Role as OrmRole,
)
from contexts.auth.infrastructure.tables import (
    User as OrmUser,
)
from contexts.auth.infrastructure.tables import (
    UserRole,
)
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.domain.pagination import Pagination

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


class FakeUserRepository:
    def __init__(self):
        self.list_args = None

    async def list_all(self, *, keyword="", offset=0, limit=20):
        self.list_args = (keyword, offset, limit)
        return [
            User(
                user_id=UserId(7),
                username="alice",
                password_hash="hash",
                real_name="Alice",
                email="alice@example.com",
                department="项目部",
                roles=[RoleRef(2, "manager", "项目经理")],
            )
        ], 21

    @staticmethod
    async def list_projects(user_id):
        assert user_id.value == 7
        return [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}]


class CreateUserRepository:
    def __init__(self):
        self.user = None
        self.role = None

    @staticmethod
    async def find_by_username(_username):
        return None

    async def save(self, user):
        user.id = user.id or UserId(8)
        self.user = user

    async def find_by_id(self, user_id):
        return self.user if self.user and self.user.id == user_id else None

    @staticmethod
    async def list_projects(_user_id):
        return []

    async def set_system_role(self, _user_id, role_code):
        self.role = role_code


class FakePasswordHasher:
    @staticmethod
    def hash(value):
        return f"hash:{value}"


@pytest.mark.asyncio
async def test_personnel_list_contains_table_columns():
    repo = FakeUserRepository()
    # noinspection PyTypeChecker
    result = await UserApplicationService(repo).list_all(
        keyword="  alice@example  ",
        pagination=Pagination(2, 20, max_size=100),
    )

    assert repo.list_args == ("alice@example", 20, 20)
    assert result == {
        "users": [
            {
                "serial_number": 21,
                "id": 7,
                "username": "alice",
                "real_name": "Alice",
                "email": "alice@example.com",
                "phone": "",
                "department": "项目部",
                "system_roles": [{"id": 2, "code": "manager", "name": "项目经理"}],
                "is_admin": False,
                "projects": [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}],
                "main_projects": [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}],
                "project_permission_overview": [{"id": 3, "code": "P001", "name": "一号项目"}],
                "project_permission_summary": {"manager": 1, "viewer": 0},
                "is_active": True,
            }
        ],
        "pagination": {"page": 2, "size": 20, "total": 21},
    }


@pytest.mark.asyncio
async def test_create_user_accepts_published_ui_form_shape():
    repo = CreateUserRepository()
    # noinspection PyTypeChecker
    result = await UserApplicationService(repo, password_hasher=FakePasswordHasher()).create(
        username="",
        password="",
        real_name="Alice",
        email="alice@example.com",
        department="工程部",
        is_admin=True,
    )
    assert result["username"] == "alice@example.com"
    assert len(result["temporary_password"]) >= 8
    assert repo.role == "admin"


@pytest.mark.asyncio
async def test_admin_toggle_preserves_other_system_roles(db):
    user = await OrmUser.create(username="alice", password="hash")
    admin = await OrmRole.create(code="admin", name="admin")
    manager = await OrmRole.create(code="manager", name="manager")
    await OrmRole.create(code="viewer", name="viewer")
    await UserRole.create(user_id=user.id, role_id=admin.id)
    await UserRole.create(user_id=user.id, role_id=manager.id)

    repo = TortoiseUserRepository()
    await repo.set_system_role(UserId(user.id), "viewer")
    role_ids = await UserRole.filter(user_id=user.id).values_list(
        "role_id",
        flat=True,
    )
    assert set(role_ids) == {manager.id}

    await repo.set_system_role(UserId(user.id), "admin")
    role_ids = await UserRole.filter(user_id=user.id).values_list(
        "role_id",
        flat=True,
    )
    assert set(role_ids) == {manager.id, admin.id}


@pytest.mark.asyncio
@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (1, 101)])
async def test_personnel_list_rejects_invalid_pagination(page, size):
    with pytest.raises(ValidationError, match="page|size"):
        Pagination(page, size, max_size=100)
