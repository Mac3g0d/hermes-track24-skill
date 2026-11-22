"""Read public Track24 tracking data without replaying another session's credentials."""

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import re
import sys
import urllib.parse
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from track24_constants import (
    AES_BLOCK_BYTES,
    AES_IV_BYTES,
    AES_KEY_BYTES,
    ACCEPT_HEADER_VALUE,
    AJAX_PATH_PREFIX,
    AJAX_PATH_SUFFIX,
    CLI_CODES_HELP,
    CLI_ENDPOINT_HELP,
    CLI_ERROR_HTTP,
    CLI_TIMEOUT_HELP,
    CONNECT_ATTEMPTS,
    CRYPTOJS_CIPHERTEXT_KEY,
    CRYPTOJS_IV_KEY,
    CRYPTOJS_SALT_BYTES,
    CRYPTOJS_SALT_KEY,
    DEFAULT_TIMEOUT_SECONDS,
    DELIVERED_FLAG_VALUE,
    ENDPOINT_LITERAL_NAME,
    ERROR_CHALLENGE,
    ERROR_DECRYPTION_FAILED,
    ERROR_ENDPOINT_NOT_ALLOWED,
    ERROR_ENDPOINT_NOT_DISCOVERED,
    ERROR_ENVELOPE_LENGTHS,
    ERROR_ENVELOPE_MALFORMED,
    ERROR_IDENTIFIER_MISMATCH,
    ERROR_INVALID_TRACK_CODE,
    ERROR_MISSING_LITERAL,
    ERROR_NON_OK_STATUS,
    ERROR_RESPONSE_TOO_LARGE,
    ERROR_TIMEOUT_RANGE,
    ERROR_TOO_MANY_CODES,
    ERROR_UNEXPECTED_REDIRECT,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    FORM_CONTENT_TYPE,
    HEX_RADIX,
    HTTP_METHOD_GET,
    HTTP_METHOD_POST,
    JS_DOUBLE_QUOTED_STRING_PATTERN,
    JS_HEX_ESCAPE_PATTERN,
    JS_LITERAL_ASSIGNMENT_TEMPLATE,
    JS_SIMPLE_ESCAPES,
    JS_UNICODE_ESCAPE_PATTERN,
    KEY_MATERIAL_BYTES,
    MAX_CONCURRENT_REQUESTS,
    MAX_RESPONSE_BYTES,
    MAX_TIMEOUT_SECONDS,
    MAX_TRACK_CODES_PER_RUN,
    PACKER_DIGITS,
    PACKER_DOUBLE_BACKSLASH,
    PACKER_MAX_PAYLOAD_CHARS,
    PACKER_MAX_RADIX,
    PACKER_MAX_WORDS,
    PACKER_MIN_RADIX,
    PACKER_PATTERN,
    PACKER_SINGLE_BACKSLASH,
    PACKER_WORD_SEPARATOR,
    PASSWORD_LITERAL_NAME,
    RESPONSE_STATUS_OK,
    TEXT_ENCODING,
    TRACK24_HOST,
    TRACK24_ORIGIN,
    TRACK24_PAGE_CODE_PARAMETER,
    TRACK24_SCHEME,
    TRACK_CODE_PATTERN,
    TRACKING_FORM_DEFAULTS,
)


class Track24Error(ValueError):
    """Base class for every failure the tracker reports deliberately."""


class InvalidTrackCodeError(Track24Error):
    """The identifier does not look like a tracking code and was not repaired."""


class MissingLiteralError(Track24Error):
    """The public page does not contain an expected JavaScript literal."""


class EndpointError(Track24Error):
    """The tracking endpoint is missing or is outside the allowed Track24 path."""


class DecryptionError(Track24Error):
    """The CryptoJS envelope cannot be decoded with the page password."""


class ResponseTooLargeError(Track24Error):
    """The server returned more bytes than the configured safety limit."""


class ChallengeError(Track24Error):
    """The site asked for an interactive challenge; it is never bypassed."""


class ServiceStatusError(Track24Error):
    """The decrypted response reports a status other than ``ok``."""


class IdentifierMismatchError(Track24Error):
    """The response describes a different parcel than the one requested."""


class UnexpectedRedirectError(Track24Error):
    """Track24 answered with a redirect, which is never followed."""


