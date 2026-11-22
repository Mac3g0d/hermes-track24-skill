"""Repository-level checks: Hermes hub layout, SKILL.md frontmatter and code conventions."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Any

import pytest
import yaml

from helpers.constants import (
    ALLOWED_SKILL_SUBDIRECTORIES,
    CONSTANTS_MODULE,
    FRONTMATTER_DELIMITER,
    REPOSITORY_ROOT,
    SKILL_DIRECTORY,
    SKILL_MANIFEST,
    SKILL_NAME,
    SKILL_NAME_PATTERN,
    SKILLS_DIRECTORY,
)

PYTHON_SOURCES = sorted(
    path
    for directory in (SKILLS_DIRECTORY, REPOSITORY_ROOT / "tests")
    for path in directory.rglob("*.py")
)
CONSTANT_MODULES = [CONSTANTS_MODULE, REPOSITORY_ROOT / "tests" / "helpers" / "constants.py"]


def read_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML block between the leading ``---`` delimiters."""
    text = path.read_text(encoding="utf-8")
    _, block, _ = text.split(FRONTMATTER_DELIMITER + "\n", 2)
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict)
    return loaded


def test_hub_tap_layout_contains_exactly_one_skill() -> None:
    """A Hermes tap lists ``skills/`` and probes each subdirectory for ``SKILL.md``."""
    tap = SKILLS_DIRECTORY

    skills = sorted(path.parent.name for path in tap.glob("*/SKILL.md"))

    assert skills == [SKILL_NAME]


def test_skill_only_ships_hub_supported_subdirectories() -> None:
    """Only directories the hub downloads alongside ``SKILL.md`` are present."""
    skill = SKILL_DIRECTORY

    subdirectories = {
        path.name for path in skill.iterdir() if path.is_dir() and not path.name.startswith(("_", "."))
    }

    assert subdirectories <= ALLOWED_SKILL_SUBDIRECTORIES


def test_frontmatter_identifies_skill() -> None:
    """``name`` matches the directory and the hub name pattern; metadata is complete."""
    manifest = SKILL_MANIFEST

    frontmatter = read_frontmatter(manifest)

    assert frontmatter["name"] == SKILL_DIRECTORY.name
    assert re.fullmatch(SKILL_NAME_PATTERN, frontmatter["name"])
    assert frontmatter["description"].strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(frontmatter["version"]))
    assert frontmatter["license"] == "MIT"
    assert frontmatter["metadata"]["hermes"]["tags"]


def test_skill_version_matches_pyproject() -> None:
    """The published skill version and the project version move together."""
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)

    assert project_version is not None
    assert str(read_frontmatter(SKILL_MANIFEST)["version"]) == project_version[1]


def test_skill_references_existing_scripts() -> None:
    """Every ``scripts/...`` path mentioned in ``SKILL.md`` exists in the skill."""
    text = SKILL_MANIFEST.read_text(encoding="utf-8")

    referenced = set(re.findall(r"scripts/[\w.]+\.py", text))

    assert referenced
    for relative in referenced:
        assert (SKILL_DIRECTORY / relative).is_file(), relative


def test_skill_has_no_inline_shell_dsl() -> None:
    """Community hub installs refuse skills that embed auto-run inline shell snippets."""
    text = SKILL_MANIFEST.read_text(encoding="utf-8")

    matches = re.findall(r"!`", text)

    assert matches == []


@pytest.mark.parametrize("path", PYTHON_SOURCES, ids=lambda path: str(path.relative_to(REPOSITORY_ROOT)))
def test_python_sources_have_no_line_comments(path: Path) -> None:
    """Explanations live in docstrings; ``#`` comments are not used anywhere."""
    source = path.read_text(encoding="utf-8")

    tokens = tokenize.generate_tokens(io.StringIO(source).readline)

    assert [token.start[0] for token in tokens if token.type == tokenize.COMMENT] == []


@pytest.mark.parametrize("path", CONSTANT_MODULES, ids=lambda path: path.name)
def test_constants_are_annotated_final(path: Path) -> None:
    """Every module-level UPPER_CASE name is declared with a ``typing.Final`` annotation."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    plain = [
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    ]
    annotated = {
        node.target.id: ast.unparse(node.annotation)
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }

    assert plain == []
    assert annotated
    assert all(name.isupper() for name in annotated)
    assert all(annotation.startswith("Final") for annotation in annotated.values())


def test_tracker_module_defines_no_module_constants() -> None:
    """All constants live in ``track24_constants.py``, not in the tracker itself."""
    tree = ast.parse((SKILL_DIRECTORY / "scripts" / "track24.py").read_text(encoding="utf-8"))

    names = [
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    ]

    assert names == []
