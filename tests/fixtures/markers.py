"""Collection hooks that mark tests by module, so test files hold nothing but tests."""

import pytest

from constants import INTEGRATION_MODULE_PREFIX


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test in a ``test_integration_*`` module with ``integration``."""
    for item in items:
        if item.path.name.startswith(INTEGRATION_MODULE_PREFIX):
            item.add_marker(pytest.mark.integration)
