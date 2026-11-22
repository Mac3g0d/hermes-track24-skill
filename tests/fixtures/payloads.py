"""Fixtures with synthetic Track24 results built by polyfactory."""

from collections.abc import Callable
from typing import Any

import pytest

from constants import BATCH_SIZE
from factories import TrackDataFactory, TrackResultFactory

ResultFor = Callable[[str], dict[str, Any]]


@pytest.fixture
def ok_result() -> dict[str, Any]:
    """A decrypted successful response with random, valid content."""
    return dict(TrackResultFactory.build())


@pytest.fixture
def track_code(ok_result: dict[str, Any]) -> str:
    """The identifier ``ok_result`` belongs to."""
    return str(ok_result["data"]["trackCode"])


@pytest.fixture
def other_track_code(track_code: str) -> str:
    """A valid identifier that differs from ``track_code``."""
    candidate = track_code
    while candidate == track_code:
        candidate = TrackDataFactory.build()["trackCode"]
    return candidate


@pytest.fixture
def result_for() -> ResultFor:
    """Build a successful response for an arbitrary identifier."""

    def build(code: str) -> dict[str, Any]:
        return dict(TrackResultFactory.build(data={"trackCode": code}))

    return build


@pytest.fixture
def batch_codes() -> list[str]:
    """Several distinct valid identifiers."""
    codes: dict[str, None] = {}
    while len(codes) < BATCH_SIZE:
        codes[TrackDataFactory.build()["trackCode"]] = None
    return list(codes)
