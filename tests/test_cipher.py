# ABOUTME: Unit tests for bluetooth cipher — AES-128-CBC with chained IV, zero-padding, no PKCS.
# ABOUTME: Unit 5 per IMPLEMENTATION_UNITS.md.

import hashlib

from src.bluetti_cli.bluetooth.cipher import CbcSession, decrypt, derive_iv, encrypt


def test_roundtrip():
    key = bytes.fromhex("459FC535808941F17091E0993EE3E93D")
    iv = hashlib.md5(b"test").digest()
    for size in (1, 15, 16, 17, 100):
        plaintext = b"A" * size
        ct = encrypt(plaintext, key, iv)
        pt = decrypt(ct, key, iv)
        assert pt == plaintext


def test_derive_iv():
    result = derive_iv("abc")
    expected = hashlib.md5(b"abc").digest()
    assert result == expected


def test_chained_iv():
    key = bytes.fromhex("459FC535808941F17091E0993EE3E93D")
    initial_iv = hashlib.md5(b"start").digest()
    session = CbcSession(key, initial_iv)

    m1 = b"first message 42"
    m2 = b"second messageXX"
    m3 = b"third messages!"

    e1 = session.encrypt(m1)
    e2 = session.encrypt(m2)
    e3 = session.encrypt(m3)

    # Decrypt in order — must recover originals
    session2 = CbcSession(key, initial_iv)
    assert session2.decrypt(e1) == m1
    assert session2.decrypt(e2) == m2
    assert session2.decrypt(e3) == m3

    # Re-decrypting the first message should NOT round-trip (IV state advanced)
    session3 = CbcSession(key, initial_iv)
    session3.decrypt(e1)  # advance IV
    session3.decrypt(e2)  # advance IV
    session3.decrypt(e3)  # advance IV
    assert session3.decrypt(e1) != m1
