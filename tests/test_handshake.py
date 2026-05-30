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

    Matches ConnectManager.bleEncryptedHandle: randomMd5 = lowercase MD5 of the
    reversed random bytes; bleConnAESKey = byte-wise XOR of the decoded digest
    and the decoded LOCAL_AES_KEY (16 bytes). Cross-checked against the captured
    Elite 100 V2 vector in test_handshake_framing.py.

    The KAT catches accidental algorithm drift (losing the reverse, dropping the
    hex-decode of the digest, computing MD5 of the wrong thing).
    """
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(b"\x01\x02\x03\x04")

    assert random_md5_hex == "c73cabeb6558aba030bba9ca49dcdd75"
    assert ble_conn_aes_key.hex() == "82a36edee5d1ea51402a4953773f3448"


def test_derive_legacy_session_key_shape_and_determinism():
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(b"\xde\xad\xbe\xef")

    # 32 hex chars, lowercase (matches MD5.md5Encode in the APK)
    assert len(random_md5_hex) == 32
    assert random_md5_hex == random_md5_hex.lower()

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
