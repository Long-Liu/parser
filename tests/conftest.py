import sys
import os

# Ensure project root in path for `import app`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app


@pytest.fixture
def test_app():
    return app
