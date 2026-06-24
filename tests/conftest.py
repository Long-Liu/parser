import pytest
from parser.app import app


@pytest.fixture
def test_app():
    return app
