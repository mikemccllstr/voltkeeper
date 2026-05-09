# ABOUTME: Unit tests for BLE encryption handshake state machine — mock-driven BLE I/O.
# ABOUTME: Unit 7b per IMPLEMENTATION_UNITS.md.

import asyncio
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.bluetti_cli.bluetooth.cipher import CbcSession
from src.bluetti_cli.bluetooth.handshake import (
    HandshakeSession,
    _checksum,
    derive_iv,
    derive_legacy_session_key,
    derive_shared_key,
    sign_app_pubkey,
)


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


async def build_device_side_handshake(client, app_client) -> CbcSession:
    random_bytes = b"\x01\x02\x03\x04"
    random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)

    # Wait until the handshake task has called start_notify
    while client._notify_callback is None:
        await asyncio.sleep(0)

    # Path 1: device sends challenge
    client.feed(b"\x2a\x2a\x01" + random_bytes)

    # Device receives reply
    reply = await _await_send(app_client)
    assert reply[:4] == b"\x2a\x2a\x02\x04"
    assert reply[4:12] == random_md5_hex[16:24].encode("ascii")

    # Path 2: device sends ECDH payload
    initial_iv = derive_iv(random_md5_hex)
    enc_session = CbcSession(ble_conn_aes_key, initial_iv)

    device_priv = ec.generate_private_key(ec.SECP256R1())
    device_pub = device_priv.public_key()
    device_pub_raw = device_pub.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)[1:]
    device_sig = sign_app_pubkey(device_pub_raw, random_md5_hex)

    ecdh_msg = b"\x2a\x2a\x04" + device_pub_raw + device_sig
    ecdh_msg += _checksum(ecdh_msg)
    enc_ecdh = enc_session.encrypt(ecdh_msg)
    client.feed(enc_ecdh)

    # Device receives ECDH reply
    enc_reply = await _await_send(app_client)
    plaintext = enc_session.decrypt(enc_reply)
    # ECDH reply header is \x2a\x2a\x05\x80 (4 bytes), then 64-byte pubkey
    shared = derive_shared_key(
        device_priv,
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + plaintext[4:68]),
    )

    # Device sends confirmation
    conf_msg = b"\x2a\x2a\x06\x00" + b"\x00" * 10
    conf_msg += _checksum(conf_msg)
    enc_conf = enc_session.encrypt(conf_msg)
    client.feed(enc_conf)

    return CbcSession(shared, initial_iv)


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
        app_client = FakeClient()
        h = HandshakeSession()

        async with asyncio.timeout(5):
            with patch("src.bluetti_cli.bluetooth.handshake.verify_device_pubkey") as mock_verify:
                # Return a real SECP256R1 pubkey from the device-side raw bytes
                def fake_verify(device_pub_raw, signature_rs, random_md5_hex):
                    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + device_pub_raw)

                mock_verify.side_effect = fake_verify

                session, dev_session = await asyncio.gather(
                    h.run(app_client),
                    build_device_side_handshake(app_client, app_client),
                )

        assert isinstance(session, CbcSession)

        # Verify both sides have same session key (decrypt returns padded data per Unit 5)
        test_msg = b"hello modbus test"
        enc = session.encrypt(test_msg)
        dec = dev_session.decrypt(enc)
        assert dec[: len(test_msg)] == test_msg

    @pytest.mark.asyncio
    async def test_rejects_invalid_device_signature(self):
        client = FakeClient()
        h = HandshakeSession()

        random_bytes = b"\x01\x02\x03\x04"
        random_md5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)

        initial_iv = derive_iv(random_md5_hex)
        enc_session = CbcSession(ble_conn_aes_key, initial_iv)

        fake_pub_raw = b"\x04" * 64
        bad_sig = b"\x00" * 64

        ecdh_msg = b"\x2a\x2a\x04" + fake_pub_raw + bad_sig
        ecdh_msg += _checksum(ecdh_msg)
        enc_ecdh = enc_session.encrypt(ecdh_msg)

        # Start handshake, wait for start_notify, then feed data
        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)
        client.feed(b"\x2a\x2a\x01" + random_bytes)
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
        enc_session = CbcSession(ble_conn_aes_key, initial_iv)

        # Build an ECDH frame with WRONG header (2A 2A 99 instead of 2A 2A 04),
        # padded to 144 bytes so _collect(144) returns.
        bad_ecdh = b"\x2a\x2a\x99" + b"\x00" * (144 - 3)
        enc_bad = enc_session.encrypt(bad_ecdh)

        task = asyncio.create_task(h.run(client))
        while client._notify_callback is None:
            await asyncio.sleep(0)

        client.feed(b"\x2a\x2a\x01" + random_bytes)
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
        enc_session = CbcSession(ble_conn_aes_key, initial_iv)

        device_priv = ec.generate_private_key(ec.SECP256R1())
        device_pub_raw = device_priv.public_key().public_bytes(
            encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
        )[1:]
        device_sig = sign_app_pubkey(device_pub_raw, random_md5_hex)
        ecdh_msg = b"\x2a\x2a\x04" + device_pub_raw + device_sig
        ecdh_msg += _checksum(ecdh_msg)
        enc_ecdh = enc_session.encrypt(ecdh_msg)

        # Build a confirmation with WRONG header (2A 2A 99 instead of 2A 2A 06)
        bad_conf = b"\x2a\x2a\x99\x00" + b"\x00" * 10
        bad_conf += _checksum(bad_conf)

        with patch("src.bluetti_cli.bluetooth.handshake.verify_device_pubkey") as mock_verify:
            mock_verify.side_effect = lambda pub, sig, md5: ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), b"\x04" + pub
            )

            task = asyncio.create_task(h.run(client))
            while client._notify_callback is None:
                await asyncio.sleep(0)

            # Feed challenge → capture legacy reply.
            client.feed(b"\x2a\x2a\x01" + random_bytes)
            legacy_reply = await _await_send(client)
            assert legacy_reply[:3] == b"\x2a\x2a\x02"

            # Feed encrypted ECDH frame → capture app's ECDH reply, mirror its
            # decryption on our side to keep the CBC IV state in sync with the
            # handshake's enc_session.
            client.feed(enc_ecdh)
            ecdh_reply = await _await_send(client)
            enc_session.decrypt(ecdh_reply)

            # Now encrypt and feed the bad confirmation.
            enc_bad_conf = enc_session.encrypt(bad_conf)
            client.feed(enc_bad_conf)

            with pytest.raises(ValueError, match="Expected confirmation 0x2A2A06"):
                await task
