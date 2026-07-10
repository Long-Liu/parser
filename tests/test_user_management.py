import pytest

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.domain.user import RoleRef, User
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId


class FakeUserRepository:
    def __init__(self):
        self.list_args = None

    async def list_all(self, *, keyword="", offset=0, limit=20):
        self.list_args = (keyword, offset, limit)
        return [User(
            user_id=UserId(7),
            username="alice",
            password_hash="hash",
            real_name="Alice",
            email="alice@example.com",
            department="项目部",
            roles=[RoleRef(2, "manager", "项目经理")],
        )], 21

    async def list_projects(self, user_id):
        assert user_id.value == 7
        return [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}]


@pytest.mark.asyncio
async def test_personnel_list_contains_table_columns():
    repo = FakeUserRepository()
    result = await UserApplicationService(repo).list_all(
        keyword="  alice@example  ", page=2, size=20,
    )

    assert repo.list_args == ("alice@example", 20, 20)
    assert result == {
        "users": [{
            "serial_number": 21,
            "id": 7,
            "username": "alice",
            "real_name": "Alice",
            "email": "alice@example.com",
            "department": "项目部",
            "system_roles": [{"id": 2, "code": "manager", "name": "项目经理"}],
            "projects": [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}],
            "main_projects": [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}],
            "project_permission_overview": [{"id": 3, "code": "P001", "name": "一号项目"}],
            "is_active": True,
        }],
        "pagination": {"page": 2, "size": 20, "total": 21},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (1, 101)])
async def test_personnel_list_rejects_invalid_pagination(page, size):
    with pytest.raises(ValidationError, match="page|size"):
        await UserApplicationService(FakeUserRepository()).list_all(
            page=page, size=size,
        )