@dataclass(frozen=True)
class TrackOutcome:
    """The result of tracking one identifier: either ``result`` or an error description."""

    code: str
    result: dict[str, Any] | None = None
    error: str | None = None
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        """``True`` when the identifier was fetched and verified."""
        return self.result is not None


def js_string(value: str) -> str:
    """Decode only the JavaScript string escapes observed in Track24 literals."""
    decoded = JS_HEX_ESCAPE_PATTERN.sub(lambda match: chr(int(match[1], HEX_RADIX)), value)
    decoded = JS_UNICODE_ESCAPE_PATTERN.sub(lambda match: chr(int(match[1], HEX_RADIX)), decoded)
    for escape, replacement in JS_SIMPLE_ESCAPES.items():
        decoded = decoded.replace(escape, replacement)
    return decoded


def literal(text: str, name: str) -> str:
    """Return the decoded string assigned to ``name`` in page source ``text``."""
    pattern = JS_LITERAL_ASSIGNMENT_TEMPLATE.format(name=re.escape(name))
    match = re.search(pattern, text)
    if match is None:
        raise MissingLiteralError(ERROR_MISSING_LITERAL.format(name=name))
    return js_string(match[2])


def to_radix(number: int, radix: int) -> str:
    """Render a non-negative integer the way the JavaScript packer encodes word indexes."""
    if number == 0:
        return PACKER_DIGITS[0]
    digits = ""
    while number:
        number, remainder = divmod(number, radix)
        digits = PACKER_DIGITS[remainder] + digits
    return digits


def unpack_dictionary(packed: str, radix: int, count: int, words: Sequence[str]) -> str:
    """Substitute packer word indexes with dictionary words, treating the payload as data."""
    unpacked = packed
    for index in range(min(count, len(words)) - 1, -1, -1):
        word = words[index]
        if word:
            token = re.compile(r"\b" + to_radix(index, radix) + r"\b")
            unpacked = token.sub(lambda _match, replacement=word: replacement, unpacked)
    return unpacked


def endpoint_from_packed(html: str) -> str | None:
    """Find an ``/ajax/`` endpoint inside the observed dictionary-packed script."""
    for match in PACKER_PATTERN.finditer(html):
        packed, radix_text, count_text, words_text = match.groups()
        radix, count = int(radix_text), int(count_text)
        if not PACKER_MIN_RADIX <= radix <= PACKER_MAX_RADIX:
            continue
        if count > PACKER_MAX_WORDS or len(packed) > PACKER_MAX_PAYLOAD_CHARS:
            continue
        unpacked = unpack_dictionary(packed, radix, count, words_text.split(PACKER_WORD_SEPARATOR))
        if ENDPOINT_LITERAL_NAME not in unpacked:
            continue
        unescaped = unpacked.replace(PACKER_DOUBLE_BACKSLASH, PACKER_SINGLE_BACKSLASH)
        for candidate in JS_DOUBLE_QUOTED_STRING_PATTERN.findall(unescaped):
            decoded = js_string(candidate)
            if decoded.startswith(AJAX_PATH_PREFIX) and decoded.endswith(AJAX_PATH_SUFFIX):
                return decoded
    return None


def discover_endpoint(html: str) -> str:
    """Locate the tracking endpoint in page HTML without executing JavaScript."""
    try:
        value: str | None = literal(html, ENDPOINT_LITERAL_NAME)
    except MissingLiteralError:
        value = endpoint_from_packed(html)
    if not value:
        raise EndpointError(ERROR_ENDPOINT_NOT_DISCOVERED)
    return validate_endpoint(value)


def validate_endpoint(value: str) -> str:
    """Resolve ``value`` against Track24 and accept only HTTPS ``/ajax/`` URLs on its host."""
    url = urllib.parse.urljoin(TRACK24_ORIGIN + "/", value)
    parts = urllib.parse.urlsplit(url)
    allowed = (
        parts.scheme == TRACK24_SCHEME
        and parts.netloc == TRACK24_HOST
        and parts.path.startswith(AJAX_PATH_PREFIX)
        and not parts.query
        and not parts.fragment
    )
    if not allowed:
        raise EndpointError(ERROR_ENDPOINT_NOT_ALLOWED)
    return url


