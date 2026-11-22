"""Unit tests for envelope decryption, input validation and result reduction."""

import json
from typing import Any

import pytest

import track24
from helpers.constants import (
    AES_KEY_BYTES,
    KEY_MATERIAL_BYTES,
    EVENT_CARRIER,
    EVENT_ID,
    EVENT_OPERATION,
    EVENT_TIME,
    OTHER_TRACK_CODE,
    PASSWORD,
    SECRET_ADDRESS,
    SOURCE_UPDATED_AT,
    SOURCES,
    TRACK_CODE,
    WRONG_PASSWORD,
)
from helpers.crypto import encrypt_envelope, openssl_key


def test_derive_key_material_matches_independent_implementation() -> None:
    """The first 32 bytes are the AES key used by CryptoJS."""
    salt = b"abcdefgh"

    material = track24.derive_key_material(PASSWORD, salt)

    assert material[:AES_KEY_BYTES] == openssl_key(PASSWORD, salt)
    assert len(material) == KEY_MATERIAL_BYTES


def test_decrypt_round_trips_synthetic_envelope(ok_result: dict[str, Any]) -> None:
    """An envelope built like the browser client decrypts to the original object."""
    envelope = encrypt_envelope(ok_result)

    decrypted = track24.decrypt(envelope, PASSWORD)

    assert decrypted == ok_result


def test_decrypt_passes_plain_objects_through() -> None:
    """Unencrypted JSON responses are returned as-is."""
    plain = {"status": "error"}

    decrypted = track24.decrypt(plain, PASSWORD)

    assert decrypted is plain


def test_decrypt_with_wrong_password_fails(ok_result: dict[str, Any]) -> None:
    """A wrong key must never yield a silently corrupted result."""
    envelope = encrypt_envelope(ok_result)

    with pytest.raises(track24.DecryptionError):
        track24.decrypt(envelope, WRONG_PASSWORD)


@pytest.mark.parametrize(
    "mutation",
    [
        {"s": "0011"},
        {"iv": "00"},
        {"s": "zz"},
        {"ct": "not base64!"},
        {"iv": None},
    ],
)
def test_decrypt_rejects_malformed_envelopes(mutation: dict[str, Any], ok_result: dict[str, Any]) -> None:
    """Bad salt/IV lengths, bad hex and bad base64 all raise ``DecryptionError``."""
    envelope = {**encrypt_envelope(ok_result), **mutation}

    with pytest.raises(track24.DecryptionError):
        track24.decrypt(envelope, PASSWORD)


def test_decrypt_rejects_missing_salt(ok_result: dict[str, Any]) -> None:
    """An envelope without ``s`` is malformed rather than a ``KeyError``."""
    envelope = encrypt_envelope(ok_result)
    del envelope["s"]

    with pytest.raises(track24.DecryptionError):
        track24.decrypt(envelope, PASSWORD)


def test_decrypt_rejects_non_object_plaintext() -> None:
    """A decrypted JSON array is not a valid tracking response."""
    envelope = encrypt_envelope([1, 2, 3])

    with pytest.raises(track24.DecryptionError):
        track24.decrypt(envelope, PASSWORD)


@pytest.mark.parametrize("code", ["TEST00001", "RA123456789CN", "ab-12.3", "A(1)/2345"])
def test_validate_track_code_accepts_and_preserves(code: str) -> None:
    """Valid identifiers come back byte-for-byte."""
    candidate = code

    validated = track24.validate_track_code(candidate)

    assert validated == candidate


@pytest.mark.parametrize("code", ["", "abcd", " TEST00001", "TEST00001 ", "-TEST0001", "TEST&0001", "A" * 33, "ТЕСТ00001"])
def test_validate_track_code_rejects_without_normalizing(code: str) -> None:
    """Whitespace, punctuation, non-ASCII and length violations are refused, not repaired."""
    candidate = code

    with pytest.raises(track24.InvalidTrackCodeError):
        track24.validate_track_code(candidate)


def test_build_form_contains_exact_fields() -> None:
    """The POST body mirrors the browser client's fields."""
    code = TRACK_CODE

    form = track24.build_form(code).decode()

    assert form == f"code={TRACK_CODE}&selectedService=&lng=ru&sort=true&grouped=false&type=cache"


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"challenge": True}, track24.ChallengeError),
        ({"status": "error"}, track24.ServiceStatusError),
        ({"data": None}, track24.IdentifierMismatchError),
        ({"data": {"trackCode": OTHER_TRACK_CODE}}, track24.IdentifierMismatchError),
    ],
)
def test_verify_result_rejects_untrusted_responses(
    override: dict[str, Any], error: type[Exception], ok_result: dict[str, Any]
) -> None:
    """Challenges, error statuses and foreign identifiers never count as success."""
    result = {**ok_result, **override}

    with pytest.raises(error):
        track24.verify_result(result, TRACK_CODE)


def test_summary_reports_latest_point_fields(ok_result: dict[str, Any]) -> None:
    """The summary is exactly the documented status shape."""
    result = ok_result

    reduced = track24.summary(result)

    assert reduced == {
        "track": TRACK_CODE,
        "status": "ok",
        "last_event_id": EVENT_ID,
        "operation_time": EVENT_TIME,
        "operation": EVENT_OPERATION,
        "carrier": EVENT_CARRIER,
        "delivered": False,
        "source_updated_at": SOURCE_UPDATED_AT,
        "sources": SOURCES,
        "timezone": None,
    }


def test_summary_never_leaks_address(ok_result: dict[str, Any]) -> None:
    """Delivery addresses in the raw data are dropped."""
    result = ok_result

    serialized = json.dumps(track24.summary(result), ensure_ascii=False)

    assert SECRET_ADDRESS not in serialized


@pytest.mark.parametrize(("flag", "delivered"), [("1", True), (1, True), ("0", False), (0, False), (None, False), ("true", False)])
def test_summary_delivered_flag(flag: Any, delivered: bool, ok_result: dict[str, Any]) -> None:
    """Only the value ``1`` marks a parcel as delivered."""
    ok_result["data"]["deliveredStatus"] = flag

    reduced = track24.summary(ok_result)

    assert reduced["delivered"] is delivered


def test_summary_tolerates_missing_last_point(ok_result: dict[str, Any]) -> None:
    """Without ``lastPoint`` the event fields are ``None`` rather than guessed from ``events``."""
    ok_result["data"]["lastPoint"] = None
    ok_result["data"]["events"] = [{"id": "older"}, {"id": "newer"}]

    reduced = track24.summary(ok_result)

    assert reduced["last_event_id"] is None
    assert reduced["operation_time"] is None
