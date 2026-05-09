# ABOUTME: BLE encryption handshake — legacy + ECDH paths per FINDINGS §15.2 step 3 and §15.8.
# ABOUTME: Unit 6 (pure helpers) and Unit 7b (state machine) per IMPLEMENTATION_UNITS.md.

import asyncio
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_public_key

from .cipher import CbcSession, derive_iv

LOCAL_AES_KEY = bytes.fromhex("459FC535808941F17091E0993EE3E93D")
PRIVATE_KEY_L1_HEX = "4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337"
PUBLIC_KEY_K2_DER_HEX = (
    "3059301306072a8648ce3d020106082a8648ce3d030107"
    "03420004A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251"
    "EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594"
)


def derive_legacy_session_key(random_bytes: bytes) -> tuple[str, bytes]:
    reversed_bytes = random_bytes[::-1]
    digest = hashlib.md5(reversed_bytes).hexdigest().upper()
    digest_ascii = digest.encode("ascii")
    extended_local = (LOCAL_AES_KEY * 2)[: len(digest_ascii)]
    aes_key_bytes = bytes(a ^ b for a, b in zip(digest_ascii, extended_local))
    return digest, aes_key_bytes[:16]


def verify_device_pubkey(device_pub_raw: bytes, signature_rs: bytes, random_md5_hex: str) -> ec.EllipticCurvePublicKey:
    k2 = load_der_public_key(bytes.fromhex(PUBLIC_KEY_K2_DER_HEX))
    if not isinstance(k2, ec.EllipticCurvePublicKey):
        raise ValueError("PUBLIC_KEY_K2_DER_HEX is not an EC public key")
    r = int.from_bytes(signature_rs[:32], "big")
    s = int.from_bytes(signature_rs[32:], "big")
    der_sig = encode_dss_signature(r, s)
    message = device_pub_raw + random_md5_hex.encode("ascii")
    try:
        k2.verify(der_sig, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as e:
        raise ValueError("device pubkey signature does not verify against K2") from e
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + device_pub_raw)


def sign_app_pubkey(app_pub_raw: bytes, random_md5_hex: str) -> bytes:
    private_value = int(PRIVATE_KEY_L1_HEX, 16)
    priv = ec.derive_private_key(private_value, ec.SECP256R1())
    der = priv.sign(app_pub_raw + random_md5_hex.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def derive_shared_key(app_priv: ec.EllipticCurvePrivateKey, device_pub: ec.EllipticCurvePublicKey) -> bytes:
    shared = app_priv.exchange(ec.ECDH(), device_pub)
    return shared[:16]


def _checksum(data: bytes) -> bytes:
    return (sum(data) & 0xFFFF).to_bytes(2, "little")


class HandshakeSession:
    def __init__(self):
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _notify_handler(self, _sender: int, data: bytearray):
        self._queue.put_nowait(bytes(data))

    async def _next_notification(self, timeout: float = 5.0) -> bytes:
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def _collect(self, expected_size: int, timeout: float = 5.0) -> bytes:
        buf = bytearray()
        while len(buf) < expected_size:
            buf.extend(await self._next_notification(timeout=timeout))
        return bytes(buf)

    async def _send(self, client, data: bytes) -> None:
        from . import WRITE_UUID

        await client.write_gatt_char(WRITE_UUID, data, response=False)

    async def run(self, client) -> CbcSession:
        from . import NOTIFY_UUID

        await client.start_notify(NOTIFY_UUID, self._notify_handler)

        try:
            # Path 1 — legacy challenge-response
            challenge = await self._collect(7)
            if challenge[:3] != b"\x2a\x2a\x01":
                raise ValueError(f"Expected challenge 0x2A2A01, got {challenge[:3].hex()}")
            random_bytes = challenge[3:7]

            random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)

            reply = b"\x2a\x2a\x02\x04" + random_md5_hex[16:24].encode("ascii")
            reply += _checksum(reply)
            await self._send(client, reply)

            # Path 2 — ECDH key exchange
            initial_iv = derive_iv(random_md5_hex)
            enc_session = CbcSession(ble_conn_aes_key, initial_iv)

            encrypted = await self._collect(144)
            plaintext = enc_session.decrypt(encrypted)

            if plaintext[:3] != b"\x2a\x2a\x04":
                raise ValueError(f"Expected ECDH start 0x2A2A04, got {plaintext[:3].hex()}")

            device_pub_raw = plaintext[3:67]
            signature_rs = plaintext[67:131]

            device_pub = verify_device_pubkey(device_pub_raw, signature_rs, random_md5_hex)

            app_priv = ec.generate_private_key(ec.SECP256R1())
            app_pub = app_priv.public_key()
            app_pub_raw = app_pub.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)[1:]

            app_sig = sign_app_pubkey(app_pub_raw, random_md5_hex)

            ecdh_reply = b"\x2a\x2a\x05\x80" + app_pub_raw + app_sig
            ecdh_reply += _checksum(ecdh_reply)
            enc_reply = enc_session.encrypt(ecdh_reply)
            await self._send(client, enc_reply)

            # Path 2 confirmation
            conf_encrypted = await self._collect(16)
            conf_plaintext = enc_session.decrypt(conf_encrypted)
            if conf_plaintext[:3] != b"\x2a\x2a\x06":
                raise ValueError(f"Expected confirmation 0x2A2A06, got {conf_plaintext[:3].hex()}")

            shared_key = derive_shared_key(app_priv, device_pub)
            return CbcSession(shared_key, initial_iv)
        finally:
            await client.stop_notify(NOTIFY_UUID)
