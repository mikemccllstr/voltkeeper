# ABOUTME: Unit tests for bluetooth cipher — AES-128-CBC with chained IV, zero-padding, no PKCS.

import hashlib

from voltkeeper.bluetooth.cipher import CbcSession, decrypt, derive_iv, encrypt

_KEY = bytes.fromhex("459FC535808941F17091E0993EE3E93D")


def test_roundtrip_aligned():
    iv = hashlib.md5(b"test").digest()
    for size in (16, 32, 64, 256):
        plaintext = b"\xaa" * size
        assert decrypt(encrypt(plaintext, _KEY, iv), _KEY, iv) == plaintext


def test_padding_is_zero_extension_not_strip():
    """decrypt returns the full block-aligned plaintext including pad bytes.

    Trailing-null preservation is required: Modbus frames whose CRC high byte
    is 0x00 (~0.4% of frames) and ECDSA signature/checksum bytes that end in
    0x00 must not be silently stripped.
    """
    iv = hashlib.md5(b"test").digest()

    # Unaligned plaintext: padded to next 16-byte boundary with zeros.
    pt = b"hi"
    ct = encrypt(pt, _KEY, iv)
    assert len(ct) == 16
    assert decrypt(ct, _KEY, iv) == pt + b"\x00" * 14

    # Plaintext that legitimately ends in 0x00 — the trailing null must
    # survive the round trip. This is the regression case for the
    # `rstrip(b"\x00")` bug.
    aligned_with_null = b"\x01\x03\x02\x12\x34\x00" + b"\x00" * 10  # 16 bytes
    assert decrypt(encrypt(aligned_with_null, _KEY, iv), _KEY, iv) == aligned_with_null


def test_derive_iv():
    result = derive_iv("abc")
    expected = hashlib.md5(b"abc").digest()
    assert result == expected


def test_chained_iv():
    initial_iv = hashlib.md5(b"start").digest()
    session = CbcSession(_KEY, initial_iv)

    m1 = b"first message 42"
    m2 = b"second messageXX"
    m3 = b"third message!!!"

    e1 = session.encrypt(m1)
    e2 = session.encrypt(m2)
    e3 = session.encrypt(m3)

    # Decrypt in order — must recover originals
    session2 = CbcSession(_KEY, initial_iv)
    assert session2.decrypt(e1) == m1
    assert session2.decrypt(e2) == m2
    assert session2.decrypt(e3) == m3

    # Re-decrypting the first message should NOT round-trip (IV state advanced)
    session3 = CbcSession(_KEY, initial_iv)
    session3.decrypt(e1)  # advance IV
    session3.decrypt(e2)  # advance IV
    session3.decrypt(e3)  # advance IV
    assert session3.decrypt(e1) != m1
