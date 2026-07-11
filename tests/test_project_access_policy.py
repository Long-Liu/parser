import pytest

from contexts.auth.application.project_access import ProjectAccessPolicy
from contexts.shared.domain.exceptions import AuthorizationError, NotFoundError
from contexts.shared.domain.identifiers import UserId


class FakeAccessRepository:
    async def membership_role(self, user_id, project_id):
        return {(1, 10): "manager", (2, 10): "viewer"}.get((user_id, project_id))

    async def project_for_batch(self, batch_id):
        return {100: 10}.get(batch_id)

    async def project_for_data_row(self, template_id, row_id):
        return 10 if (template_id, row_id) == ("cost", 7) else None


@pytest.mark.asyncio
async def test_project_access_enforces_membership_and_role():
    policy = ProjectAccessPolicy(FakeAccessRepository())
    await policy.require(UserId(1), 10, {"manager"})
    with pytest.raises(AuthorizationError, match="viewer"):
        await policy.require(UserId(2), 10, {"manager"})
    with pytest.raises(AuthorizationError, match="no access"):
        await policy.require(UserId(3), 10)


@pytest.mark.asyncio
async def test_project_access_resolves_batch_and_data_row():
    policy = ProjectAccessPolicy(FakeAccessRepository())
    assert await policy.require_batch(UserId(1), 100) == 10
    assert await policy.require_data_row(UserId(1), "cost", 7) == 10
    with pytest.raises(NotFoundError):
        await policy.require_batch(UserId(1), 999)
