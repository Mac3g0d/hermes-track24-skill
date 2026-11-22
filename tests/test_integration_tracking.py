"""Integration tests: the full page-fetch, discovery, POST and decryption flow through httpx."""

from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

import track24
from constants import (
    CONCURRENCY_PROBE_DELAY_SECONDS,
    CUSTOM_TIMEOUT_SECONDS,
    ENDPOINT_PATH,
    HTTP_FORBIDDEN,
    HTTP_FOUND,
    HTTP_TOO_MANY_REQUESTS,
    OVERRIDE_ENDPOINT_PATH,
    OVERSIZED_PADDING_BYTES,
    PACKED_ENDPOINT_PATH,
    PACKED_SCRIPT,
    PAGE_WITH_PACKED_TEMPLATE,
    PAGE_WITHOUT_ENDPOINT_TEMPLATE,
    PAGE_WITHOUT_PASSWORD,
    PASSWORD,
    TRACK24_BASE_URL,
    WRONG_PASSWORD,
)
from fixtures.crypto import Encrypt
from fixtures.network import FakeTrack24
from track24_constants import CONNECT_ATTEMPTS, MAX_CONCURRENT_REQUESTS


async def test_track_returns_verified_result(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """Happy path: GET page, POST the discovered endpoint, decrypt and verify."""
    site.page()
    site.payload(ok_result)

    result = await track24.track(client, track_code)

    assert result == ok_result
    assert site.calls == [("GET", "/"), ("POST", ENDPOINT_PATH)]


async def test_track_sends_exact_page_query_and_form(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """The identifier travels unmodified; the POST is a browser-shaped urlencoded form."""
    site.page()
    site.payload(ok_result)

    await track24.track(client, track_code)

    page_request, ajax_request = site.requests
    assert dict(page_request.url.params) == {"code": track_code}
    assert site.form_of(ajax_request) == {
        "code": [track_code],
        "selectedService": [""],
        "lng": ["ru"],
        "sort": ["true"],
        "grouped": ["false"],
        "type": ["cache"],
    }
    assert ajax_request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert ajax_request.headers["accept"].startswith("application/json")
    assert ajax_request.url.host == "track24.ru"


async def test_track_never_sends_cookies_or_password(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """No session replay: no cookie header and the page password is never echoed back."""
    site.page(headers={"Set-Cookie": "session=synthetic"})
    site.payload(ok_result)

    await track24.track(client, track_code)

    assert all(PASSWORD not in str(request.url) + request.content.decode() for request in site.requests)
    assert "cookie" not in site.requests[0].headers


async def test_track_discovers_packed_endpoint(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """When only the packed script is present, its endpoint receives the POST."""
    site.page(PAGE_WITH_PACKED_TEMPLATE.format(password=PASSWORD, packed=PACKED_SCRIPT))
    site.payload(ok_result, path=PACKED_ENDPOINT_PATH)

    result = await track24.track(client, track_code)

    assert result["data"]["trackCode"] == track_code
    assert site.calls[-1] == ("POST", PACKED_ENDPOINT_PATH)


async def test_track_uses_operator_endpoint_override(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """An explicit ``--endpoint`` replaces discovery even when the page has none."""
    site.page(PAGE_WITHOUT_ENDPOINT_TEMPLATE.format(password=PASSWORD))
    site.payload(ok_result, path=OVERRIDE_ENDPOINT_PATH)

    result = await track24.track(client, track_code, TRACK24_BASE_URL + OVERRIDE_ENDPOINT_PATH)

    assert result == ok_result
    assert site.calls[-1] == ("POST", OVERRIDE_ENDPOINT_PATH)


async def test_track_accepts_unencrypted_ok_response(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """A plain JSON response is verified the same way as a decrypted one."""
    site.page()
    site.respond(json=ok_result)

    result = await track24.track(client, track_code)

    assert result == ok_result


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"challenge": {"type": "captcha"}}, track24.ChallengeError),
        ({"status": "error", "data": None}, track24.ServiceStatusError),
        ({"data": {"trackCode": "TEST99999"}}, track24.IdentifierMismatchError),
    ],
)
async def test_track_rejects_http_200_with_bad_payload(
    override: dict[str, Any],
    error: type[Exception],
    site: FakeTrack24,
    client: httpx.AsyncClient,
    ok_result: dict[str, Any],
    track_code: str,
) -> None:
    """HTTP 200 plus valid ciphertext is not success unless the decrypted payload verifies."""
    site.page()
    site.payload({**ok_result, **override})

    with pytest.raises(error):
        await track24.track(client, track_code)


async def test_track_rejects_case_changed_identifier(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """Identifier comparison is exact, so a lower-cased echo is a mismatch."""
    ok_result["data"]["trackCode"] = track_code.lower()
    site.page()
    site.payload(ok_result)

    with pytest.raises(track24.IdentifierMismatchError):
        await track24.track(client, track_code)


async def test_track_rejects_envelope_for_another_password(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """A rotated page password makes old ciphertext fail closed."""
    site.page()
    site.payload(ok_result, password=WRONG_PASSWORD)

    with pytest.raises(track24.DecryptionError):
        await track24.track(client, track_code)


@pytest.mark.parametrize("status", [HTTP_FORBIDDEN, HTTP_TOO_MANY_REQUESTS])
async def test_track_stops_on_blocking_http_status(
    status: int, site: FakeTrack24, client: httpx.AsyncClient, track_code: str
) -> None:
    """403/429 propagate as ``HTTPStatusError``; there is no retry."""
    site.page()
    site.respond(status_code=status, json={"error": "blocked"})

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await track24.track(client, track_code)

    assert caught.value.response.status_code == status
    assert site.calls.count(("POST", ENDPOINT_PATH)) == 1


async def test_track_refuses_redirects(site: FakeTrack24, client: httpx.AsyncClient, track_code: str) -> None:
    """A redirect is reported instead of followed, so no request leaves Track24."""
    site.page("", status_code=HTTP_FOUND, headers={"Location": "https://example.com/"})

    with pytest.raises(track24.UnexpectedRedirectError):
        await track24.track(client, track_code)

    assert site.calls == [("GET", "/")]


@pytest.mark.parametrize(
    ("page", "error"),
    [
        (PAGE_WITHOUT_PASSWORD, track24.MissingLiteralError),
        (PAGE_WITHOUT_ENDPOINT_TEMPLATE.format(password=PASSWORD), track24.EndpointError),
        (FakeTrack24.literal_page(endpoint="https://example.com/ajax/x.ajax.php"), track24.EndpointError),
    ],
)
async def test_track_stops_before_post_on_unusable_page(
    page: str, error: type[Exception], site: FakeTrack24, client: httpx.AsyncClient, track_code: str
) -> None:
    """A missing password, unknown endpoint or foreign endpoint fails closed with no POST."""
    site.page(page)

    with pytest.raises(error):
        await track24.track(client, track_code)

    assert site.calls == [("GET", "/")]


async def test_track_rejects_invalid_code_without_network(site: FakeTrack24, client: httpx.AsyncClient) -> None:
    """Input validation runs before any request."""
    code = " TEST00001"

    with pytest.raises(track24.InvalidTrackCodeError):
        await track24.track(client, code)

    assert site.requests == []


async def test_track_enforces_response_size_limit(
    site: FakeTrack24, client: httpx.AsyncClient, track_code: str
) -> None:
    """Oversized bodies are refused while streaming, before parsing."""
    site.page(" " * OVERSIZED_PADDING_BYTES)

    with pytest.raises(track24.ResponseTooLargeError):
        await track24.track(client, track_code)


async def test_track_rejects_non_object_json(site: FakeTrack24, client: httpx.AsyncClient, track_code: str) -> None:
    """A JSON array from the endpoint is malformed."""
    site.page()
    site.respond(json=[])

    with pytest.raises(track24.DecryptionError):
        await track24.track(client, track_code)


async def test_track_many_returns_outcomes_in_input_order(
    site: FakeTrack24, client: httpx.AsyncClient, batch_codes: list[str]
) -> None:
    """Several identifiers share one client and come back in the order they were given."""
    site.page()
    site.echo()

    outcomes = await track24.track_many(batch_codes, client=client)

    assert [outcome.code for outcome in outcomes] == batch_codes
    assert [outcome.result["data"]["trackCode"] for outcome in outcomes if outcome.result] == batch_codes


async def test_track_many_isolates_failures(
    site: FakeTrack24, client: httpx.AsyncClient, batch_codes: list[str]
) -> None:
    """One bad identifier does not affect the others."""
    site.page()
    site.echo()
    codes = [batch_codes[0], "bad code", batch_codes[1]]

    outcomes = await track24.track_many(codes, client=client)

    assert [outcome.ok for outcome in outcomes] == [True, False, True]
    assert outcomes[1].error == "InvalidTrackCodeError"


async def test_track_many_deduplicates_identifiers(
    site: FakeTrack24, client: httpx.AsyncClient, track_code: str
) -> None:
    """A repeated identifier is fetched once."""
    site.page()
    site.echo()

    outcomes = await track24.track_many([track_code] * 3, client=client)

    assert len(outcomes) == 1
    assert site.calls == [("GET", "/"), ("POST", ENDPOINT_PATH)]


async def test_track_many_runs_concurrently_within_limit(
    site: FakeTrack24, client: httpx.AsyncClient, batch_codes: list[str]
) -> None:
    """Requests overlap, but never exceed ``MAX_CONCURRENT_REQUESTS`` in flight."""
    site.page()
    site.echo(delay_seconds=CONCURRENCY_PROBE_DELAY_SECONDS)

    outcomes = await track24.track_many(batch_codes, client=client)

    assert all(outcome.ok for outcome in outcomes)
    assert 1 < site.peak_in_flight <= MAX_CONCURRENT_REQUESTS


async def test_track_many_reports_http_status(site: FakeTrack24, client: httpx.AsyncClient, track_code: str) -> None:
    """HTTP failures become ``http_error`` outcomes carrying the status code."""
    site.page()
    site.respond(status_code=HTTP_TOO_MANY_REQUESTS)

    outcomes = await track24.track_many([track_code], client=client)

    assert (outcomes[0].error, outcomes[0].http_status) == ("http_error", HTTP_TOO_MANY_REQUESTS)


async def test_track_many_closes_only_its_own_client(site: FakeTrack24, mocker: MockerFixture, track_code: str) -> None:
    """Without an injected client, ``track_many`` builds one via ``create_client`` and closes it."""
    site.page()
    site.echo()
    factory = mocker.spy(track24, "create_client")
    closer = mocker.spy(httpx.AsyncClient, "aclose")

    outcomes = await track24.track_many([track_code], timeout=CUSTOM_TIMEOUT_SECONDS)

    assert outcomes[0].ok
    factory.assert_called_once_with(CUSTOM_TIMEOUT_SECONDS)
    closer.assert_called_once()


async def test_track_many_leaves_injected_client_open(
    site: FakeTrack24, client: httpx.AsyncClient, mocker: MockerFixture, track_code: str
) -> None:
    """A caller-owned client is not closed and no second client is created."""
    site.page()
    site.echo()
    factory = mocker.spy(track24, "create_client")

    await track24.track_many([track_code], client=client)

    factory.assert_not_called()
    assert not client.is_closed


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ConnectTimeout])
async def test_connect_failure_is_retried_once(
    failure: type[httpx.TransportError],
    site: FakeTrack24,
    client: httpx.AsyncClient,
    ok_result: dict[str, Any],
    track_code: str,
) -> None:
    """A connection that could not be opened is retried; the request then succeeds."""
    site.fail_page(failure("synthetic"))
    site.page()
    site.payload(ok_result)

    result = await track24.track(client, track_code)

    assert result == ok_result
    assert site.calls == [("GET", "/"), ("GET", "/"), ("POST", ENDPOINT_PATH)]


async def test_persistent_connect_failure_gives_up(
    site: FakeTrack24, client: httpx.AsyncClient, track_code: str
) -> None:
    """After ``CONNECT_ATTEMPTS`` failures the error surfaces as a typed outcome."""
    site.fail_page(httpx.ConnectError("synthetic"), reusable=True)

    outcomes = await track24.track_many([track_code], client=client)

    assert outcomes[0].error == "ConnectError"
    assert len(site.requests) == CONNECT_ATTEMPTS


async def test_read_timeout_is_not_retried(site: FakeTrack24, client: httpx.AsyncClient, track_code: str) -> None:
    """A timeout after connecting may have reached Track24, so it is not repeated."""
    site.fail_page(httpx.ReadTimeout("synthetic"))

    outcomes = await track24.track_many([track_code], client=client)

    assert outcomes[0].error == "ReadTimeout"
    assert len(site.requests) == 1


async def test_envelope_decryption_uses_page_password(
    site: FakeTrack24,
    client: httpx.AsyncClient,
    encrypt: Encrypt,
    ok_result: dict[str, Any],
    track_code: str,
    mocker: MockerFixture,
) -> None:
    """The ``cp`` literal from the fetched page is the password handed to ``decrypt``."""
    site.page()
    site.payload(ok_result)
    decrypt = mocker.spy(track24, "decrypt")

    await track24.track(client, track_code)

    decrypt.assert_called_once_with(encrypt(ok_result), PASSWORD)
