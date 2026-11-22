"""Constants shared by the Track24 tracking script.

Every value here is a module-level name annotated with ``typing.Final`` so that
static type checkers reject accidental reassignment.
"""

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

TRACK24_SCHEME: Final[str] = "https"
TRACK24_HOST: Final[str] = "track24.ru"
TRACK24_ORIGIN: Final[str] = f"{TRACK24_SCHEME}://{TRACK24_HOST}"
TRACK24_PAGE_CODE_PARAMETER: Final[str] = "code"

AJAX_PATH_PREFIX: Final[str] = "/ajax/"
AJAX_PATH_SUFFIX: Final[str] = ".ajax.php"

CIPHER_KEY_LITERAL_NAME: Final[str] = "cp"
ENDPOINT_LITERAL_NAME: Final[str] = "trackingUrl"

TRACK_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9.()/\-]{4,31}")

JS_HEX_ESCAPE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\\x([0-9a-fA-F]{2})")
JS_UNICODE_ESCAPE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\\u([0-9a-fA-F]{4})")
JS_SIMPLE_ESCAPES: Final[Mapping[str, str]] = MappingProxyType(
    {
        r"\/": "/",
        r"\"": '"',
        r"\'": "'",
    }
)
JS_DOUBLE_QUOTED_STRING_PATTERN: Final[re.Pattern[str]] = re.compile(r'"((?:\\.|[^"\\])*)"')
JS_LITERAL_ASSIGNMENT_TEMPLATE: Final[str] = r"\b{name}\s*=\s*([\x27\x22])((?:\\.|(?!\1).)*)\1"
HEX_RADIX: Final[int] = 16

PACKER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\}\('((?:\\.|[^'\\])*)',(\d+),(\d+),'([^']*)'\.split\('\|'\)")
PACKER_WORD_SEPARATOR: Final[str] = "|"
PACKER_DIGITS: Final[str] = "0123456789abcdefghijklmnopqrstuvwxyz"
PACKER_MIN_RADIX: Final[int] = 2
PACKER_MAX_RADIX: Final[int] = 36
PACKER_MAX_WORDS: Final[int] = 5000
PACKER_MAX_PAYLOAD_CHARS: Final[int] = 100_000
PACKER_DOUBLE_BACKSLASH: Final[str] = "\\\\"
PACKER_SINGLE_BACKSLASH: Final[str] = "\\"

TEXT_ENCODING: Final[str] = "utf-8"
MAX_RESPONSE_BYTES: Final[int] = 8_000_000
DEFAULT_TIMEOUT_SECONDS: Final[float] = 25.0
MAX_TIMEOUT_SECONDS: Final[float] = 120.0
MAX_TRACK_CODES_PER_RUN: Final[int] = 10
MAX_CONCURRENT_REQUESTS: Final[int] = 3
CONNECT_ATTEMPTS: Final[int] = 2
HTTP_METHOD_GET: Final[str] = "GET"
HTTP_METHOD_POST: Final[str] = "POST"

ACCEPT_HEADER_VALUE: Final[str] = "application/json, text/javascript, */*; q=0.01"
FORM_CONTENT_TYPE: Final[str] = "application/x-www-form-urlencoded; charset=UTF-8"
TRACKING_FORM_DEFAULTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "selectedService": "",
        "lng": "ru",
        "sort": "true",
        "grouped": "false",
        "type": "cache",
    }
)

CRYPTOJS_CIPHERTEXT_KEY: Final[str] = "ct"
CRYPTOJS_IV_KEY: Final[str] = "iv"
CRYPTOJS_SALT_KEY: Final[str] = "s"
CRYPTOJS_SALT_BYTES: Final[int] = 8
AES_IV_BYTES: Final[int] = 16
AES_KEY_BYTES: Final[int] = 32
AES_BLOCK_BYTES: Final[int] = 16
KEY_MATERIAL_BYTES: Final[int] = AES_KEY_BYTES + AES_IV_BYTES

RESPONSE_STATUS_OK: Final[str] = "ok"
DELIVERED_FLAG_VALUE: Final[str] = "1"

EXIT_SUCCESS: Final[int] = 0
EXIT_FAILURE: Final[int] = 1

ERROR_MISSING_LITERAL: Final[str] = "Missing page literal: {name}"
ERROR_ENDPOINT_NOT_DISCOVERED: Final[str] = "Cannot discover tracking endpoint; supply --endpoint from DevTools"
ERROR_ENDPOINT_NOT_ALLOWED: Final[str] = "Endpoint must be an HTTPS /ajax/ URL on track24.ru"
ERROR_ENVELOPE_LENGTHS: Final[str] = "Unexpected CryptoJS salt/IV length"
ERROR_ENVELOPE_MALFORMED: Final[str] = "Malformed CryptoJS envelope"
ERROR_DECRYPTION_FAILED: Final[str] = "Cannot decrypt CryptoJS envelope"
ERROR_RESPONSE_TOO_LARGE: Final[str] = "Response exceeds size limit"
ERROR_INVALID_TRACK_CODE: Final[str] = "Invalid tracking identifier; input was not normalized"
ERROR_CHALLENGE: Final[str] = "Site challenge requires operator action; not bypassed"
ERROR_NON_OK_STATUS: Final[str] = "Tracking service returned a non-ok status"
ERROR_IDENTIFIER_MISMATCH: Final[str] = "Response does not match the exact requested identifier"
ERROR_TIMEOUT_RANGE: Final[str] = "--timeout must be between 0 and 120 seconds"
ERROR_TOO_MANY_CODES: Final[str] = "At most 10 tracking identifiers per run"
ERROR_UNEXPECTED_REDIRECT: Final[str] = "Track24 answered with a redirect; not followed"

CLI_ERROR_HTTP: Final[str] = "http_error"
CLI_ENDPOINT_HELP: Final[str] = "Optional observed Track24 /ajax/ URL"
CLI_TIMEOUT_HELP: Final[str] = "Request timeout in seconds"
CLI_CODES_HELP: Final[str] = "One or more exact tracking identifiers (at most 10)"
