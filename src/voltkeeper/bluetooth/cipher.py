# ABOUTME: AES-CBC cipher with chained IV and zero-padding (no PKCS) for Bluetti BLE encryption.
# Framing note: encrypt() zero-pads to a 16-byte boundary. decrypt() returns
# the full block-aligned plaintext including any padding bytes — it does NOT
# strip trailing zeros, because the Bluetti protocol carries plaintext bytes
# that legitimately end in 0x00 (Modbus register values < 256, CRC high
# bytes, ECDSA signature/checksum bytes, etc.). The upper layer (Modbus
# parser, handshake state machine) determines actual payload length from
# protocol-level fields and ignores trailing pad bytes.

import hashlib
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def derive_iv(random_md5_hex: str) -> bytes:
    """The legacy-stage CBC IV is the 16-byte decoded randomMd5 digest.

    Per ConnectManager.bleEncryptedHandle, which passes hexStringToBytes(randomMd5) as the
    IV — NOT a second MD5 of the hex string.
    """
    return bytes.fromhex(random_md5_hex)


def _zero_pad(data: bytes, block: int = 16) -> bytes:
    if len(data) % block == 0:
        return data
    return data + b"\x00" * (block - len(data) % block)


def encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(key) not in (16, 32):
        raise ValueError("AES key must be 16 or 32 bytes")
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    padded = _zero_pad(plaintext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(ciphertext) % 16 != 0:
        raise ValueError("Ciphertext length must be a multiple of 16")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    return dec.update(ciphertext) + dec.finalize()


class CbcSession:
    def __init__(self, key: bytes, initial_iv: bytes):
        self._key = key
        self._iv = initial_iv

    def encrypt(self, plaintext: bytes) -> bytes:
        ct = encrypt(plaintext, self._key, self._iv)
        self._iv = ct[-16:]
        return ct

    def decrypt(self, ciphertext: bytes) -> bytes:
        pt = decrypt(ciphertext, self._key, self._iv)
        self._iv = ciphertext[-16:]
        return pt


def frame_decode(frame: bytes, session: CbcSession) -> bytes:
    """Decode a handshake-stage frame [2B BE len][ciphertext] -> plaintext trimmed to len bytes."""
    if len(frame) < 2:
        raise ValueError("frame too short for length prefix")
    plaintext_len = int.from_bytes(frame[:2], "big")
    ciphertext_len = (plaintext_len + 15) // 16 * 16
    if len(frame) < 2 + ciphertext_len:
        raise ValueError(f"frame too short: need {2 + ciphertext_len}, got {len(frame)}")
    return session.decrypt(frame[2 : 2 + ciphertext_len])[:plaintext_len]


def frame_encode(plaintext: bytes, session: CbcSession) -> bytes:
    """Encode a handshake-stage frame: plaintext -> [2B BE len][ciphertext]."""
    return len(plaintext).to_bytes(2, "big") + session.encrypt(plaintext)


class ShareSession:
    """Post-handshake codec: [2B len][4B seed][ciphertext], IV = MD5(seed) per frame."""

    def __init__(self, key: bytes):
        if len(key) not in (16, 32):
            raise ValueError("AES key must be 16 or 32 bytes")
        self._key = key

    def encode_frame(self, plaintext: bytes, seed: bytes | None = None) -> bytes:
        """Encode a post-handshake frame: [2B len][4B seed][ciphertext], IV = MD5(seed)."""
        if seed is None:
            seed = os.urandom(4)
        if len(seed) != 4:
            raise ValueError("seed must be 4 bytes")
        iv = hashlib.md5(seed).digest()
        ciphertext = encrypt(plaintext, self._key, iv)
        return len(plaintext).to_bytes(2, "big") + seed + ciphertext

    def decode_frame(self, frame: bytes) -> bytes:
        """Decode a post-handshake frame: [2B len][4B seed][ciphertext] -> trimmed plaintext."""
        if len(frame) < 6:
            raise ValueError("frame too short for post-handshake header (need 6 bytes)")
        plaintext_len = int.from_bytes(frame[:2], "big")
        seed = frame[2:6]
        iv = hashlib.md5(seed).digest()
        ciphertext_len = (plaintext_len + 15) // 16 * 16
        if len(frame) < 6 + ciphertext_len:
            raise ValueError(f"frame too short: need {6 + ciphertext_len}, got {len(frame)}")
        return decrypt(frame[6 : 6 + ciphertext_len], self._key, iv)[:plaintext_len]