def derive_key_material(password: str, salt: bytes) -> bytes:
    """Reproduce OpenSSL ``EVP_BytesToKey`` with MD5, as used by CryptoJS passphrases."""
    material, previous = b"", b""
    secret = password.encode(TEXT_ENCODING)
    while len(material) < KEY_MATERIAL_BYTES:
        previous = hashlib.md5(previous + secret + salt).digest()
        material += previous
    return material


def decrypt(envelope: dict[str, Any], password: str) -> dict[str, Any]:
    """Decode a CryptoJS JSON envelope; plain JSON objects are returned unchanged."""
    if CRYPTOJS_CIPHERTEXT_KEY not in envelope:
        return envelope
    try:
        salt = bytes.fromhex(envelope[CRYPTOJS_SALT_KEY])
        iv = bytes.fromhex(envelope[CRYPTOJS_IV_KEY])
        ciphertext = base64.b64decode(envelope[CRYPTOJS_CIPHERTEXT_KEY], validate=True)
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        raise DecryptionError(ERROR_ENVELOPE_MALFORMED) from exc
    if len(salt) != CRYPTOJS_SALT_BYTES or len(iv) != AES_IV_BYTES:
        raise DecryptionError(ERROR_ENVELOPE_LENGTHS)
    key = derive_key_material(password, salt)[:AES_KEY_BYTES]
    try:
        plain = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
        decoded = json.loads(unpad(plain, AES_BLOCK_BYTES).decode(TEXT_ENCODING))
    except (ValueError, UnicodeDecodeError) as exc:
        raise DecryptionError(ERROR_DECRYPTION_FAILED) from exc
    if not isinstance(decoded, dict):
        raise DecryptionError(ERROR_DECRYPTION_FAILED)
    return decoded


async def fetch_once(client: httpx.AsyncClient, url: str, data: bytes | None) -> bytes:
    """Perform one GET or form POST, refuse redirects and enforce the response size limit."""
    headers = {"Accept": ACCEPT_HEADER_VALUE}
    method = HTTP_METHOD_GET
    if data is not None:
        headers["Content-Type"] = FORM_CONTENT_TYPE
        method = HTTP_METHOD_POST
    async with client.stream(method, url, headers=headers, content=data) as response:
        if response.is_redirect:
            raise UnexpectedRedirectError(ERROR_UNEXPECTED_REDIRECT)
        response.raise_for_status()
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ResponseTooLargeError(ERROR_RESPONSE_TOO_LARGE)
    return bytes(body)


async def fetch(client: httpx.AsyncClient, url: str, data: bytes | None = None) -> bytes:
    """Fetch ``url``, retrying only when no connection could be opened.

    A connection failure means no request reached Track24, so repeating it is safe.
    HTTP errors, challenges and timeouts after connecting are never retried.
    """
    attempts_left = CONNECT_ATTEMPTS
    while True:
        try:
            return await fetch_once(client, url, data)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            attempts_left -= 1
            if attempts_left <= 0:
                raise


def validate_track_code(code: str) -> str:
    """Return ``code`` unchanged when valid; never normalize user input."""
    if not TRACK_CODE_PATTERN.fullmatch(code):
        raise InvalidTrackCodeError(ERROR_INVALID_TRACK_CODE)
    return code


def build_form(code: str) -> bytes:
    """Encode the tracking POST body for ``code``."""
    fields = {TRACK24_PAGE_CODE_PARAMETER: code, **TRACKING_FORM_DEFAULTS}
    return urllib.parse.urlencode(fields).encode(TEXT_ENCODING)


def verify_result(result: dict[str, Any], code: str) -> dict[str, Any]:
    """Reject challenges, non-ok statuses and responses for another identifier."""
    if result.get("challenge"):
        raise ChallengeError(ERROR_CHALLENGE)
    if result.get("status") != RESPONSE_STATUS_OK:
        raise ServiceStatusError(ERROR_NON_OK_STATUS)
    data = result.get("data")
    if not isinstance(data, dict) or data.get("trackCode") != code:
        raise IdentifierMismatchError(ERROR_IDENTIFIER_MISMATCH)
    return result


