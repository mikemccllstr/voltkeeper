# ABOUTME: Test that BluetoothClient.connect runs handshake when encrypted=True.

from unittest.mock import AsyncMock, patch

import pytest

from voltkeeper.bluetooth.client import BluetoothClient


class TestBluetoothClientConnectEncrypted:
    @pytest.mark.asyncio
    async def test_connect_runs_handshake_when_encrypted(self):
        with patch("voltkeeper.bluetooth.client.BleakClient", autospec=True) as mock_bleak:
            mock_bleak_instance = mock_bleak.return_value
            mock_bleak_instance.connect = AsyncMock()
            mock_bleak_instance.start_notify = AsyncMock()
            mock_bleak_instance.disconnect = AsyncMock()

            with patch("voltkeeper.bluetooth.client.HandshakeSession") as mock_hs:
                mock_hs_instance = mock_hs.return_value
                mock_hs_instance.run = AsyncMock()

                c = BluetoothClient("AA:BB:CC:DD:EE:FF", encrypted=True)
                await c.connect()

                mock_hs_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_encrypted_calls_start_notify_exactly_once(self):
        """start_notify must be called once total; a second call would trigger a device challenge reset."""
        with patch("voltkeeper.bluetooth.client.BleakClient", autospec=True) as mock_bleak:
            mock_bleak_instance = mock_bleak.return_value
            mock_bleak_instance.connect = AsyncMock()
            mock_bleak_instance.start_notify = AsyncMock()
            mock_bleak_instance.disconnect = AsyncMock()

            with patch("voltkeeper.bluetooth.client.HandshakeSession") as mock_hs:
                mock_hs_instance = mock_hs.return_value
                mock_hs_instance.run = AsyncMock()

                c = BluetoothClient("AA:BB:CC:DD:EE:FF", encrypted=True)
                await c.connect()

                # The fix: start_notify must be called EXACTLY once (not once in HandshakeSession
                # and again in connect()).  A double-subscribe resets the device's challenge state.
                assert mock_bleak_instance.start_notify.call_count == 1, (
                    "start_notify must be called exactly once; a second call triggers device challenge reset"
                )

    @pytest.mark.asyncio
    async def test_connect_skips_handshake_when_plaintext(self):
        with patch("voltkeeper.bluetooth.client.BleakClient", autospec=True) as mock_bleak:
            mock_bleak_instance = mock_bleak.return_value
            mock_bleak_instance.connect = AsyncMock()
            mock_bleak_instance.start_notify = AsyncMock()

            with patch("voltkeeper.bluetooth.client.HandshakeSession") as mock_hs:
                c = BluetoothClient("AA:BB:CC:DD:EE:FF", encrypted=False)
                await c.connect()

                mock_hs.return_value.run.assert_not_called()
