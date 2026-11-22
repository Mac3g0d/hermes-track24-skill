"""Integration tests: the full page-fetch, discovery, POST and decryption flow over real HTTP."""

from __future__ import annotations

import urllib.error
from typing import Any

import pytest

import track24
from helpers.constants import (
    ENDPOINT_PATH,
    HTTP_FORBIDDEN,
    HTTP_TOO_MANY_REQUESTS,
    OTHER_TRACK_CODE,
    OVERRIDE_ENDPOINT_PATH,
    OVERSIZED_PADDING_BYTES,
    PACKED_ENDPOINT_PATH,
    PACKED_SCRIPT,
    PAGE_WITH_LITERAL_TEMPLATE,
    PAGE_WITH_PACKED_TEMPLATE,
    PAGE_WITHOUT_ENDPOINT_TEMPLATE,
    PAGE_WITHOUT_PASSWORD,
    PASSWORD,
    TRACK24_BASE_URL,
    TRACK_CODE,
    WRONG_PASSWORD,
)
from helpers.crypto import encrypt_envelope
from helpers.server import FakeTrack24, Reply

pytestmark = pytest.mark.integration


def literal_page(password: str = PASSWORD, endpoint: str = ENDPOINT_PATH) -> Reply:
    """A page exposing both literals directly."""
    return Reply.html(PAGE_WITH_LITERAL_TEMPLATE.format(password=password, endpoint=endpoint))


def test_track_returns_verified_result(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """Happy path: GET page, POST the discovered endpoint, decrypt and verify."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    result = track24.track(TRACK_CODE, opener=opener)

    assert result == ok_result
    assert fake_track24.paths() == [("GET", "/"), ("POST", ENDPOINT_PATH)]


def test_track_sends_exact_page_query_and_form(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """The identifier travels unmodified; the POST is a browser-shaped urlencoded form."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    track24.track(TRACK_CODE, opener=opener)

    page_request, ajax_request = fake_track24.requests
    assert page_request.query == {"code": [TRACK_CODE]}
    assert ajax_request.form == {
        "code": [TRACK_CODE],
        "selectedService": [""],
        "lng": ["ru"],
        "sort": ["true"],
        "grouped": ["false"],
        "type": ["cache"],
    }
    assert ajax_request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert ajax_request.headers["accept"].startswith("application/json")


def test_track_never_sends_cookies_or_password(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """No session replay: no cookie header and the page password is never echoed back."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    track24.track(TRACK_CODE, opener=opener)

    for request in fake_track24.requests:
        assert "cookie" not in request.headers
        assert PASSWORD not in str(request.form) + str(request.query)


def test_track_discovers_packed_endpoint(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """When only the packed script is present, its endpoint receives the POST."""
    page = PAGE_WITH_PACKED_TEMPLATE.format(password=PASSWORD, packed=PACKED_SCRIPT)
    fake_track24.routes["/"] = Reply.html(page)
    fake_track24.routes[PACKED_ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    result = track24.track(TRACK_CODE, opener=opener)

    assert result["data"]["trackCode"] == TRACK_CODE
    assert fake_track24.paths()[-1] == ("POST", PACKED_ENDPOINT_PATH)


def test_track_uses_operator_endpoint_override(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """An explicit ``--endpoint`` replaces discovery even when the page has none."""
    fake_track24.routes["/"] = Reply.html(PAGE_WITHOUT_ENDPOINT_TEMPLATE.format(password=PASSWORD))
    fake_track24.routes[OVERRIDE_ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    result = track24.track(TRACK_CODE, endpoint=TRACK24_BASE_URL + OVERRIDE_ENDPOINT_PATH, opener=opener)

    assert result == ok_result
    assert fake_track24.paths()[-1] == ("POST", OVERRIDE_ENDPOINT_PATH)


def test_track_accepts_unencrypted_ok_response(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """A plain JSON response is verified the same way as a decrypted one."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(ok_result)

    result = track24.track(TRACK_CODE, opener=opener)

    assert result == ok_result


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"challenge": {"type": "captcha"}}, track24.ChallengeError),
        ({"status": "error", "data": None}, track24.ServiceStatusError),
        ({"data": {"trackCode": OTHER_TRACK_CODE}}, track24.IdentifierMismatchError),
        ({"data": {"trackCode": TRACK_CODE.lower()}}, track24.IdentifierMismatchError),
    ],
)
def test_track_rejects_http_200_with_bad_payload(
    override: dict[str, Any],
    error: type[Exception],
    fake_track24: FakeTrack24,
    opener: Any,
    ok_result: dict[str, Any],
) -> None:
    """HTTP 200 plus valid ciphertext is not success unless the decrypted payload verifies."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope({**ok_result, **override}))

    with pytest.raises(error):
        track24.track(TRACK_CODE, opener=opener)


def test_track_rejects_envelope_for_another_password(
    fake_track24: FakeTrack24, opener: Any, ok_result: dict[str, Any]
) -> None:
    """A rotated page password makes old ciphertext fail closed."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result, password=WRONG_PASSWORD))

    with pytest.raises(track24.DecryptionError):
        track24.track(TRACK_CODE, opener=opener)


