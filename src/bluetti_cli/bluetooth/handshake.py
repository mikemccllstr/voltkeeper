# ABOUTME: BLE encryption handshake — legacy + ECDH paths per FINDINGS §15.2 step 3 and §15.8.
# ABOUTME: Unit 6 per IMPLEMENTATION_UNITS.md.

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key

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


class HandshakeSession:
    def __init__(self):
        pass

    async def run(self, client):
        raise NotImplementedError("HandshakeSession.run is wired in Unit 7")
