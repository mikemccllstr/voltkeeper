# ABOUTME: Known-answer tests for the V2 legacy challenge-response framing, derived from the
# ABOUTME: decompiled APK and a captured Elite 100 V2 BLE trace (challenge 2A2A0104 3D9687E0 023F).

from voltkeeper.bluetooth.cipher import derive_iv
from voltkeeper.bluetooth.handshake import (
    build_legacy_reply,
    derive_legacy_session_key,
    parse_legacy_challenge,
)

# Captured from a real Elite 100 V2 (DC:B4:D9:46:73:96) handshake notification.
HW_CHALLENGE = bytes.fromhex("2A2A01043D9687E0023F")
HW_RANDOM = bytes.fromhex("3D9687E0")
HW_RANDOM_MD5 = "a0ce9adc2c5341f1d271d0518c4e7773"
HW_REPLY = bytes.fromhex("2A2A0204D271D051026A")


def test_parse_legacy_challenge_reads_random_after_length_field():
    """Random is challenge[4:8] — the 0x04 length byte at offset 3 is skipped."""
    assert parse_legacy_challenge(HW_CHALLENGE) == HW_RANDOM


def test_build_legacy_reply_matches_hardware_vector():
    """The reply is the symmetric 10-byte frame the device accepts."""
    random_md5_hex, _ = derive_legacy_session_key(HW_RANDOM)
    assert random_md5_hex == HW_RANDOM_MD5
    assert build_legacy_reply(random_md5_hex) == HW_REPLY


def test_legacy_reply_is_ten_bytes_with_decoded_token():
    """Token is the 4 hex-decoded bytes of randomMd5[16:24], not 8 ASCII bytes."""
    reply = build_legacy_reply(HW_RANDOM_MD5)
    assert len(reply) == 10
    assert reply[:4] == bytes.fromhex("2A2A0204")
    assert reply[4:8] == bytes.fromhex(HW_RANDOM_MD5[16:24])  # d2 71 d0 51


def test_legacy_reply_checksum_is_big_endian_sum_over_body():
    """Checksum = big-endian 2-byte sum of (02 04 + token), excluding the 2A 2A header."""
    reply = build_legacy_reply(HW_RANDOM_MD5)
    body = reply[2:8]  # 02 04 d2 71 d0 51
    assert reply[8:10] == (sum(body) & 0xFFFF).to_bytes(2, "big")
    assert reply[8:10] == bytes.fromhex("026A")


def test_legacy_session_key_is_bytewise_xor_of_decoded_values():
    """bleConnAESKey = decode(randomMd5) XOR decode(LOCAL_AES_KEY), 16 bytes."""
    _, key = derive_legacy_session_key(HW_RANDOM)
    assert key == bytes.fromhex("e5515fe9acda0000a2e030c8b2ad9e4e")
    assert len(key) == 16


def test_derive_iv_is_decoded_digest():
    """IV = hex-decoded randomMd5 (the raw digest), not a second MD5 of the hex string."""
    assert derive_iv(HW_RANDOM_MD5) == bytes.fromhex(HW_RANDOM_MD5)
    assert len(derive_iv(HW_RANDOM_MD5)) == 16