async def track(
    client: httpx.AsyncClient,
    code: str,
    endpoint: str | None = None,
) -> dict[str, Any]:
    """Fetch, decrypt and verify the Track24 result for the exact identifier ``code``."""
    validate_track_code(code)
    query = urllib.parse.urlencode({TRACK24_PAGE_CODE_PARAMETER: code})
    page = (await fetch(client, f"{TRACK24_ORIGIN}/?{query}")).decode(TEXT_ENCODING)
    password = literal(page, PASSWORD_LITERAL_NAME)
    target = validate_endpoint(endpoint) if endpoint else discover_endpoint(page)
    envelope = json.loads(await fetch(client, target, build_form(code)))
    if not isinstance(envelope, dict):
        raise DecryptionError(ERROR_ENVELOPE_MALFORMED)
    return verify_result(decrypt(envelope, password), code)


async def track_outcome(
    client: httpx.AsyncClient,
    code: str,
    endpoint: str | None,
    limiter: asyncio.Semaphore,
) -> TrackOutcome:
    """Track one identifier and convert every failure into a typed, content-free outcome."""
    async with limiter:
        try:
            result = await track(client, code, endpoint)
        except httpx.HTTPStatusError as exc:
            return TrackOutcome(code, error=CLI_ERROR_HTTP, http_status=exc.response.status_code)
        except Exception as exc:
            return TrackOutcome(code, error=type(exc).__name__)
    return TrackOutcome(code, result=result)


def unique_codes(codes: Sequence[str]) -> list[str]:
    """Drop repeated identifiers while keeping the caller's order."""
    return list(dict.fromkeys(codes))


def create_client(timeout: float) -> httpx.AsyncClient:
    """Build the shared HTTP client; redirects are refused rather than followed."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


async def track_many(
    codes: Sequence[str],
    endpoint: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.AsyncClient | None = None,
) -> list[TrackOutcome]:
    """Track several identifiers concurrently over one connection pool, in input order."""
    limiter = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    active_client = client or create_client(timeout)
    try:
        tasks = [track_outcome(active_client, code, endpoint, limiter) for code in unique_codes(codes)]
        return list(await asyncio.gather(*tasks))
    finally:
        if client is None:
            await active_client.aclose()


def summary(result: dict[str, Any]) -> dict[str, Any]:
    """Reduce a verified result to status fields; addresses and session data are dropped."""
    data = result["data"]
    point = data.get("lastPoint") or {}
    return {
        "track": data["trackCode"],
        "status": result["status"],
        "last_event_id": point.get("id"),
        "operation_time": point.get("operationDateTime"),
        "operation": point.get("operationAttribute"),
        "carrier": point.get("serviceName"),
        "delivered": str(data.get("deliveredStatus")) == DELIVERED_FLAG_VALUE,
        "source_updated_at": data.get("trackUpdateDateTime"),
        "sources": result.get("sources"),
        "timezone": None,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes", nargs="+", metavar="code", help=CLI_CODES_HELP)
    parser.add_argument("--endpoint", help=CLI_ENDPOINT_HELP)
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help=CLI_TIMEOUT_HELP
    )
    return parser


def render_outcome(outcome: TrackOutcome) -> str:
    """Serialize a failed outcome without raw responses, keys or addresses."""
    error: dict[str, Any] = {"track": outcome.code, "ok": False, "error": outcome.error}
    if outcome.http_status is not None:
        error["http_status"] = outcome.http_status
    return json.dumps(error, ensure_ascii=False)


async def run(
    argv: Sequence[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> int:
    """Parse arguments, track every identifier and print one JSON line per identifier."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= MAX_TIMEOUT_SECONDS:
        parser.error(ERROR_TIMEOUT_RANGE)
    if len(unique_codes(args.codes)) > MAX_TRACK_CODES_PER_RUN:
        parser.error(ERROR_TOO_MANY_CODES)
    outcomes = await track_many(args.codes, args.endpoint, args.timeout, client)
    for outcome in outcomes:
        if outcome.result is not None:
            print(json.dumps(summary(outcome.result), ensure_ascii=False))
        else:
            print(render_outcome(outcome), file=sys.stderr)
    return EXIT_SUCCESS if all(outcome.ok for outcome in outcomes) else EXIT_FAILURE


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous CLI entry point."""
    return asyncio.run(run(argv))


if __name__ == "__main__":
    sys.exit(main())
