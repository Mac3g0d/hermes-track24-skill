"""Factories that build random but valid Track24 payloads."""

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from constants import (
    EVENT_DATETIME_FORMAT,
    EVENT_ID_DIGITS,
    SOURCES,
    TRACK_CODE_DIGITS,
    TRACK_CODE_PREFIX,
)
from factories.models import LastPoint, TrackData, TrackResult


class LastPointFactory(TypedDictFactory[LastPoint]):
    """Latest-event factory with realistic identifiers and timestamps."""

    __set_as_default_factory_for_type__ = True

    id = Use(lambda: LastPointFactory.__faker__.numerify("#" * EVENT_ID_DIGITS))
    operationDateTime = Use(lambda: LastPointFactory.__faker__.date_time().strftime(EVENT_DATETIME_FORMAT))
    operationAttribute = Use(lambda: LastPointFactory.__faker__.sentence())
    serviceName = Use(lambda: LastPointFactory.__faker__.company())


class TrackDataFactory(TypedDictFactory[TrackData]):
    """Tracking ``data`` factory; identifiers always satisfy the CLI's validation pattern."""

    __set_as_default_factory_for_type__ = True

    trackCode = Use(lambda: TRACK_CODE_PREFIX + TrackDataFactory.__faker__.numerify("#" * TRACK_CODE_DIGITS))
    deliveredStatus = "0"
    trackUpdateDateTime = Use(lambda: TrackDataFactory.__faker__.date_time().strftime(EVENT_DATETIME_FORMAT))
    destinationAddress = Use(lambda: TrackDataFactory.__faker__.address())
    events = Use(list)


class TrackResultFactory(TypedDictFactory[TrackResult]):
    """Decrypted successful response factory."""

    status = "ok"
    sources = Use(lambda: list(SOURCES))
