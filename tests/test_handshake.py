# ABOUTME: Unit tests for BLE encryption handshake — legacy and ECDH paths per FINDINGS §15.2/§15.8.

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from voltkeeper.bluetooth.handshake import (
    PRIVATE_KEY_L1_HEX,
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


def test_derive_shared_key_returns_32_bytes():
    priv_a = ec.generate_private_key(ec.SECP256R1())
    priv_b = ec.generate_private_key(ec.SECP256R1())
    shared = derive_shared_key(priv_a, priv_b.public_key())
    assert len(shared) == 32


def test_ecdh_determinism():
    # Generate two fixed ephemeral keypairs
    priv_a = ec.generate_private_key(ec.SECP256R1())
    priv_b = ec.generate_private_key(ec.SECP256R1())

    pub_a = priv_a.public_key()
    pub_b = priv_b.public_key()

    shared_ab = derive_shared_key(priv_a, pub_b)
    shared_ba = derive_shared_key(priv_b, pub_a)

    assert shared_ab == shared_ba
    assert len(shared_ab) == 32


# Task 3.1: ECDSA signature message uses hex-decoded randomMd5 (80 bytes)
def test_verify_device_pubkey_uses_hex_decoded_message(monkeypatch):
    """verify_device_pubkey accepts hex-decoded (80B) message; uses K2 for verification.

    We can't sign with the real device's L1 (not available), so we patch K2 to a
    test keypair we control, mirroring exactly how the device and app interact.
    """
    from cryptography.hazmat.primitives.serialization import PublicFormat

    import voltkeeper.bluetooth.handshake as hs_module

    random_md5_hex = "a0ce9adc2c5341f1d271d0518c4e7773"

    # Use a valid EC point as the "device" pubkey
    fake_device_key = ec.generate_private_key(ec.SECP256R1())
    fake_pub_raw = fake_device_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)[1:]

    # Create a test "K2" keypair we control
    test_device_priv = ec.generate_private_key(ec.SECP256R1())
    test_k2_der = test_device_priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()

    # Sign with hex-decoded message (correct APK behaviour: pubkey || hex_decode(md5), 80 bytes)
    der = test_device_priv.sign(fake_pub_raw + bytes.fromhex(random_md5_hex), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    sig_rs = r.to_bytes(32, "big") + s.to_bytes(32, "big")

    monkeypatch.setattr(hs_module, "PUBLIC_KEY_K2_DER_HEX", test_k2_der)
    result = verify_device_pubkey(fake_pub_raw, sig_rs, random_md5_hex)
    assert isinstance(result, ec.EllipticCurvePublicKey)


def test_verify_device_pubkey_rejects_ascii_message(monkeypatch):
    """A signature over the ASCII hex string (96B) does not verify when K2 expects hex-decoded."""
    from cryptography.hazmat.primitives.serialization import PublicFormat

    import voltkeeper.bluetooth.handshake as hs_module

    random_md5_hex = "a0ce9adc2c5341f1d271d0518c4e7773"

    fake_device_key = ec.generate_private_key(ec.SECP256R1())
    fake_pub_raw = fake_device_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)[1:]

    test_device_priv = ec.generate_private_key(ec.SECP256R1())
    test_k2_der = test_device_priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()

    # Sign with ASCII message (wrong — will not verify against hex-decoded expectation)
    der = test_device_priv.sign(fake_pub_raw + random_md5_hex.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    sig_rs_ascii = r.to_bytes(32, "big") + s.to_bytes(32, "big")

    monkeypatch.setattr(hs_module, "PUBLIC_KEY_K2_DER_HEX", test_k2_der)
    with pytest.raises(ValueError, match="device pubkey signature"):
        verify_device_pubkey(fake_pub_raw, sig_rs_ascii, random_md5_hex)


def test_sign_app_pubkey_uses_hex_decoded_message():
    """sign_app_pubkey signs over hex-decoded randomMd5 (not ASCII), verifiable with L1's pubkey."""
    random_md5_hex = "a0ce9adc2c5341f1d271d0518c4e7773"
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    priv = ec.generate_private_key(ec.SECP256R1())
    pub_raw = priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)[1:]

    sig_rs = sign_app_pubkey(pub_raw, random_md5_hex)
    r = int.from_bytes(sig_rs[:32], "big")
    s = int.from_bytes(sig_rs[32:], "big")
    der_sig = encode_dss_signature(r, s)

    # Verify with L1's own public key (L1 priv signs → L1 pub verifies)
    l1_pub = ec.derive_private_key(int(PRIVATE_KEY_L1_HEX, 16), ec.SECP256R1()).public_key()
    # Must not raise — L1 signed with hex-decoded message, L1_pub verifies same
    l1_pub.verify(der_sig, pub_raw + bytes.fromhex(random_md5_hex), ec.ECDSA(hashes.SHA256()))
