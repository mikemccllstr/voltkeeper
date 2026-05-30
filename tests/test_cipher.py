# ABOUTME: Unit tests for bluetooth cipher — AES-CBC with chained IV, zero-padding, no PKCS.

import hashlib

import pytest

from voltkeeper.bluetooth.cipher import (
    CbcSession,
    ShareSession,
    decrypt,
    derive_iv,
    encrypt,
    frame_decode,
    frame_encode,
)

_KEY = bytes.fromhex("459FC535808941F17091E0993EE3E93D")
_KEY_32 = bytes(range(32))


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
    # IV is the decoded randomMd5 digest (16 bytes), not a second MD5 of the hex string.
    random_md5_hex = "a0ce9adc2c5341f1d271d0518c4e7773"
    assert derive_iv(random_md5_hex) == bytes.fromhex(random_md5_hex)


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


# Task 1.1: length-prefix codec round-trip
def test_frame_encode_decode_roundtrip():
    """frame_encode/decode: 2-byte length prefix prepended; decode trims to plaintext_len."""
    iv = bytes.fromhex("a0ce9adc2c5341f1d271d0518c4e7773")
    enc = CbcSession(_KEY, iv)
    dec = CbcSession(_KEY, iv)

    # 17 bytes: pads to 32-byte ciphertext; prefix must record the real length
    pt = b"\x2a\x2a\x04" + b"\xab" * 14
    encoded = frame_encode(pt, enc)
    assert int.from_bytes(encoded[:2], "big") == len(pt)
    decoded = frame_decode(encoded, dec)
    assert decoded == pt  # exactly 17 bytes, no trailing padding


def test_frame_encode_decode_aligned():
    """Works when plaintext is already block-aligned (no padding discarded)."""
    iv = hashlib.md5(b"test").digest()
    enc = CbcSession(_KEY, iv)
    dec = CbcSession(_KEY, iv)
    pt = b"\xcc" * 32
    assert frame_decode(frame_encode(pt, enc), dec) == pt


# Task 1.2: synthetic 146-byte ECDH block (hardware-format test vector)
def test_frame_decode_ecdh_block():
    """Synthetic 146-byte frame [00 86 | 144-byte ciphertext] decodes to 134 bytes, starts 2A2A04."""
    from voltkeeper.bluetooth.handshake import derive_legacy_session_key

    hw_random = bytes.fromhex("3D9687E0")
    hw_random_md5 = "a0ce9adc2c5341f1d271d0518c4e7773"
    _, hw_key = derive_legacy_session_key(hw_random)
    hw_iv = derive_iv(hw_random_md5)

    # 134-byte ECDH plaintext: 2A2A0480 + 64B pubkey + 64B sig + 2B checksum
    pt = b"\x2a\x2a\x04\x80" + b"\xaa" * 64 + b"\xbb" * 64 + b"\x3e\x3e"
    assert len(pt) == 134

    # Build the "captured" 146-byte frame
    enc = CbcSession(hw_key, hw_iv)
    frame = len(pt).to_bytes(2, "big") + enc.encrypt(pt)
    assert frame[:2] == bytes.fromhex("0086")  # 134 == 0x86
    assert len(frame) == 146

    dec = CbcSession(hw_key, hw_iv)
    decoded = frame_decode(frame, dec)
    assert len(decoded) == 134
    assert decoded[:4] == b"\x2a\x2a\x04\x80"
    assert decoded == pt


# Task 4.1: post-handshake per-frame IV codec round-trip
def test_share_session_encode_decode_roundtrip():
    """[len][4B seed][ciphertext], IV = MD5(seed): round-trip with injected seed."""
    session = ShareSession(_KEY)
    seed = bytes.fromhex("cafebabe")

    pt = b"\x01\x03\x02\x12\x34\x56\x78\x9a"  # 8 bytes, not 16-aligned
    encoded = session.encode_frame(pt, seed=seed)
    assert encoded[:2] == (8).to_bytes(2, "big")
    assert encoded[2:6] == seed
    assert len(encoded) == 2 + 4 + 16  # 6-byte header + one block

    decoded = session.decode_frame(encoded)
    assert decoded == pt


def test_share_session_random_seed_roundtrip():
    """encode_frame with no seed argument uses os.urandom; decode recovers plaintext."""
    session = ShareSession(_KEY)
    pt = b"hello from modbus" + b"\x00\x01\x02"
    encoded = session.encode_frame(pt)
    assert len(encoded) == 2 + 4 + 32  # pads to 32-byte ciphertext block
    assert session.decode_frame(encoded) == pt


def test_share_session_fresh_iv_per_frame():
    """Each frame uses an independent IV — frames do NOT chain state."""
    session = ShareSession(_KEY)
    seed = b"\x00\x00\x00\x01"
    pt = b"\xff" * 16

    f1 = session.encode_frame(pt, seed=seed)
    f2 = session.encode_frame(pt, seed=seed)
    # Same seed → same ciphertext (IV is deterministic from seed, no chaining)
    assert f1 == f2


def test_share_session_32byte_key_encode_decode_roundtrip():
    """ShareSession accepts a 32-byte key and round-trips correctly (AES-256-CBC)."""
    session = ShareSession(_KEY_32)
    seed = bytes.fromhex("cafebabe")
    pt = b"\x01\x03\x02\x12\x34\x56\x78\x9a"
    encoded = session.encode_frame(pt, seed=seed)
    assert session.decode_frame(encoded) == pt


def test_share_session_32byte_key_random_seed_roundtrip():
    """32-byte key with random seed: encode then decode recovers plaintext."""
    session = ShareSession(_KEY_32)
    pt = b"hello from modbus with aes256" + b"\x00\x01"
    encoded = session.encode_frame(pt)
    assert session.decode_frame(encoded) == pt


# Task 4.2: malformed post-handshake frame is rejected
def test_share_session_wrong_layout_raises():
    """decode_frame raises ValueError rather than silently mis-decrypting a truncated frame."""
    session = ShareSession(_KEY)
    # Claims 16-byte plaintext but only has 5 payload bytes after the 6-byte header
    bad_frame = (16).to_bytes(2, "big") + b"\x00" * 4 + b"\xff" * 5
    with pytest.raises(ValueError, match="frame too short"):
        session.decode_frame(bad_frame)
