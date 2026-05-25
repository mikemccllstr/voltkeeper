# ABOUTME: Unit tests for DeviceManager — reconciliation, handler lifecycle, status transitions.

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from voltkeeper.bluetooth import ScanResult
from voltkeeper.bus import EventBus
from voltkeeper.config import Config, DeviceEntry, ScanConfig, ServerConfig
from voltkeeper.device_manager import DeviceManager


@pytest.fixture
def config():
    return Config(
        server=ServerConfig(api_key="test"),
        devices=[
            DeviceEntry(address="AA:BB:CC:DD:EE:FF", name="Living Room"),
            DeviceEntry(address="11:22:33:44:55:66"),
        ],
        scan=ScanConfig(interval=60, timeout=5.0),
    )


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def manager(config, bus):
    return DeviceManager(config, bus)


@pytest.fixture
def mock_scan_results():
    return [
        ScanResult(address="AA:BB:CC:DD:EE:FF", name="AC2A2409000123456", encrypted=False),
        ScanResult(address="11:22:33:44:55:66", name="AC200L2409000789012", encrypted=False),
    ]


class TestDeviceManagerReconciliation:
    def test_all_devices_online(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=mock_scan_results)
        asyncio.run(manager._reconcile())
        statuses = {s.address: s for s in manager.get_statuses()}
        assert statuses["AA:BB:CC:DD:EE:FF"].status == "online"
        assert statuses["11:22:33:44:55:66"].status == "online"

    def test_one_device_missing(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=[mock_scan_results[0]])
        asyncio.run(manager._reconcile())
        statuses = {s.address: s for s in manager.get_statuses()}
        assert statuses["AA:BB:CC:DD:EE:FF"].status == "online"
        assert statuses["11:22:33:44:55:66"].status == "missing"

    def test_new_device_in_scan(self, manager, mock_scan_results):
        manager._scan = AsyncMock(
            return_value=mock_scan_results
            + [ScanResult(address="FF:EE:DD:CC:BB:AA", name="EP6002409000999999", encrypted=True)]
        )
        asyncio.run(manager._reconcile())
        statuses = {s.address: s for s in manager.get_statuses()}
        assert len(statuses) == 3
        assert statuses["FF:EE:DD:CC:BB:AA"].status == "new"
        assert statuses["FF:EE:DD:CC:BB:AA"].encrypted is True

    def test_no_devices_configured(self, bus):
        config = Config(server=ServerConfig(api_key="test"), devices=[])
        manager = DeviceManager(config, bus)
        manager._scan = AsyncMock(
            return_value=[ScanResult(address="AA:BB:CC:DD:EE:FF", name="AC2A2409000123456", encrypted=False)]
        )
        asyncio.run(manager._reconcile())
        statuses = manager.get_statuses()
        assert len(statuses) == 1
        assert statuses[0].status == "new"

    def test_status_transitions_online_to_missing(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=mock_scan_results)
        asyncio.run(manager._reconcile())
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "online"

        manager._scan = AsyncMock(return_value=[mock_scan_results[1]])
        asyncio.run(manager._reconcile())
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "missing"

    def test_status_transitions_missing_to_online(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=[mock_scan_results[1]])
        asyncio.run(manager._reconcile())
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "missing"

        manager._scan = AsyncMock(return_value=mock_scan_results)
        asyncio.run(manager._reconcile())
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "online"

    def test_scan_failure_no_crash(self, manager):
        with patch("voltkeeper.device_manager.scan_devices", side_effect=Exception("BLE error")):
            asyncio.run(manager._reconcile())
        statuses = manager.get_statuses()
        assert statuses[0].status == "missing"
        assert statuses[1].status == "missing"

    def test_unknown_device_status_returns_none(self, manager):
        assert manager.get_status("ZZ:ZZ:ZZ:ZZ:ZZ:ZZ") is None

    def test_device_type_populated_for_online(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=mock_scan_results)
        asyncio.run(manager._reconcile())
        ds = manager.get_status("AA:BB:CC:DD:EE:FF")
        assert ds.device_type == "AC2A"
        assert ds.sn == "2409000123456"

    def test_unrecognized_device_no_type(self, manager):
        manager._scan = AsyncMock(
            return_value=[ScanResult(address="FF:EE:DD:CC:BB:AA", name="UNKNOWN123", encrypted=False)]
        )
        asyncio.run(manager._reconcile())
        ds = manager.get_status("FF:EE:DD:CC:BB:AA")
        assert ds.device_type is None
        assert ds.status == "new"

    def test_connected_device_stays_online_despite_missing_scan(self, manager, mock_scan_results):
        manager._scan = AsyncMock(return_value=mock_scan_results)
        asyncio.run(manager._reconcile())
        manager._handlers["AA:BB:CC:DD:EE:FF"] = None  # simulate active handler
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "online"

        manager._scan = AsyncMock(return_value=[])
        asyncio.run(manager._reconcile())
        assert manager.get_status("AA:BB:CC:DD:EE:FF").status == "online"
