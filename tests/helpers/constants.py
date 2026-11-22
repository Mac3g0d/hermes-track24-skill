"""Synthetic test data; none of these values come from a real parcel or session."""

from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
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
TRACK24_BASE_URL: Final[str] = "https://track24.ru"
LOOPBACK_HOST: Final[str] = "127.0.0.1"

EVENT_ID: Final[str] = "synthetic-event-1"
EVENT_TIME: Final[str] = "01.01.2000 12:00:00"
EVENT_OPERATION: Final[str] = "Synthetic arrival"
EVENT_CARRIER: Final[str] = "Synthetic Post"
SOURCE_UPDATED_AT: Final[str] = "01.01.2000 12:30:00"
SOURCES: Final[str] = "cache"
SECRET_ADDRESS: Final[str] = "Synthetic Street 1, Nowhere"

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
HTTP_NOT_FOUND: Final[int] = 404
LOOPBACK_SCHEME: Final[str] = "http"
HTTP_TOO_MANY_REQUESTS: Final[int] = 429
JSON_CONTENT_TYPE: Final[str] = "application/json"
HTML_CONTENT_TYPE: Final[str] = "text/html; charset=utf-8"
OVERSIZED_PADDING_BYTES: Final[int] = 8_000_001
CLI_TIMEOUT_ARGUMENT: Final[str] = "5"
OUT_OF_RANGE_TIMEOUT: Final[str] = "121"
SUBPROCESS_TIMEOUT_SECONDS: Final[float] = 30.0
SERVER_POLL_INTERVAL_SECONDS: Final[float] = 0.01
