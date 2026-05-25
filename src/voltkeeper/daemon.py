# ABOUTME: voltkeeperd — long-running daemon that manages multiple Bluetti devices via BLE.
# ABOUTME: Serves REST API + WebSocket + Web UI. All components run in a single asyncio event loop.

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiohttp import web

from . import state_store
from .api import create_app
from .bus import EventBus
from .config import Config, load_config
from .device_manager import DeviceManager

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: Config | None = None, *, config_path: Path | None = None):
        self._config = config or load_config(config_path)
        self._bus = EventBus()
        self._store = state_store.StateStore(self._bus)
        self._device_manager = DeviceManager(self._config, self._bus)
        self._app = create_app(self._config, self._bus, self._store, self._device_manager)
        self._runner: web.AppRunner | None = None
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    def run(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)

        logger.info("voltkeeperd starting...")

        self._tasks.append(asyncio.create_task(self._bus.run(), name="bus"))
        self._tasks.append(asyncio.create_task(self._device_manager.run_periodic(), name="device_manager_reconcile"))

        await self._device_manager.startup_scan()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        host = self._resolve_host()
        site = web.TCPSite(self._runner, host=host, port=self._config.server.port)
        await site.start()
        logger.info(f"HTTP server listening on {host}:{self._config.server.port}")

        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass

        await self._shutdown()

    def _resolve_host(self) -> str:
        if self._config.server.interface:
            return _get_interface_ip(self._config.server.interface, self._config.server.host)
        return self._config.server.host

    def _handle_signal(self) -> None:
        logger.info("Received shutdown signal")
        self._shutdown_event.set()

    async def _shutdown(self) -> None:
        logger.info("voltkeeperd shutting down...")

        await self._device_manager.shutdown()

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self._runner:
            await self._runner.cleanup()

        logger.info("voltkeeperd stopped")


def _get_interface_ip(interface: str, fallback: str) -> str:
    import fcntl
    import socket
    import struct

    ifreq = struct.pack("256s", interface.encode("utf-8")[:15])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ip = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), 0x8915, ifreq)[20:24])
        return ip
    except OSError:
        logger.warning(f"Could not resolve interface {interface}, falling back to {fallback}")
        return fallback
    finally:
        sock.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    daemon = Daemon()
    daemon.run()


if __name__ == "__main__":
    main()
