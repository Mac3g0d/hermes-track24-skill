"""Pytest fixtures shared by unit and integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from helpers.constants import (
    EVENT_CARRIER,
    EVENT_ID,
    EVENT_OPERATION,
    EVENT_TIME,
    SECRET_ADDRESS,
    SOURCE_UPDATED_AT,
    SOURCES,
    TRACK_CODE,
)
from helpers.server import FakeTrack24, serve


@pytest.fixture
def ok_result() -> dict[str, Any]:
    """A decrypted successful response, including fields the summary must drop."""
    return {
        "status": "ok",
        "sources": SOURCES,
        "data": {
            "trackCode": TRACK_CODE,
            "deliveredStatus": "0",
            "trackUpdateDateTime": SOURCE_UPDATED_AT,
            "destinationAddress": SECRET_ADDRESS,
            "lastPoint": {
                "id": EVENT_ID,
                "operationDateTime": EVENT_TIME,
                "operationAttribute": EVENT_OPERATION,
                "serviceName": EVENT_CARRIER,
            },
            "events": [],
        },
    }


@pytest.fixture
def fake_track24() -> FakeTrack24:
    """An empty fake site; tests register their own routes."""
    return FakeTrack24()


@pytest.fixture
def opener(fake_track24: FakeTrack24) -> Iterator[Any]:
    """A urllib opener whose Track24 traffic reaches ``fake_track24``."""
    with serve(fake_track24) as routed_opener:
        yield routed_opener
