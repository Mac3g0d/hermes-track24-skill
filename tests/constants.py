"""Synthetic test data; none of these values come from a real parcel or session."""

import re
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TESTS_DIRECTORY: Final[Path] = REPOSITORY_ROOT / "tests"
INTEGRATION_MODULE_PREFIX: Final[str] = "test_integration_"
PYPROJECT_VERSION_PATTERN: Final[str] = r'^version = "([^"]+)"'
PEP723_BLOCK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)
PEP723_BLOCK_TYPE: Final[str] = "script"
PEP723_LINE_PREFIX: Final[str] = "# "
SKILLS_DIRECTORY: Final[Path] = REPOSITORY_ROOT / "skills"
SKILL_NAME: Final[str] = "track24-parcel-tracking"
SKILL_DIRECTORY: Final[Path] = SKILLS_DIRECTORY / SKILL_NAME
SKILL_MANIFEST: Final[Path] = SKILL_DIRECTORY / "SKILL.md"
SCRIPTS_DIRECTORY: Final[Path] = SKILL_DIRECTORY / "scripts"
TRACKER_SCRIPT: Final[Path] = SCRIPTS_DIRECTORY / "track24.py"
CONSTANTS_MODULE: Final[Path] = SCRIPTS_DIRECTORY / "track24_constants.py"
SKILL_NAME_PATTERN: Final[str] = r"[a-z][a-z0-9_-]*"
FRONTMATTER_DELIMITER: Final[str] = "---"
ALLOWED_SKILL_SUBDIRECTORIES: Final[frozenset[str]] = frozenset(
    {"references", "templates", "scripts", "assets", "examples"}
)

TRACK_CODE: Final[str] = "TEST00001"
OTHER_TRACK_CODE: Final[str] = "TEST00002"
PASSWORD: Final[str] = "test-only-passphrase"
WRONG_PASSWORD: Final[str] = "not-the-passphrase"
SALT: Final[bytes] = b"12345678"
IV: Final[bytes] = b"0123456789abcdef"
KEY_MATERIAL_BYTES: Final[int] = 48
AES_KEY_BYTES: Final[int] = 32
AES_BLOCK_BYTES: Final[int] = 16

ENDPOINT_PATH: Final[str] = "/ajax/synthetic.ajax.php"
PACKED_ENDPOINT_PATH: Final[str] = "/ajax/t.ajax.php"
OVERRIDE_ENDPOINT_PATH: Final[str] = "/ajax/override.ajax.php"
TRACK24_HOST: Final[str] = "track24.ru"
TRACK24_BASE_URL: Final[str] = f"https://{TRACK24_HOST}"
PAGE_URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"https://track24\.ru/\?code=.+")
ENDPOINT_URL: Final[str] = f"{TRACK24_BASE_URL}/ajax/synthetic.ajax.php"
CONCURRENCY_PROBE_DELAY_SECONDS: Final[float] = 0.05
HTTP_FOUND: Final[int] = 302

SOURCES: Final[tuple[str, ...]] = ("cache",)
TRACK_CODE_PREFIX: Final[str] = "TEST"
TRACK_CODE_DIGITS: Final[int] = 9
EVENT_ID_DIGITS: Final[int] = 9
EVENT_DATETIME_FORMAT: Final[str] = "%d.%m.%Y %H:%M:%S"
BATCH_SIZE: Final[int] = 5

PAGE_WITH_LITERAL_TEMPLATE: Final[str] = (
    '<html><script>var cp="{password}";var trackingUrl="{endpoint}";</script></html>'
)
PAGE_WITHOUT_ENDPOINT_TEMPLATE: Final[str] = '<html><script>var cp="{password}";</script></html>'
PAGE_WITHOUT_PASSWORD: Final[str] = '<html><script>var trackingUrl="/ajax/x.ajax.php";</script></html>'
PACKED_SCRIPT: Final[str] = (
    r'''eval(function(p,a,c,k,e,d){return p}('0 a=["\\x2f\\x61\\x6a\\x61\\x78\\x2f\\x74\\x2e'''
    r'''\\x61\\x6a\\x61\\x78\\x2e\\x70\\x68\\x70"];0 b=a[1];',12,12,'var|||||||||||'''
    r'''trackingUrl'.split('|')));'''
)
PACKED_SCRIPT_WITHOUT_ENDPOINT_WORD: Final[str] = (
    r'''eval(function(p,a,c,k,e,d){return p}('0 a=["\\x2f\\x61\\x6a\\x61\\x78\\x2f\\x74\\x2e'''
    r'''\\x61\\x6a\\x61\\x78\\x2e\\x70\\x68\\x70"];',12,12,'var|||||||||||'''
    r'''otherName'.split('|')));'''
)
PACKED_SCRIPT_WITH_INVALID_RADIX: Final[str] = (
    r'''eval(function(p,a,c,k,e,d){return p}('0 a=["/ajax/t.ajax.php"];0 b=a[1];',99,12,'var'''
    r'''|||||||||||trackingUrl'.split('|')));'''
)
PAGE_WITH_PACKED_TEMPLATE: Final[str] = '<html><script>var cp="{password}";{packed}</script></html>'

HTTP_OK: Final[int] = 200
HTTP_FORBIDDEN: Final[int] = 403
HTTP_TOO_MANY_REQUESTS: Final[int] = 429
OVERSIZED_PADDING_BYTES: Final[int] = 8_000_001
CLI_TIMEOUT_ARGUMENT: Final[str] = "5"
CUSTOM_TIMEOUT_SECONDS: Final[float] = 5.0
OUT_OF_RANGE_TIMEOUT: Final[str] = "121"
SUBPROCESS_TIMEOUT_SECONDS: Final[float] = 30.0
