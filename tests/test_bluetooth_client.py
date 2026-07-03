# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

import asyncio

import pytest

from voltkeeper.core.utils import (
    crc16_modbus,
)


class TestBluetoothClientExecuteSerialization:
    @staticmethod
    def _build_read_response(values):
        import struct

        data = struct.pack(f"!{len(values)}H", *values)
        msg = b"\x01\x03" + struct.pack("!B", len(data)) + data
        return msg + crc16_modbus(msg)

    @staticmethod
    def _make_client():
        from unittest.mock import AsyncMock

        from voltkeeper.bluetooth.client import BluetoothClient

        c = BluetoothClient("AA:BB:CC:DD:EE:FF", encrypted=False)
        c.client = AsyncMock()
        c.client.write_gatt_char = AsyncMock()
        return c

    @pytest.mark.asyncio
    async def test_two_concurrent_calls_each_receive_own_response(self):
        """Two concurrent execute() calls each get their own response — no cross-matching."""
        from voltkeeper.core.commands import ReadHoldingRegisters

        client = self._make_client()

        cmd1 = ReadHoldingRegisters(100, 6)
        cmd2 = ReadHoldingRegisters(200, 6)

        write_log = []

        async def tracked_write(uuid, data, response=False):
            write_log.append(client._current_cmd)

        client.client.write_gatt_char = tracked_write

        task1 = asyncio.create_task(client.execute(cmd1))
        await asyncio.sleep(0)

        task2 = asyncio.create_task(client.execute(cmd2))
        await asyncio.sleep(0)

        # Without serialization, task2 would have entered the loop and
        # overwritten _current_cmd / _notify_response, and its write would
        # appear in the log.
        assert client._current_cmd is cmd1, "cmd2 must not overwrite in-flight state while cmd1 is pending"
        assert len(write_log) == 1, "cmd2 must not write while cmd1 is in flight"
        assert write_log[0] is cmd1

        resp1 = self._build_read_response([1, 2, 3, 4, 5, 6])
        client._on_notification(0, bytearray(resp1))
        result1 = await task1
        assert result1 == resp1[3:-2], "cmd1 got its own parsed body"

        await asyncio.sleep(0)
        assert len(write_log) == 2, "cmd2 must write after cmd1 completes"
        assert write_log[1] is cmd2

        resp2 = self._build_read_response([10, 20, 30, 40, 50, 60])
        client._on_notification(0, bytearray(resp2))
        result2 = await task2
        assert result2 == resp2[3:-2], "cmd2 got its own parsed body"

        assert result1 != result2, "responses must not be identical"

    @pytest.mark.asyncio
    async def test_second_not_written_until_first_completes(self):
        """A second execute() call is not written until the first exits."""
        from voltkeeper.core.commands import ReadHoldingRegisters

        client = self._make_client()

        cmd1 = ReadHoldingRegisters(100, 6)
        cmd2 = ReadHoldingRegisters(200, 6)

        write_count = 0

        async def counted_write(uuid, data, response=False):
            nonlocal write_count
            write_count += 1

        client.client.write_gatt_char = counted_write

        task1 = asyncio.create_task(client.execute(cmd1))
        await asyncio.sleep(0)

        task2 = asyncio.create_task(client.execute(cmd2))
        await asyncio.sleep(0)

        assert write_count == 1, "only one write before first command completes"

        resp1 = self._build_read_response([100, 200, 300, 400, 500, 600])
        client._on_notification(0, bytearray(resp1))
        await task1

        await asyncio.sleep(0)
        assert write_count == 2, "second write must happen after first completes"

        resp2 = self._build_read_response([1, 2, 3, 4, 5, 6])
        client._on_notification(0, bytearray(resp2))
        await task2

    @pytest.mark.asyncio
    async def test_queued_call_runs_after_first_exhausts_retries(self):
        """A queued call runs cleanly after the first call exhausts all retries."""
        from voltkeeper.bluetooth.client import MAX_RETRIES
        from voltkeeper.core.commands import ReadHoldingRegisters

        client = self._make_client()

        cmd1 = ReadHoldingRegisters(100, 6)
        cmd2 = ReadHoldingRegisters(200, 6)

        writes_by_cmd = {cmd1: 0, cmd2: 0}

        async def fail_n_times(uuid, data, response=False):
            writes_by_cmd[client._current_cmd] += 1

            if client._current_cmd is cmd1:
                client._notify_future.set_exception(asyncio.TimeoutError())

        client.client.write_gatt_char = fail_n_times

        task1 = asyncio.create_task(client.execute(cmd1))
        await asyncio.sleep(0)

        task2 = asyncio.create_task(client.execute(cmd2))
        await asyncio.sleep(0)

        with pytest.raises(Exception) as exc_info:
            await task1

        assert "retries" in str(exc_info.value) or "Timeout" in str(exc_info.value)

        # Now cmd2 must complete successfully with its own response.
        # With serialization: cmd2 has NOT written yet (blocked by lock until
        # cmd1 gives up).  Without serialization: cmd2 may have already
        # written while cmd1 was still retrying.
        resp2 = self._build_read_response([7, 8, 9, 10, 11, 12])
        client._on_notification(0, bytearray(resp2))
        result2 = await task2
        assert result2 == resp2[3:-2], "cmd2 must complete after cmd1's failure"

        # Verify cmd1 exhausted exactly MAX_RETRIES without cmd2 interleaving.
        assert writes_by_cmd[cmd1] == MAX_RETRIES, (
            f"cmd1 should have retried {MAX_RETRIES} times, got {writes_by_cmd[cmd1]}"
        )

    @pytest.mark.asyncio
    async def test_no_interleaving_between_retries(self):
        """No other command writes between a failed attempt and its retry."""
        from voltkeeper.core.commands import ReadHoldingRegisters

        client = self._make_client()

        cmd1 = ReadHoldingRegisters(100, 6)
        cmd2 = ReadHoldingRegisters(200, 6)

        write_log = []
        first_attempt = True

        async def interleave_check_write(uuid, data, response=False):
            write_log.append(client._current_cmd)

            if client._current_cmd is cmd1:
                nonlocal first_attempt
                if first_attempt:
                    first_attempt = False
                    # Deliver bad notification (CRC-mismatched) via the real
                    # handler so ParseError is raised inside _on_notification.
                    bad_data = bytearray(b"\x00" * cmd1.response_size())
                    client._on_notification(0, bad_data)

        client.client.write_gatt_char = interleave_check_write

        task1 = asyncio.create_task(client.execute(cmd1))
        await asyncio.sleep(0)
        # cmd1 has written its first attempt; the bad notification triggers
        # ParseError and it loops back to retry (still holding the lock).

        task2 = asyncio.create_task(client.execute(cmd2))
        await asyncio.sleep(0)

        # With serialization: every write so far belongs to cmd1; cmd2 is
        # blocked by the lock.
        for idx, cmd in enumerate(write_log):
            assert cmd is cmd1, f"write {idx} should be cmd1, got {cmd}"

        assert len(write_log) >= 2, "cmd1 should have initial write + at least one retry"

        # Resolve cmd1's retry so it completes and releases the lock.
        resp1 = self._build_read_response([50, 51, 52, 53, 54, 55])
        client._on_notification(0, bytearray(resp1))
        result1 = await task1
        assert result1 == resp1[3:-2]

        # cmd2 proceeds now.
        await asyncio.sleep(0)
        resp2 = self._build_read_response([60, 61, 62, 63, 64, 65])
        client._on_notification(0, bytearray(resp2))
        result2 = await task2
        assert result2 == resp2[3:-2]


