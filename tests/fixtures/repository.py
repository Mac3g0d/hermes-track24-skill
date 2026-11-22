"""Fixtures describing the repository layout and the published skill manifest."""

import re
from pathlib import Path
from typing import Any

import pytest
import tomli
import yaml

from constants import (
    CONSTANTS_MODULE,
    FRONTMATTER_DELIMITER,
    PEP723_BLOCK_PATTERN,
    PEP723_BLOCK_TYPE,
    PEP723_LINE_PREFIX,
    PYPROJECT_VERSION_PATTERN,
    REPOSITORY_ROOT,
    SKILL_MANIFEST,
    SKILLS_DIRECTORY,
    TESTS_DIRECTORY,
    TRACKER_SCRIPT,
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


def pep723_block_lines(source: str) -> set[int]:
    """Line numbers covered by PEP 723 inline metadata blocks, which are comments by design."""
    lines: set[int] = set()
    for match in PEP723_BLOCK_PATTERN.finditer(source):
        first = source.count("\n", 0, match.start()) + 1
        last = source.count("\n", 0, match.end()) + 1
        lines.update(range(first, last + 1))
    return lines


@pytest.fixture(scope="session")
def metadata_lines() -> Any:
    """Return a function giving the PEP 723 block line numbers of a source text."""
    return pep723_block_lines


@pytest.fixture(scope="session")
def script_metadata() -> dict[str, Any]:
    """The parsed PEP 723 ``script`` block at the top of the tracker."""
    source = TRACKER_SCRIPT.read_text(encoding="utf-8")
    blocks = [match for match in PEP723_BLOCK_PATTERN.finditer(source) if match["type"] == PEP723_BLOCK_TYPE]
    assert len(blocks) == 1
    content = "".join(
        line[len(PEP723_LINE_PREFIX):] if line.startswith(PEP723_LINE_PREFIX) else line[1:]
        for line in blocks[0]["content"].splitlines(keepends=True)
    )
    return tomli.loads(content)


@pytest.fixture(scope="session")
def pyproject() -> dict[str, Any]:
    """The parsed ``pyproject.toml``."""
    return tomli.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
