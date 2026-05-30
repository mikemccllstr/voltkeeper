# ABOUTME: Unit tests for BLE encryption handshake state machine — mock-driven BLE I/O.

import asyncio

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from voltkeeper.bluetooth.cipher import CbcSession, ShareSession, frame_decode, frame_encode
from voltkeeper.bluetooth.handshake import (
    PRIVATE_KEY_L1_HEX,
    HandshakeSession,
    _checksum,
    _frame,
    build_legacy_reply,
    derive_iv,
    derive_legacy_session_key,
    derive_shared_key,
    sign_app_pubkey,
)

# The simulator signs device ECDH messages with L1 (sign_app_pubkey). To allow
# verify_device_pubkey to verify those signatures without a mock, we patch K2 to
# be L1's public key for all tests in this file.
_L1_PUB_DER = (
    ec.derive_private_key(int(PRIVATE_KEY_L1_HEX, 16), ec.SECP256R1())
    .public_key()
    .public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    .hex()
)


@pytest.fixture(autouse=True)
def patch_k2_to_l1_pub(monkeypatch):
    import voltkeeper.bluetooth.handshake as hs_module

    monkeypatch.setattr(hs_module, "PUBLIC_KEY_K2_DER_HEX", _L1_PUB_DER)


class FakeClient:
    def __init__(self, notify_callback=None):
        self._notify_callback = notify_callback
        self.sent: list[bytes] = []
        self._notify_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._is_notifying = False

    async def start_notify(self, _uuid, callback):
        self._notify_callback = callback
        self._is_notifying = True

    async def stop_notify(self, _uuid):
        self._is_notifying = False

    async def write_gatt_char(self, _uuid, data, response=False):
        self.sent.append(data)

    def feed(self, data: bytes):
        if self._notify_callback:
            self._notify_callback(0, bytearray(data))


async def build_device_side_handshake(client, app_client) -> ShareSession:
    random_bytes = b"\x01\x02\x03\x04"
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)

    # Wait until the handshake task has called start_notify
    while client._notify_callback is None:
        await asyncio.sleep(0)

    # Path 1: device sends challenge (10-byte frame: 2A 2A 01 04 <random> <checksum>)
    client.feed(_frame(0x01, 0x04, random_bytes))

    # Device receives reply
    reply = await _await_send(app_client)
    assert reply == build_legacy_reply(random_md5_hex)

    # Device sends status-ack frame (2A 2A 03 01 00) before the ECDH block
    client.feed(_frame(0x03, 0x01, b"\x00"))

    # Path 2: device sends ECDH payload — with length prefix and hex-decoded signature message
    # Each handshake-stage frame uses a fresh session with the same IV (no cross-frame chaining).
    initial_iv = derive_iv(random_md5_hex)

    device_priv = ec.generate_private_key(ec.SECP256R1())
    device_pub = device_priv.public_key()
    device_pub_raw = device_pub.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)[1:]
    device_sig = sign_app_pubkey(device_pub_raw, random_md5_hex)

    # Task 6.1: prepend the %04X length prefix on the encrypted ECDH frame
    client.feed(frame_encode(_frame(0x04, 0x80, device_pub_raw + device_sig), CbcSession(ble_conn_aes_key, initial_iv)))

    # Device receives app ECDH reply (also length-prefixed, fresh session for decode)
    enc_reply = await _await_send(app_client)
    plaintext = frame_decode(enc_reply, CbcSession(ble_conn_aes_key, initial_iv))
    shared = derive_shared_key(
        device_priv,
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + plaintext[4:68]),
    )

    # Device sends confirmation (length-prefixed, fresh session)
    client.feed(frame_encode(_frame(0x06, 0x01, b"\x00"), CbcSession(ble_conn_aes_key, initial_iv)))

    return ShareSession(shared)


async def _await_send(client, timeout: float = 2.0):
    start = len(client.sent)
    deadline = asyncio.get_event_loop().time() + timeout
    while len(client.sent) <= start:
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError("Did not receive expected write")
        await asyncio.sleep(0.01)
    return client.sent[start]