@pytest.mark.parametrize("status", [HTTP_FORBIDDEN, HTTP_TOO_MANY_REQUESTS])
def test_track_stops_on_blocking_http_status(status: int, fake_track24: FakeTrack24, opener: Any) -> None:
    """403/429 propagate as ``HTTPError``; there is no retry."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json({"error": "blocked"}, status=status)

    with pytest.raises(urllib.error.HTTPError) as caught:
        track24.track(TRACK_CODE, opener=opener)

    assert caught.value.code == status
    assert fake_track24.paths().count(("POST", ENDPOINT_PATH)) == 1


def test_track_stops_before_post_when_page_lacks_password(fake_track24: FakeTrack24, opener: Any) -> None:
    """Without ``cp`` nothing is posted."""
    fake_track24.routes["/"] = Reply.html(PAGE_WITHOUT_PASSWORD)

    with pytest.raises(track24.MissingLiteralError):
        track24.track(TRACK_CODE, opener=opener)

    assert fake_track24.paths() == [("GET", "/")]


def test_track_stops_before_post_when_endpoint_unknown(fake_track24: FakeTrack24, opener: Any) -> None:
    """Discovery failure fails closed instead of guessing an endpoint."""
    fake_track24.routes["/"] = Reply.html(PAGE_WITHOUT_ENDPOINT_TEMPLATE.format(password=PASSWORD))

    with pytest.raises(track24.EndpointError):
        track24.track(TRACK_CODE, opener=opener)

    assert fake_track24.paths() == [("GET", "/")]


def test_track_refuses_external_endpoint_from_page(fake_track24: FakeTrack24, opener: Any) -> None:
    """A page pointing at another host never causes an outbound request there."""
    fake_track24.routes["/"] = literal_page(endpoint="https://example.com/ajax/x.ajax.php")

    with pytest.raises(track24.EndpointError):
        track24.track(TRACK_CODE, opener=opener)

    assert fake_track24.paths() == [("GET", "/")]


def test_track_rejects_invalid_code_without_network(fake_track24: FakeTrack24, opener: Any) -> None:
    """Input validation runs before any request."""
    code = " TEST00001"

    with pytest.raises(track24.InvalidTrackCodeError):
        track24.track(code, opener=opener)

    assert fake_track24.requests == []


def test_track_enforces_response_size_limit(fake_track24: FakeTrack24, opener: Any) -> None:
    """Oversized bodies are refused before parsing."""
    fake_track24.routes["/"] = Reply.html(" " * OVERSIZED_PADDING_BYTES)

    with pytest.raises(track24.ResponseTooLargeError):
        track24.track(TRACK_CODE, opener=opener)


def test_track_rejects_non_object_json(fake_track24: FakeTrack24, opener: Any) -> None:
    """A JSON array from the endpoint is malformed."""
    fake_track24.routes["/"] = literal_page()
    fake_track24.routes[ENDPOINT_PATH] = Reply.json([])

    with pytest.raises(track24.DecryptionError):
        track24.track(TRACK_CODE, opener=opener)
