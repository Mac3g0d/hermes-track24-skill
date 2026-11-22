"""Fixtures that build CryptoJS envelopes independently from the code under test."""

import base64
import hashlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

from constants import AES_BLOCK_BYTES, AES_KEY_BYTES, IV, KEY_MATERIAL_BYTES, PASSWORD, SALT

Encrypt = Callable[..., dict[str, str]]
DeriveKey = Callable[[str, bytes], bytes]


def openssl_key(password: str, salt: bytes) -> bytes:
    """Independent EVP_BytesToKey implementation so tests do not trust the code under test."""
    material, previous = b"", b""
    while len(material) < KEY_MATERIAL_BYTES:
        previous = hashlib.md5(previous + password.encode() + salt, usedforsecurity=False).digest()
        material += previous
    return material[:AES_KEY_BYTES]


def encrypt_envelope(payload: Any, password: str = PASSWORD, salt: bytes = SALT, iv: bytes = IV) -> dict[str, str]:
    """Encrypt ``payload`` as JSON into a CryptoJS-style ``{ct, iv, s}`` envelope."""
    plain = pad(json.dumps(payload).encode(), AES_BLOCK_BYTES)
    ciphertext = AES.new(openssl_key(password, salt), AES.MODE_CBC, iv).encrypt(plain)
    return {"ct": base64.b64encode(ciphertext).decode(), "iv": iv.hex(), "s": salt.hex()}


@pytest.fixture
def encrypt() -> Encrypt:
    """Return the envelope builder used by the browser client format."""
    return encrypt_envelope


@pytest.fixture
def derive_key() -> DeriveKey:
    """Return the reference AES key derivation."""
    return openssl_key
