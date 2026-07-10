import pytest

from contexts.auth.application.user_app_service import UserApplicationService
from contexts.auth.domain.user import RoleRef, User
from contexts.shared.domain.identifiers import UserId


class FakeUserRepository:
    async def list_all(self):
        return [User(
            user_id=UserId(7),
            username="alice",
            password_hash="hash",
            real_name="Alice",
            email="alice@example.com",
            department="项目部",
            roles=[RoleRef(2, "manager", "项目经理")],
        )]

    async def list_projects(self, user_id):
        assert user_id.value == 7
        return [{"id": 3, "code": "P001", "name": "一号项目", "is_primary": True}]


@pytest.mark.asyncio
async def test_personnel_list_contains_table_columns():
    result = await UserApplicationService(FakeUserRepository()).list_all()

    assert result == [{
        "serial_number": 1,
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
    }]
