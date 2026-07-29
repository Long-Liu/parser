from typing import Any, cast

from contexts.auth.application.project_access import ProjectAccessRepository
from contexts.parsing.infrastructure.tables import UploadBatch
from contexts.project.infrastructure.tables import ProjectUser
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS


class TortoiseProjectAccessRepository(ProjectAccessRepository):
    async def projects_for_user(self, user_id: int) -> list[int]:
        return cast(
            list[int],
            list(
                await ProjectUser.filter(user_id=user_id).values_list(
                    "project_id",
                    flat=True,
                )
            ),
        )

    async def membership_role(self, user_id: int, project_id: int) -> str | None:
        row = await ProjectUser.get_or_none(user_id=user_id, project_id=project_id)
        return row.role if row else None

    async def project_for_batch(self, batch_id: int) -> int | None:
        batch = await UploadBatch.get_or_none(id=batch_id)
        return batch.project_id if batch else None

    async def project_for_data_row(self, template_id: str, row_id: int) -> int | None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return None
        row = await model.get_or_none(id=row_id)
        if row is None:
            return None
        return await self.project_for_batch(int(cast(Any, row).batch_id))
