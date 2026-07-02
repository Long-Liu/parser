from __future__ import annotations

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.exceptions import ValidationError


class Project(AggregateRoot[ProjectId]):
    def __init__(self, project_id: ProjectId | None, code: str, name: str,
                 created_by: UserId | None = None) -> None:
        super().__init__()
        self.id = project_id
        self._code = code
        self._name = name
        self.created_by = created_by

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    def rename(self, new_name: str) -> None:
        if not new_name.strip():
            raise ValidationError("project name must not be empty")
        self._name = new_name.strip()

    @classmethod
    def create(cls, project_id: ProjectId | None, code: str, name: str,
               created_by: UserId | None = None) -> "Project":
        if not code.strip():
            raise ValidationError("project code must not be empty")
        if not name.strip():
            raise ValidationError("project name must not be empty")
        return cls(project_id=project_id, code=code.strip(), name=name.strip(),
                   created_by=created_by)
