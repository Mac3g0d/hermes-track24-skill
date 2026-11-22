"""Repository-level checks: Hermes hub layout, SKILL.md frontmatter and code conventions."""

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Any

from constants import (
    ALLOWED_SKILL_SUBDIRECTORIES,
    REPOSITORY_ROOT,
    SKILL_DIRECTORY,
    SKILL_NAME,
    SKILL_NAME_PATTERN,
    SKILLS_DIRECTORY,
    TRACKER_SCRIPT,
)


def test_hub_tap_layout_contains_exactly_one_skill() -> None:
    """A Hermes tap lists ``skills/`` and probes each subdirectory for ``SKILL.md``."""
    tap = SKILLS_DIRECTORY

    skills = sorted(path.parent.name for path in tap.glob("*/SKILL.md"))

    assert skills == [SKILL_NAME]


def test_skill_only_ships_hub_supported_subdirectories() -> None:
    """Only directories the hub downloads alongside ``SKILL.md`` are present."""
    skill = SKILL_DIRECTORY

    subdirectories = {path.name for path in skill.iterdir() if path.is_dir() and not path.name.startswith(("_", "."))}

    assert subdirectories <= ALLOWED_SKILL_SUBDIRECTORIES


def test_frontmatter_identifies_skill(frontmatter: dict[str, Any]) -> None:
    """``name`` matches the directory and the hub name pattern; metadata is complete."""
    name = frontmatter["name"]

    matches = re.fullmatch(SKILL_NAME_PATTERN, name)

    assert matches
    assert name == SKILL_DIRECTORY.name
    assert frontmatter["description"].strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(frontmatter["version"]))
    assert frontmatter["license"] == "MIT"
    assert frontmatter["metadata"]["hermes"]["tags"]


def test_skill_version_matches_pyproject(frontmatter: dict[str, Any], project_version: str) -> None:
    """The published skill version and the project version move together."""
    skill_version = str(frontmatter["version"])

    matches = skill_version == project_version

    assert matches


def test_skill_references_existing_scripts(skill_text: str) -> None:
    """Every ``scripts/...`` path mentioned in ``SKILL.md`` exists in the skill."""
    referenced = set(re.findall(r"scripts/[\w.]+\.py", skill_text))

    missing = [relative for relative in referenced if not (SKILL_DIRECTORY / relative).is_file()]

    assert referenced
    assert missing == []


def test_skill_has_no_inline_shell_dsl(skill_text: str) -> None:
    """Community hub installs refuse skills that embed auto-run inline shell snippets."""
    text = skill_text

    matches = re.findall(r"!`", text)

    assert matches == []


def test_python_sources_have_no_line_comments(python_sources: list[Path]) -> None:
    """Explanations live in docstrings; ``#`` comments are not used anywhere."""
    sources = {path: path.read_text(encoding="utf-8") for path in python_sources}

    offenders = [
        f"{path.relative_to(REPOSITORY_ROOT)}:{token.start[0]}"
        for path, source in sources.items()
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]

    assert offenders == []


def test_python_sources_do_not_use_future_annotations(python_sources: list[Path]) -> None:
    """Annotations are evaluated normally; ``from __future__ import annotations`` is not used."""
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in python_sources}

    offenders = [
        str(path.relative_to(REPOSITORY_ROOT))
        for path, tree in trees.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
    ]

    assert offenders == []


def test_constants_are_annotated_final(constant_modules: list[Path]) -> None:
    """Every module-level name in a constants module is UPPER_CASE and annotated ``Final``."""
    trees = {path.name: ast.parse(path.read_text(encoding="utf-8")).body for path in constant_modules}

    plain = [f"{name}:{node.lineno}" for name, body in trees.items() for node in body if isinstance(node, ast.Assign)]
    annotated = [
        (node.target.id, ast.unparse(node.annotation))
        for body in trees.values()
        for node in body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]

    assert plain == []
    assert annotated
    assert [name for name, annotation in annotated if not name.isupper() or not annotation.startswith("Final")] == []


def test_tracker_module_defines_no_module_constants() -> None:
    """All constants live in ``track24_constants.py``, not in the tracker itself."""
    tree = ast.parse(TRACKER_SCRIPT.read_text(encoding="utf-8"))

    names = [node.lineno for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))]

    assert names == []


def test_test_modules_contain_only_imports_and_tests(test_modules: list[Path]) -> None:
    """Helpers, fixtures and constants live in ``fixtures/``, ``factories/`` and ``constants.py``."""
    trees = {path.name: ast.parse(path.read_text(encoding="utf-8")).body for path in test_modules}

    offenders = [
        f"{name}:{node.lineno}"
        for name, body in trees.items()
        for index, node in enumerate(body)
        if not (index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        and not isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"))
    ]

    assert offenders == []


def test_conftest_only_registers_plugins() -> None:
    """``conftest.py`` loads fixture modules as plugins and defines nothing else."""
    body = ast.parse((REPOSITORY_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")).body

    statements = [node for node in body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))]

    assert len(statements) == 1
    assert isinstance(statements[0], ast.Assign)
    assert ast.unparse(statements[0].targets[0]) == "pytest_plugins"
