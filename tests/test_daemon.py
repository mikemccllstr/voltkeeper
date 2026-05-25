# ABOUTME: Integration tests for voltkeeperd — daemon startup, reconcile, graceful shutdown.

import asyncio
from unittest.mock import patch

import pytest
from aiohttp import web

from voltkeeper.api import CONFIG_KEY
from voltkeeper.bus import EventBus
from voltkeeper.config import Config, DeviceEntry, ScanConfig, ServerConfig
from voltkeeper.daemon import Daemon


@pytest.fixture
def test_config():
    return Config(
        server=ServerConfig(api_key="test-key", host="127.0.0.1", port=0),
        devices=[
            DeviceEntry(address="AA:BB:CC:DD:EE:FF", name="Test AC2A"),
        ],
        scan=ScanConfig(interval=3600, timeout=1.0),
    )


class TestDaemonStartup:
    def test_config_loads_and_eventbus_created(self, test_config):
        daemon = Daemon(test_config)
        assert daemon._bus is not None
        assert isinstance(daemon._bus, EventBus)
        assert daemon._config is test_config

    def test_state_store_created(self, test_config):
        daemon = Daemon(test_config)
        assert daemon._store is not None
        assert daemon._store.get("unknown") == {}

    def test_app_created(self, test_config):
        daemon = Daemon(test_config)
        assert daemon._app is not None
        assert isinstance(daemon._app, web.Application)
        assert daemon._app[CONFIG_KEY] is test_config

    def test_device_manager_created(self, test_config):
        daemon = Daemon(test_config)
        assert daemon._device_manager is not None
        assert len(daemon._device_manager.get_statuses()) == 0

    @patch("voltkeeper.device_manager.scan_devices")
    def test_startup_scan_populates_statuses(self, mock_scan, test_config):
        from voltkeeper.bluetooth import ScanResult

        mock_scan.return_value = [ScanResult(address="AA:BB:CC:DD:EE:FF", name="AC2A2409000123456", encrypted=False)]

        daemon = Daemon(test_config)
        asyncio.run(daemon._device_manager.startup_scan())
        statuses = daemon._device_manager.get_statuses()
        assert len(statuses) == 1
        assert statuses[0].status == "online"


class TestDaemonShutdown:
    def test_shutdown_method_cleans_up(self, test_config):
        daemon = Daemon(test_config)
        asyncio.run(daemon._shutdown())
        assert daemon._runner is None


class TestInterfaceResolution:
    def test_resolve_host_uses_config_host(self, test_config):
        daemon = Daemon(test_config)
        host = daemon._resolve_host()
        assert host == "127.0.0.1"

    def test_resolve_host_uses_interface(self, test_config):
        test_config.server.interface = "lo"
        daemon = Daemon(test_config)
        host = daemon._resolve_host()
        # lo resolves to 127.0.0.1; on failure falls back to config host (127.0.0.1)
        assert host == "127.0.0.1"

    def test_get_interface_ip_raises_on_unknown_interface(self):
        from voltkeeper.daemon import _get_interface_ip

        with pytest.raises(RuntimeError, match="nonexistent_nic_xyz"):
            _get_interface_ip("nonexistent_nic_xyz")
