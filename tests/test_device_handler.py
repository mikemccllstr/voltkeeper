# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

import asyncio
import time
from pathlib import Path

import pytest

from voltkeeper.bus import CommandMessage, EventBus
from voltkeeper.core.commands import WriteSingleRegister
from voltkeeper.core.utils import (
    crc16_modbus,
)
from voltkeeper.device_handler import SourceChangeWatcher, _watch_source_changes


class TestDeviceHandler:
    @pytest.mark.asyncio
    async def test_poll_once_no_double_strip(self, ac2a_device, ac2a_home_bytes):
        """execute() already returns stripped body; _poll_once must not strip again."""
        from unittest.mock import MagicMock

        from voltkeeper.device_handler import DeviceHandler

        bus = EventBus()
        handler = DeviceHandler("00:00:00:00:00:00", ac2a_device, 0, bus)

        mock_client = MagicMock()
        handler.client = mock_client
        mock_client.is_connected = True

        # execute() returns the already-stripped body (12 bytes for 6 regs)
        home_body = ac2a_home_bytes[:12]

        async def fake_execute(cmd):
            return home_body

        mock_client.execute = fake_execute

        received = []
        bus.add_parser_listener(lambda msg: received.append(msg))

        bus_task = asyncio.create_task(bus.run())
        await handler._poll_once_individual()
        await asyncio.sleep(0.1)
        bus_task.cancel()

        assert len(received) > 0, "no ParserMessage dispatched"
        parsed = received[0].parsed
        # These should be real-looking values, not garbled by double-strip
        assert "packTotalSoc" in parsed
        assert parsed["packTotalSoc"] == 100
        assert 20 <= parsed["packTotalVoltage"] <= 40
        assert 0 <= parsed["packTotalCurrent"] <= 100

    @pytest.mark.asyncio
    async def test_command_handled_mid_poll_no_corruption(self, ac2a_device):
        """A CommandMessage handled mid-poll does not corrupt the in-flight poll."""
        import struct
        from unittest.mock import AsyncMock, PropertyMock, patch

        from voltkeeper.bluetooth.client import BluetoothClient
        from voltkeeper.core.commands import ReadHoldingRegisters
        from voltkeeper.device_handler import DeviceHandler

        bus = EventBus()
        handler = DeviceHandler("00:00:00:00:00:00", ac2a_device, 60, bus)
        client = BluetoothClient("00:00:00:00:00:00", encrypted=False)
        client.client = AsyncMock()
        client.client.is_connected = True
        handler.client = client

        small_read = ReadHoldingRegisters(100, 6)
        mock_prop = PropertyMock(return_value=[small_read])
        with patch.object(type(ac2a_device), "polling_commands", mock_prop):
            write_log = []
            poll_read_parked = asyncio.Event()

            async def controlled_write(uuid, data, response=False):
                cmd = client._current_cmd
                write_log.append(cmd)
                if isinstance(cmd, ReadHoldingRegisters):
                    await poll_read_parked.wait()

            client.client.write_gatt_char = controlled_write

            async def start_poll():
                try:
                    await handler._poll_once_individual()
                except Exception:
                    pass

            poll_task = asyncio.create_task(start_poll())
            await asyncio.sleep(0)

            assert len(write_log) == 1
            assert isinstance(write_log[0], ReadHoldingRegisters)

            write_cmd = WriteSingleRegister(2015, 3)
            msg = CommandMessage(ac2a_device, write_cmd)
            cmd_task = asyncio.create_task(handler.handle_command(msg))
            await asyncio.sleep(0)

            assert len(write_log) == 1, "write command must not write mid-poll"

            resp1_data = b"\x00\x01" * 6
            resp1_msg = b"\x01\x03\x0c" + resp1_data
            resp1 = resp1_msg + crc16_modbus(resp1_msg)
            client._on_notification(0, bytearray(resp1))
            poll_read_parked.set()

            await poll_task
            await asyncio.sleep(0)

            assert len(write_log) >= 2, "write command should have written after poll"

            resp2 = struct.pack("!BBHH", 1, 6, 2015, 3)
            resp2 += crc16_modbus(resp2)
            client._on_notification(0, bytearray(resp2))
            await cmd_task


