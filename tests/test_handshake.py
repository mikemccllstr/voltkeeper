# ABOUTME: Unit tests for BLE encryption handshake — legacy and ECDH paths per FINDINGS §15.2/§15.8.

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec

from voltkeeper.bluetooth.handshake import (
    derive_legacy_session_key,
    derive_shared_key,
    sign_app_pubkey,
    verify_device_pubkey,
)


def test_derive_legacy_session_key_kat():
    """Known-answer test for the legacy challenge-response derivation.

    CAVEAT: these expected values are SELF-CONSISTENT — they're what the
    current Python implementation produces, hand-traced step by step
    (reverse → MD5 → uppercase hex → ASCII-XOR against repeated
    LOCAL_AES_KEY → take first 16 bytes). They have NOT been validated
    against a real Bluetti device; FINDINGS §15.8 leaves the XOR
    interpretation ambiguous. If a real encrypted-device handshake fails
    in Unit 7 / production, suspect this test vector first and try the
    alternative interpretation: XOR `bytes.fromhex(random_md5_hex)`
    (16 bytes) against LOCAL_AES_KEY directly.

    The KAT still catches accidental algorithm drift (e.g., losing the
    reverse, swapping endianness, dropping the .upper(), computing MD5
    of the wrong thing).
    """
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(b"\x01\x02\x03\x04")

    assert random_md5_hex == "C73CABEB6558ABA030BBA9CA49DCDD75"
    assert ble_conn_aes_key.hex() == "06a8f676c1cb04b346a4d5a17fa1a80d"


def test_derive_legacy_session_key_shape_and_determinism():
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(b"\xde\xad\xbe\xef")

    # 32 hex chars, uppercase
    assert len(random_md5_hex) == 32
    assert random_md5_hex == random_md5_hex.upper()

    # Session key is 16 bytes
    assert len(ble_conn_aes_key) == 16

    # Deterministic: same input → same output
    h2, k2 = derive_legacy_session_key(b"\xde\xad\xbe\xef")
    assert h2 == random_md5_hex
    assert k2 == ble_conn_aes_key


def test_sign_app_pubkey_produces_64_bytes():
    fake_pub = b"\x04" * 64
    sig = sign_app_pubkey(fake_pub, "ABCDEF0123456789ABCDEF0123456789AB")
    assert len(sig) == 64


def test_verify_device_pubkey_raises_on_garbage():
    garbage_pub = b"\x03" * 64
    garbage_sig = b"\x00" * 64
    with pytest.raises((ValueError, InvalidSignature)):
        verify_device_pubkey(garbage_pub, garbage_sig, "ABCDEF0123456789ABCDEF0123456789AB")


def test_ecdh_determinism():
    # Generate two fixed ephemeral keypairs
    priv_a = ec.generate_private_key(ec.SECP256R1())
    priv_b = ec.generate_private_key(ec.SECP256R1())

    pub_a = priv_a.public_key()
    pub_b = priv_b.public_key()

    shared_ab = derive_shared_key(priv_a, pub_b)
    shared_ba = derive_shared_key(priv_b, pub_a)

    assert shared_ab == shared_ba
    assert len(shared_ab) == 16
