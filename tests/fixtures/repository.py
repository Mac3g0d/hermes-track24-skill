"""Fixtures describing the repository layout and the published skill manifest."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from constants import (
    CONSTANTS_MODULE,
    FRONTMATTER_DELIMITER,
    PYPROJECT_VERSION_PATTERN,
    REPOSITORY_ROOT,
    SKILL_MANIFEST,
    SKILLS_DIRECTORY,
    TESTS_DIRECTORY,
)


@pytest.fixture(scope="session")
def python_sources() -> list[Path]:
    """Every Python file of the skill and the test suite."""
    return sorted(path for directory in (SKILLS_DIRECTORY, TESTS_DIRECTORY) for path in directory.rglob("*.py"))


@pytest.fixture(scope="session")
def constant_modules() -> list[Path]:
    """Modules that must declare only ``Final`` constants."""
    return [CONSTANTS_MODULE, TESTS_DIRECTORY / "constants.py"]


@pytest.fixture(scope="session")
def test_modules() -> list[Path]:
    """Every ``test_*.py`` module."""
    return sorted(TESTS_DIRECTORY.glob("test_*.py"))


@pytest.fixture(scope="session")
def skill_text() -> str:
    """The raw ``SKILL.md``."""
    return SKILL_MANIFEST.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def frontmatter(skill_text: str) -> dict[str, Any]:
    """The parsed YAML frontmatter of ``SKILL.md``."""
    _, block, _ = skill_text.split(FRONTMATTER_DELIMITER + "\n", 2)
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def project_version() -> str:
    """The ``version`` declared in ``pyproject.toml``."""
    match = re.search(PYPROJECT_VERSION_PATTERN, (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    return match[1]
