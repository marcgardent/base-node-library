import sys
from pathlib import Path
import pytest

PYTHON_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import base_node
sys.modules["lang"] = base_node
sys.modules["base_node.lang"] = base_node

from fake_schema import FakeSchema  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def schema():
    return FakeSchema()


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")
