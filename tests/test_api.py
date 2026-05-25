# ABOUTME: Unit tests for HTTP API — middleware, REST endpoints, WebSocket.

import asyncio

import aiohttp
import pytest
from aiohttp import web

from voltkeeper.api import create_app
from voltkeeper.bus import EventBus
from voltkeeper.config import Config, DeviceEntry, ServerConfig
from voltkeeper.core.devices.ac2a import AC2A
from voltkeeper.device_manager import DeviceManager, DeviceStatus
from voltkeeper.state_store import StateStore


@pytest.fixture
def config(unused_tcp_port):
    return Config(
        server=ServerConfig(api_key="test-key-123", host="127.0.0.1", port=unused_tcp_port),
        devices=[DeviceEntry(address="AA:BB:CC:DD:EE:FF", name="Test AC2A")],
    )


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def store(bus):
    return StateStore(bus)


@pytest.fixture
def device():
    return AC2A("AA:BB:CC:DD:EE:FF", "1234567890")


@pytest.fixture
def device_manager(config, bus):
    dm = DeviceManager(config, bus)
    dm._statuses = {
        "AA:BB:CC:DD:EE:FF": DeviceStatus(
            address="AA:BB:CC:DD:EE:FF",
            name="Test AC2A",
            status="online",
            encrypted=False,
            device_type="AC2A",
            sn="1234567890",
        ),
    }
    return dm


@pytest.fixture
def app(config, bus, store, device_manager):
    return create_app(config, bus, store, device_manager)


def _auth_headers(config):
    return {"Authorization": f"Bearer {config.server.api_key}"}


async def _create_cli(app, port):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner, site


class TestAuthMiddleware:
    def test_valid_api_key_allows_request(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 200
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_invalid_api_key_returns_401(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={"Authorization": "Bearer wrong-key"}) as resp:
                        assert resp.status == 401
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_missing_api_key_returns_401(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        assert resp.status == 401
            finally:
                await runner.cleanup()

        asyncio.run(_run())


class TestAclMiddleware:
    def test_allowed_network_passes(self, config, bus, store, device_manager):
        config.server.allowed_networks = ["127.0.0.0/8"]

        async def _run():
            app = create_app(config, bus, store, device_manager)
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 200
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_disallowed_network_blocked(self, config, bus, store, device_manager):
        config.server.allowed_networks = ["10.0.0.0/8"]

        async def _run():
            app = create_app(config, bus, store, device_manager)
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 403
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_empty_acl_passes(self, config, bus, store, device_manager):
        config.server.allowed_networks = []

        async def _run():
            app = create_app(config, bus, store, device_manager)
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 200
            finally:
                await runner.cleanup()

        asyncio.run(_run())


class TestApiDevices:
    def test_returns_device_list(self, app, config, store, bus):
        async def _run():
            dev = AC2A("AA:BB:CC:DD:EE:FF", "1234567890")
            msg = type("msg", (), {"device": dev, "parsed": {"packTotalSoc": 85}})
            await store._on_parser_message(msg)

            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 200
                        data = await resp.json()
                        assert isinstance(data, list)
                        assert len(data) == 1
                        assert data[0]["address"] == "AA:BB:CC:DD:EE:FF"
                        assert data[0]["status"] == "online"
                        assert data[0]["summary"]["soc"] == 85
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_empty_device_list(self, bus, store, unused_tcp_port):
        config = Config(server=ServerConfig(api_key="key", port=unused_tcp_port), devices=[])

        async def _run():
            dm = DeviceManager(config, bus)
            app = create_app(config, bus, store, dm)
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/devices"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={"Authorization": "Bearer key"}) as resp:
                        assert resp.status == 200
                        data = await resp.json()
                        assert data == []
            finally:
                await runner.cleanup()

        asyncio.run(_run())


class TestApiDevice:
    def test_returns_device_state(self, app, config, store, bus):
        async def _run():
            dev = AC2A("AA:BB:CC:DD:EE:FF", "1234567890")
            msg = type("msg", (), {"device": dev, "parsed": {"packTotalSoc": 92, "packTotalVoltage": 52.0}})
            await store._on_parser_message(msg)

            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 200
                        data = await resp.json()
                        assert data["packTotalSoc"] == 92
                        assert data["packTotalVoltage"] == 52.0
                        assert data["_status"] == "online"
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_unknown_device_returns_404(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/ZZ:ZZ:ZZ:ZZ:ZZ:ZZ"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=_auth_headers(config)) as resp:
                        assert resp.status == 404
            finally:
                await runner.cleanup()

        asyncio.run(_run())


class TestApiCommand:
    def test_valid_command_accepted(self, app, config, device_manager, bus):
        async def _run():
            dev = AC2A("AA:BB:CC:DD:EE:FF", "1234567890")
            device_manager._devices["AA:BB:CC:DD:EE:FF"] = dev
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"field": "ac_output", "value": True},
                        headers=_auth_headers(config),
                    ) as resp:
                        assert resp.status == 200
                        data = await resp.json()
                        assert data["accepted"] is True
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_command_to_missing_device_returns_503(self, app, config, device_manager):
        device_manager._statuses["AA:BB:CC:DD:EE:FF"] = DeviceStatus(
            address="AA:BB:CC:DD:EE:FF",
            name="Test AC2A",
            status="missing",
            encrypted=False,
        )

        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"field": "ac_output", "value": True},
                        headers=_auth_headers(config),
                    ) as resp:
                        assert resp.status == 503
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_command_to_unknown_device_returns_404(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/ZZ:ZZ:ZZ:ZZ:ZZ:ZZ/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"field": "ac_output", "value": True},
                        headers=_auth_headers(config),
                    ) as resp:
                        assert resp.status == 404
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_invalid_json_returns_400(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        data="not json",
                        headers={**_auth_headers(config), "Content-Type": "application/json"},
                    ) as resp:
                        assert resp.status == 400
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_missing_field_returns_400(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"value": True},
                        headers=_auth_headers(config),
                    ) as resp:
                        assert resp.status == 400
            finally:
                await runner.cleanup()

        asyncio.run(_run())

    def test_unsupported_field_returns_400(self, app, config, device_manager, bus):
        async def _run():
            dev = AC2A("AA:BB:CC:DD:EE:FF", "1234567890")
            device_manager._devices["AA:BB:CC:DD:EE:FF"] = dev
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/api/device/AA:BB:CC:DD:EE:FF/command"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"field": "nonexistent_field", "value": 42},
                        headers=_auth_headers(config),
                    ) as resp:
                        assert resp.status == 400
            finally:
                await runner.cleanup()

        asyncio.run(_run())


class TestWebSocket:
    def test_websocket_connects(self, app, config):
        async def _run():
            runner, site = await _create_cli(app, config.server.port)
            try:
                url = f"http://127.0.0.1:{config.server.port}/ws"
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        assert ws is not None
            finally:
                await runner.cleanup()

        asyncio.run(_run())
