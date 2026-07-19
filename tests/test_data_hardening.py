import pytest

from contexts.data.infrastructure.repositories import TortoiseDataQueryRepository
from contexts.parsing.infrastructure.data_writer import TortoiseParsedDataSink
from contexts.shared.domain.exceptions import NotFoundError, ValidationError
from contexts.shared.domain.pagination import Pagination


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
