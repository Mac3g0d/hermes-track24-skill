"""Typed shapes of the decrypted Track24 response, used as polyfactory models."""

from typing import Literal, TypedDict


class LastPoint(TypedDict):
    """The latest event the site selected for a parcel."""

    id: str
    operationDateTime: str
    operationAttribute: str
    serviceName: str


class TrackData(TypedDict):
    """The ``data`` object of a tracking response, including fields the summary must drop."""

    trackCode: str
    deliveredStatus: Literal["0", "1"]
    trackUpdateDateTime: str
    destinationAddress: str
    lastPoint: LastPoint
    events: list[LastPoint]


class TrackResult(TypedDict):
    """A decrypted successful tracking response."""

    status: Literal["ok"]
    sources: list[str]
    data: TrackData
