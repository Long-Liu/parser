import pytest

from contexts.data.infrastructure.repositories import TortoiseDataQueryRepository
from contexts.parsing.domain.parse_job import ParsedRow
from contexts.parsing.infrastructure.data_writer import (
    BULK_CREATE_BATCH_SIZE,
    TortoiseParsedDataSink,
)
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination
from contexts.shared.infrastructure.database.tables import TEMPLATE_DATA_MODELS


@pytest.mark.parametrize("page,size", [(0, 10), (-1, 10), (1, 0), (1, 1001)])
def test_pagination_rejects_out_of_range_values(page, size):
    with pytest.raises(ValidationError):
        Pagination(page=page, size=size)


async def test_unknown_template_query_is_not_reported_as_empty_data():
    repo = TortoiseDataQueryRepository()
    with pytest.raises(NotFoundError, match="unknown"):
        await repo.query("unknown", None, [], Pagination(page=1, size=20))


async def test_unknown_template_sink_refuses_to_drop_rows():
    sink = TortoiseParsedDataSink()
    with pytest.raises(RuntimeError, match="refusing to drop"):
        await sink.insert_data_rows("unknown", 1, [object()])


async def test_data_sink_bulk_create_uses_bounded_batch_size(monkeypatch):
    calls = []

    class Meta:
        fields_map = {}

    class FakeModel:
        _meta = Meta()

        def __init__(self, **values):
            self.values = values

        @classmethod
        async def bulk_create(cls, rows, batch_size=None):
            calls.append((len(rows), batch_size))

    monkeypatch.setitem(TEMPLATE_DATA_MODELS, "test_bulk", FakeModel)
    rows = [ParsedRow(row_index=index, fields={"value": index}) for index in range(1200)]

    await TortoiseParsedDataSink().insert_data_rows("test_bulk", 1, rows)

    assert calls == [(1200, BULK_CREATE_BATCH_SIZE)]
    assert BULK_CREATE_BATCH_SIZE == 500
