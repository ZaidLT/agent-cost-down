import pytest

from agent_cost_down.fixtures import generate, load_task


@pytest.fixture
def suite(tmp_path):
    root = tmp_path / "fixtures"
    root.mkdir()
    generate(root)
    return root


@pytest.fixture
def first(suite):
    return load_task(suite, "resolution-development-1")
