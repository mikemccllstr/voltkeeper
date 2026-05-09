# ABOUTME: AES-128-CBC cipher with chained IV and zero-padding (no PKCS) for Bluetti BLE encryption.
# ABOUTME: Unit 5 per IMPLEMENTATION_UNITS.md.

import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def derive_iv(random_md5_hex: str) -> bytes:
    return hashlib.md5(random_md5_hex.encode("ascii")).digest()


def _zero_pad(data: bytes, block: int = 16) -> bytes:
    if len(data) % block == 0:
        return data
    return data + b"\x00" * (block - len(data) % block)


def _zero_unpad(data: bytes) -> bytes:
    return data.rstrip(b"\x00")


def encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
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
    return _zero_unpad(dec.update(ciphertext) + dec.finalize())


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
