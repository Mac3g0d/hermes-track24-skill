"""Unit tests for page parsing and endpoint discovery."""

import pytest

import track24
from constants import (
    PACKED_ENDPOINT_PATH,
    PACKED_SCRIPT,
    PACKED_SCRIPT_WITH_INVALID_RADIX,
    PACKED_SCRIPT_WITHOUT_ENDPOINT_WORD,
    TRACK24_BASE_URL,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"\x61\x62", "ab"),
        (r"тест", "тест"),
        (r"\/ajax\/a", "/ajax/a"),
        (r"say \"hi\" and \'bye\'", "say \"hi\" and 'bye'"),
        ("plain", "plain"),
    ],
)
def test_js_string_decodes_supported_escapes(raw: str, expected: str) -> None:
    """Arrange: an escaped literal body. Act: decode it. Assert: the plain text."""
    escaped = raw

    decoded = track24.js_string(escaped)

    assert decoded == expected


@pytest.mark.parametrize(
    "page",
    [
        'var cp="secret";',
        "var cp='secret';",
        'x=1;cp = "secret"; y=2',
    ],
)
def test_literal_reads_quoted_assignment(page: str) -> None:
    """Both quote styles and surrounding whitespace are accepted."""
    source = page

    value = track24.literal(source, "cp")

    assert value == "secret"


def test_literal_keeps_escaped_quote_inside_value() -> None:
    """An escaped quote does not terminate the literal early."""
    source = r'var cp="a\"b";'

    value = track24.literal(source, "cp")

    assert value == 'a"b'


def test_literal_does_not_match_name_suffix() -> None:
    """``xcp`` is a different identifier and must not satisfy ``cp``."""
    source = 'var xcp="secret";'

    with pytest.raises(track24.MissingLiteralError):
        track24.literal(source, "cp")


@pytest.mark.parametrize(("number", "radix", "expected"), [(0, 12, "0"), (11, 12, "b"), (35, 36, "z"), (36, 36, "10")])
def test_to_radix_matches_javascript_packer(number: int, radix: int, expected: str) -> None:
    """Word indexes are rendered in the packer's base."""
    value, base = number, radix

    rendered = track24.to_radix(value, base)

    assert rendered == expected


def test_discover_endpoint_from_plain_literal() -> None:
    """A direct ``trackingUrl`` assignment wins."""
    page = 'var trackingUrl="/ajax/test.ajax.php";'

    endpoint = track24.discover_endpoint(page)

    assert endpoint == f"{TRACK24_BASE_URL}/ajax/test.ajax.php"


def test_discover_endpoint_from_packed_script() -> None:
    """The dictionary-packed script is decoded as data."""
    page = PACKED_SCRIPT

    endpoint = track24.discover_endpoint(page)

    assert endpoint == TRACK24_BASE_URL + PACKED_ENDPOINT_PATH


@pytest.mark.parametrize(
    "page",
    [
        "<html></html>",
        PACKED_SCRIPT_WITHOUT_ENDPOINT_WORD,
        PACKED_SCRIPT_WITH_INVALID_RADIX,
    ],
)
def test_discover_endpoint_fails_closed(page: str) -> None:
    """Missing, unrelated or out-of-bounds packed scripts yield no endpoint."""
    source = page

    with pytest.raises(track24.EndpointError):
        track24.discover_endpoint(source)


def test_discover_endpoint_rejects_external_literal() -> None:
    """A discovered endpoint is still validated against the allowlist."""
    page = 'var trackingUrl="https://example.com/ajax/a.ajax.php";'

    with pytest.raises(track24.EndpointError):
        track24.discover_endpoint(page)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/ajax/a.ajax.php", f"{TRACK24_BASE_URL}/ajax/a.ajax.php"),
        (f"{TRACK24_BASE_URL}/ajax/b.ajax.php", f"{TRACK24_BASE_URL}/ajax/b.ajax.php"),
    ],
)
def test_validate_endpoint_accepts_track24_ajax(value: str, expected: str) -> None:
    """Relative and absolute Track24 ajax URLs resolve to the same origin."""
    candidate = value

    url = track24.validate_endpoint(candidate)

    assert url == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/ajax/a",
        "//evil.test/ajax/a",
        "http://track24.ru/ajax/a",
        "https://track24.ru:8443/ajax/a",
        "https://track24.ru.evil.test/ajax/a",
        "https://user@track24.ru/ajax/a",
        "https://track24.ru/api/a",
        "https://track24.ru/ajax/a?x=1",
        "https://track24.ru/ajax/a#frag",
    ],
)
def test_validate_endpoint_rejects_everything_else(value: str) -> None:
    """Other hosts, schemes, ports, credentials, paths, queries and fragments are refused."""
    candidate = value

    with pytest.raises(track24.EndpointError):
        track24.validate_endpoint(candidate)
