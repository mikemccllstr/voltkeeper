# ABOUTME: Unit tests for StateStore — update on parser message, query, concurrent read safety.

import asyncio
import threading

import pytest

from voltkeeper.bus import EventBus, ParserMessage
from voltkeeper.core.devices.ac2a import AC2A
from voltkeeper.state_store import StateStore


@pytest.fixture
def device():
    return AC2A("AA:BB:CC:DD:EE:FF", "1234567890")


@pytest.fixture
def device2():
    return AC2A("11:22:33:44:55:66", "0987654321")


class TestStateStore:
    def test_get_unknown_device_returns_empty(self):
        bus = EventBus()
        store = StateStore(bus)
        assert store.get("FF:EE:DD:CC:BB:AA") == {}

    def test_get_all_empty_initially(self):
        bus = EventBus()
        store = StateStore(bus)
        assert store.get_all() == {}

    def test_state_updated_on_parser_message(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg = ParserMessage(device, {"packTotalSoc": 85, "acOutputPower": 150})
        asyncio.run(store._on_parser_message(msg))
        state = store.get(device.address)
        assert state == {"packTotalSoc": 85, "acOutputPower": 150}

    def test_state_updated_twice_overwrites(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg1 = ParserMessage(device, {"packTotalSoc": 85})
        msg2 = ParserMessage(device, {"packTotalSoc": 72, "packTotalVoltage": 52.0})
        asyncio.run(store._on_parser_message(msg1))
        asyncio.run(store._on_parser_message(msg2))
        state = store.get(device.address)
        assert state == {"packTotalSoc": 72, "packTotalVoltage": 52.0}

    def test_get_returns_copy_not_reference(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg = ParserMessage(device, {"packTotalSoc": 85})
        asyncio.run(store._on_parser_message(msg))
        state = store.get(device.address)
        state["packTotalSoc"] = 999
        assert store.get(device.address)["packTotalSoc"] == 85

    def test_get_all_returns_copy_not_reference(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg = ParserMessage(device, {"packTotalSoc": 85})
        asyncio.run(store._on_parser_message(msg))
        all_states = store.get_all()
        all_states[device.address]["packTotalSoc"] = 999
        assert store.get(device.address)["packTotalSoc"] == 85

    def test_multiple_devices(self, device, device2):
        bus = EventBus()
        store = StateStore(bus)
        msg1 = ParserMessage(device, {"packTotalSoc": 85})
        msg2 = ParserMessage(device2, {"packTotalSoc": 42})
        asyncio.run(store._on_parser_message(msg1))
        asyncio.run(store._on_parser_message(msg2))
        assert store.get(device.address)["packTotalSoc"] == 85
        assert store.get(device2.address)["packTotalSoc"] == 42
        all_states = store.get_all()
        assert len(all_states) == 2

    def test_concurrent_reads_from_multiple_threads(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg = ParserMessage(device, {"packTotalSoc": 85})
        asyncio.run(store._on_parser_message(msg))

        results = []

        def _read():
            for _ in range(100):
                s = store.get(device.address)
                results.append(s.get("packTotalSoc"))

        threads = [threading.Thread(target=_read) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 85 for r in results)
        assert len(results) == 500

    def test_concurrent_read_write_from_multiple_threads(self, device):
        bus = EventBus()
        store = StateStore(bus)
        msg = ParserMessage(device, {"packTotalSoc": 50})
        asyncio.run(store._on_parser_message(msg))

        exceptions = []

        def _read():
            try:
                for _ in range(100):
                    store.get(device.address)
            except Exception as e:
                exceptions.append(e)

        def _write():
            try:
                for i in range(100):
                    msg = ParserMessage(device, {"packTotalSoc": i})
                    asyncio.run(store._on_parser_message(msg))
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=_read) for _ in range(3)] + [
            threading.Thread(target=_write) for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(exceptions) == 0