class TestHandshakeStateMachine:
    @pytest.mark.asyncio
    async def test_full_handshake_against_device_simulator(self):
        # Task 6.2: drop the verify_device_pubkey mock — real signature verifies now
        app_client = FakeClient()
        h = HandshakeSession()

        async with asyncio.timeout(5):
            session, dev_session = await asyncio.wait_for(
                asyncio.gather(
                    h.run(app_client),
                    build_device_side_handshake(app_client, app_client),
                ),
                timeout=5,
            )

        assert isinstance(session, ShareSession)

        # Task 6.3: post-handshake round-trip using [len][seed][ciphertext] layout
        test_msg = b"hello modbus test"
        enc = session.encode_frame(test_msg)
        dec = dev_session.decode_frame(enc)
        assert dec == test_msg

    @pytest.mark.asyncio
    async def test_rejects_invalid_device_signature(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"
        random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)

        initial_iv = derive_iv(random_md5_hex)

        fake_device_key = ec.generate_private_key(ec.SECP256R1())
        fake_pub_raw = fake_device_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)[1:]
        bad_sig = b"\x00" * 64

        enc_ecdh = frame_encode(_frame(0x04, 0x80, fake_pub_raw + bad_sig), CbcSession(ble_conn_aes_key, initial_iv))

        # Start handshake, wait for start_notify, then feed data
        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)
        client.feed(_frame(0x01, 0x04, random_bytes))
        # Ack consumed by handshake, then ECDH block arrives
        client.feed(_frame(0x03, 0x01, b"\x00"))
        client.feed(enc_ecdh)

        with pytest.raises(ValueError, match="device pubkey signature"):
            await task

    @pytest.mark.asyncio
    async def test_rejects_bad_challenge_header(self):
        client = FakeClient()
        h = HandshakeSession()

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)
        # Wrong header: 2A 2A 99 instead of 2A 2A 01
        client.feed(b"\x2a\x2a\x99\x01\x02\x03\x04")

        with pytest.raises(ValueError, match="Expected challenge 0x2A2A01"):
            await task

    @pytest.mark.asyncio
    async def test_rejects_bad_ecdh_header(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"
        random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)
        initial_iv = derive_iv(random_md5_hex)

        # Build an ECDH frame with WRONG header (2A 2A 99 instead of 2A 2A 04)
        bad_ecdh = b"\x2a\x2a\x99" + b"\x00" * (128 - 3)
        enc_bad = frame_encode(bad_ecdh, CbcSession(ble_conn_aes_key, initial_iv))

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)

        client.feed(_frame(0x01, 0x04, random_bytes))
        # Ack consumed by handshake, then bad ECDH block arrives
        client.feed(_frame(0x03, 0x01, b"\x00"))
        client.feed(enc_bad)

        with pytest.raises(ValueError, match="Expected ECDH start 0x2A2A04"):
            await task

    @pytest.mark.asyncio
    async def test_rejects_bad_confirmation_header(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"
        random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)
        initial_iv = derive_iv(random_md5_hex)

        device_priv = ec.generate_private_key(ec.SECP256R1())
        device_pub_raw = device_priv.public_key().public_bytes(
            encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
        )[1:]
        device_sig = sign_app_pubkey(device_pub_raw, random_md5_hex)
        enc_ecdh = frame_encode(
            _frame(0x04, 0x80, device_pub_raw + device_sig), CbcSession(ble_conn_aes_key, initial_iv)
        )

        # Build a confirmation with WRONG header (2A 2A 99 instead of 2A 2A 06)
        bad_conf = b"\x2a\x2a\x99\x00" + b"\x00" * 10
        bad_conf += _checksum(bad_conf)

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)

        # Feed challenge → capture legacy reply.
        client.feed(_frame(0x01, 0x04, random_bytes))
        legacy_reply = await _await_send(client)
        assert legacy_reply[:3] == b"\x2a\x2a\x02"

        # Ack consumed by handshake, then ECDH block arrives
        client.feed(_frame(0x03, 0x01, b"\x00"))

        # Feed encrypted ECDH frame → capture app's ECDH reply
        # Each handshake frame uses its own fresh session — no need to track IV state
        client.feed(enc_ecdh)
        await _await_send(client)  # wait for app's 05 reply

        # Encrypt and feed the bad confirmation (length-prefixed, fresh session)
        client.feed(frame_encode(bad_conf, CbcSession(ble_conn_aes_key, initial_iv)))

        with pytest.raises(ValueError, match="Expected confirmation 0x2A2A06"):
            await task

    @pytest.mark.asyncio
    async def test_rejects_ecdh_confirmation_with_nonzero_status(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"
        random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)
        initial_iv = derive_iv(random_md5_hex)

        device_priv = ec.generate_private_key(ec.SECP256R1())
        device_pub_raw = device_priv.public_key().public_bytes(
            encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
        )[1:]
        device_sig = sign_app_pubkey(device_pub_raw, random_md5_hex)
        enc_ecdh = frame_encode(
            _frame(0x04, 0x80, device_pub_raw + device_sig), CbcSession(ble_conn_aes_key, initial_iv)
        )

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)

        client.feed(_frame(0x01, 0x04, random_bytes))
        await _await_send(client)
        client.feed(_frame(0x03, 0x01, b"\x00"))
        client.feed(enc_ecdh)
        await _await_send(client)

        # Device sends 0x06 with status=1 (rejected)
        client.feed(frame_encode(_frame(0x06, 0x01, b"\x01"), CbcSession(ble_conn_aes_key, initial_iv)))

        with pytest.raises(ValueError, match="ECDH confirmation failed"):
            await task

    @pytest.mark.asyncio
    async def test_ack_non_zero_status_aborts(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)

        # Send challenge
        client.feed(_frame(0x01, 0x04, random_bytes))

        # Wait for legacy reply
        reply = await _await_send(client)
        assert reply[:3] == b"\x2a\x2a\x02"

        # Send ack with non-zero status
        client.feed(_frame(0x03, 0x01, b"\x01"))

        with pytest.raises(ValueError, match="device rejected handshake"):
            await task