class TestBluetoothClientDisconnect:
    @staticmethod
    def _make_client():
        from unittest.mock import AsyncMock

        from voltkeeper.bluetooth.client import BluetoothClient

        c = BluetoothClient("AA:BB:CC:DD:EE:FF", encrypted=False)
        c.client = AsyncMock()
        c.client.is_connected = True
        c.client.stop_notify = AsyncMock()
        c.client.disconnect = AsyncMock()
        return c

    @pytest.mark.asyncio
    async def test_disconnect_calls_stop_notify_before_disconnect(self):
        from unittest.mock import call

        from voltkeeper.bluetooth import NOTIFY_UUID

        client = self._make_client()
        await client.disconnect()

        assert client.client.stop_notify.called
        assert client.client.disconnect.called
        assert client.client.method_calls.index(call.stop_notify(NOTIFY_UUID)) < client.client.method_calls.index(
            call.disconnect()
        ), "stop_notify must be called before disconnect"

    @pytest.mark.asyncio
    async def test_disconnect_cancels_pending_future(self):
        client = self._make_client()
        client._notify_future = asyncio.get_running_loop().create_future()

        await client.disconnect()

        assert client._notify_future.cancelled(), "pending notify future must be cancelled"

    @pytest.mark.asyncio
    async def test_disconnect_skips_already_done_future(self):
        client = self._make_client()
        client._notify_future = asyncio.get_running_loop().create_future()
        client._notify_future.set_result(b"done")

        await client.disconnect()

        assert not client._notify_future.cancelled(), "resolved future must not be cancelled"

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_not_connected(self):
        client = self._make_client()
        client.client.is_connected = False

        await client.disconnect()

        client.client.stop_notify.assert_not_called()
        client.client.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_notify_failure_still_disconnects(self):
        from bleak import BleakError

        client = self._make_client()
        client.client.stop_notify.side_effect = BleakError("stop failed")

        await client.disconnect()

        assert client.client.stop_notify.called
        assert client.client.disconnect.called, "disconnect must still be called after stop_notify failure"

    @pytest.mark.asyncio
    async def test_disconnect_failure_is_suppressed(self):
        from bleak import BleakError

        client = self._make_client()
        client.client.disconnect.side_effect = BleakError("disconnect failed")

        await client.disconnect()
