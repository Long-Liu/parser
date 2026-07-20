from __future__ import annotations

from datetime import date
from decimal import Decimal

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId


class Project(AggregateRoot[ProjectId]):
    _VALID_STAGES = {"planning", "design", "construction", "completion", "maintenance"}
    _VALID_STATUSES = {"normal", "warning", "suspended", "closed"}

    def __init__(self, project_id: ProjectId | None, code: str, name: str,
                 created_by: UserId | None = None, *, project_type: str = "",
                 capacity_mw: Decimal | None = None,
                 contract_price: Decimal | None = None,
                 start_date: date | None = None, end_date: date | None = None,
                 manager_id: UserId | None = None, stage: str = "planning",
                 status: str = "normal", progress: Decimal = Decimal("0"),
                 description: str = "") -> None:
        super().__init__()
        self._validate_stage(stage)
        self._validate_status(status)
        self._validate_progress(progress)
        self._validate_dates(start_date, end_date)
        self.id = project_id
        self._code = code
        self._name = name
        self.created_by = created_by
        self.project_type = project_type
        self.capacity_mw = capacity_mw
        self.contract_price = contract_price
        self.start_date = start_date
        self.end_date = end_date
        self.manager_id = manager_id
        self.stage = stage
        self.status = status
        self.progress = progress
        self.description = description

    @staticmethod
    def _validate_stage(stage: str) -> None:
        if stage not in Project._VALID_STAGES:
            raise ValidationError(f"invalid stage: {stage!r}")

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in Project._VALID_STATUSES:
            raise ValidationError(f"invalid status: {status!r}")

    @staticmethod
    def _validate_progress(progress: Decimal) -> None:
        if not (Decimal("0") <= progress <= Decimal("100")):
            raise ValidationError("progress must be between 0 and 100")

    @staticmethod
    def _validate_dates(start: date | None, end: date | None) -> None:
        if start and end and start > end:
            raise ValidationError("start_date must be before end_date")

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

    _ALLOWED_FIELDS: set[str] = {
        "project_type", "capacity_mw", "contract_price",
        "start_date", "end_date", "manager_id", "stage",
        "status", "progress", "description",
    }

    def update_details(self, **values) -> None:
        if "name" in values:
            self.rename(values.pop("name"))
        unknown = set(values) - self._ALLOWED_FIELDS
        if unknown:
            raise ValidationError(f"unsupported project fields: {sorted(unknown)}")
        next_start = values.get("start_date", self.start_date)
        next_end = values.get("end_date", self.end_date)
        self._validate_dates(next_start, next_end)
        for field, value in values.items():
            if field == "stage":
                self._validate_stage(str(value))
            elif field == "status":
                self._validate_status(str(value))
            elif field == "progress":
                value = Decimal(str(value))
                self._validate_progress(value)
            object.__setattr__(self, field, value)

    def suspend(self) -> None:
        self.status = "suspended"

    def close(self) -> None:
        self.status = "closed"
        self.progress = Decimal("100")

    def advance_stage(self, stage: str) -> None:
        self._validate_stage(stage)
        # Sets are intentionally not used for ordering business transitions.
        order = ["planning", "design", "construction", "completion", "maintenance"]
        if order.index(stage) < order.index(self.stage):
            raise ValidationError("project stage cannot move backwards")
        self.stage = stage

    @classmethod
    def create(cls, project_id: ProjectId | None, code: str, name: str,
               created_by: UserId | None = None, **details) -> Project:
        if not code.strip():
            raise ValidationError("project code must not be empty")
        if not name.strip():
            raise ValidationError("project name must not be empty")
        return cls(project_id=project_id, code=code.strip(), name=name.strip(),
                   created_by=created_by, **details)