class TestPollIntervalPacing:
    @pytest.mark.asyncio
    async def test_period_equals_configured_interval(self, ac2a_device):
        """Start-to-start period equals interval when a cycle finishes early."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from voltkeeper.device_handler import DeviceHandler

        bus = MagicMock()
        handler = DeviceHandler("AA:BB:CC:DD:EE:FF", ac2a_device, 10, bus)
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        handler.client = mock_client
        handler._discover_topology = AsyncMock()
        handler._poll_once = AsyncMock()

        sleep_calls = []

        async def fake_sleep(duration):
            sleep_calls.append(duration)
            raise asyncio.CancelledError()

        time_values = [0.0, 3.0]

        with patch("voltkeeper.device_handler.asyncio.sleep", fake_sleep):
            with patch("voltkeeper.device_handler.time.monotonic", side_effect=time_values):
                try:
                    await handler.run()
                except asyncio.CancelledError:
                    pass

        assert len(sleep_calls) == 1, f"Expected 1 sleep, got {len(sleep_calls)}"
        assert sleep_calls[0] == 7.0, f"Expected sleep({10 - 3}) = 7.0, got {sleep_calls[0]}"

    @pytest.mark.asyncio
    async def test_slow_cycle_starts_next_immediately(self, ac2a_device):
        """A cycle longer than the interval starts the next cycle immediately."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from voltkeeper.device_handler import DeviceHandler

        bus = MagicMock()
        handler = DeviceHandler("AA:BB:CC:DD:EE:FF", ac2a_device, 10, bus)
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        handler.client = mock_client
        handler._discover_topology = AsyncMock()
        handler._poll_once = AsyncMock()

        sleep_calls = []

        async def fake_sleep(duration):
            sleep_calls.append(duration)
            raise asyncio.CancelledError()

        time_values = [0.0, 12.0]

        with patch("voltkeeper.device_handler.asyncio.sleep", fake_sleep):
            with patch("voltkeeper.device_handler.time.monotonic", side_effect=time_values):
                try:
                    await handler.run()
                except asyncio.CancelledError:
                    pass

        assert len(sleep_calls) == 1, f"Expected 1 sleep, got {len(sleep_calls)}"
        assert sleep_calls[0] == 0.0, f"Expected sleep(0.0) when elapsed > interval, got {sleep_calls[0]}"

    @pytest.mark.asyncio
    async def test_interval_zero_polls_back_to_back(self, ac2a_device):
        """Interval 0 polls back-to-back with no sleep between cycles."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from voltkeeper.device_handler import DeviceHandler

        bus = MagicMock()
        handler = DeviceHandler("AA:BB:CC:DD:EE:FF", ac2a_device, 0, bus)
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        handler.client = mock_client
        handler._discover_topology = AsyncMock()
        handler._poll_once = AsyncMock()

        sleep_calls = []

        async def fake_sleep(duration):
            sleep_calls.append(duration)

        with patch("voltkeeper.device_handler.asyncio.sleep", fake_sleep):
            run_task = asyncio.create_task(handler.run())
            await asyncio.sleep(0)
            run_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run_task

        positive_sleeps = [d for d in sleep_calls if d > 0]
        assert len(positive_sleeps) == 0, f"Expected no positive sleep for interval=0, got {positive_sleeps}"


class TestSourceChangeWatcher:
    def test_watcher_event_set_on_py_modify(self, tmp_path):
        (tmp_path / "mod.py").touch()
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        try:
            (tmp_path / "mod.py").write_text("x = 1")
            time.sleep(0.3)
            assert watcher.changed.is_set()
        finally:
            watcher.stop()

    def test_watcher_event_not_set_on_non_py(self, tmp_path):
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        try:
            (tmp_path / "notes.txt").write_text("hello")
            time.sleep(0.3)
            assert not watcher.changed.is_set()
        finally:
            watcher.stop()

    def test_watcher_start_stop(self, tmp_path):
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        watcher.stop()  # should not raise

    def test_watch_coroutine_exits_on_event(self):
        watcher = SourceChangeWatcher(Path("/tmp"))
        watcher.changed.set()
        import pytest

        with pytest.raises(SystemExit) as exc:
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_watch_source_changes(watcher))
        assert exc.value.code == 0

    def test_watch_coroutine_does_not_exit_without_event(self):
        watcher = SourceChangeWatcher(Path("/tmp"))

        async def run():
            try:
                await asyncio.wait_for(_watch_source_changes(watcher), timeout=0.2)
            except asyncio.TimeoutError:
                pass  # expected — coroutine didn't exit

        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(run())
