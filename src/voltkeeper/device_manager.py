# ABOUTME: DeviceManager — reconciles config devices against BLE scans, manages DeviceHandler pool.

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .bluetooth import ScanResult, build_device, scan_devices
from .bus import EventBus
from .config import Config
from .device_handler import DeviceHandler

if TYPE_CHECKING:
    from .core.devices.bluetti_device import BluettiDevice


@dataclass
class DeviceStatus:
    address: str
    name: str
    status: str  # "online", "missing", "new"
    encrypted: bool
    device_type: str | None = None
    sn: str | None = None


class DeviceManager:
    def __init__(self, config: Config, bus: EventBus):
        self._config = config
        self._bus = bus
        self._statuses: dict[str, DeviceStatus] = {}
        self._handlers: dict[str, asyncio.Task] = {}
        self._devices: dict[str, BluettiDevice] = {}
        self._shutting_down = asyncio.Event()

    def get_statuses(self) -> list[DeviceStatus]:
        return list(self._statuses.values())

    def get_status(self, address: str) -> DeviceStatus | None:
        return self._statuses.get(address)

    def get_device(self, address: str) -> BluettiDevice | None:
        return self._devices.get(address)

    async def startup_scan(self):
        await self._reconcile()
        self._start_handlers()

    async def run_periodic(self):
        while not self._shutting_down.is_set():
            try:
                await asyncio.sleep(self._config.scan.interval)
            except asyncio.CancelledError:
                break
            await self._reconcile()
            self._update_handlers()

    async def shutdown(self):
        self._shutting_down.set()
        for task in self._handlers.values():
            task.cancel()
        if self._handlers:
            await asyncio.gather(*self._handlers.values(), return_exceptions=True)
        self._handlers.clear()
        self._devices.clear()

    async def _reconcile(self):
        config_addresses = {d.address.upper() for d in self._config.devices}
        scan_results = await self._scan()

        scan_addresses = {sr.address.upper() for sr in scan_results}
        scan_by_addr = {sr.address.upper(): sr for sr in scan_results}

        new_statuses: dict[str, DeviceStatus] = {}

        for entry in self._config.devices:
            addr = entry.address.upper()
            if addr in scan_addresses:
                sr = scan_by_addr[addr]
                device = _try_build_device(addr, sr.name)
                device_type = type(device).__name__ if device else None
                sn = device.sn if device else None
                new_statuses[addr] = DeviceStatus(
                    address=addr,
                    name=entry.name or sr.name,
                    status="online",
                    encrypted=bool(sr.encrypted),
                    device_type=device_type,
                    sn=sn,
                )
                if device:
                    self._devices[addr] = device
            elif addr in self._handlers:
                existing = self._statuses.get(addr)
                new_statuses[addr] = DeviceStatus(
                    address=addr,
                    name=entry.name or entry.address,
                    status="online",
                    encrypted=existing.encrypted if existing else False,
                    device_type=existing.device_type if existing else None,
                    sn=existing.sn if existing else None,
                )
            else:
                new_statuses[addr] = DeviceStatus(
                    address=addr,
                    name=entry.name or entry.address,
                    status="missing",
                    encrypted=False,
                )

        for sr in scan_results:
            addr = sr.address.upper()
            if addr not in config_addresses:
                device = _try_build_device(addr, sr.name)
                device_type = type(device).__name__ if device else None
                sn = device.sn if device else None
                new_statuses[addr] = DeviceStatus(
                    address=addr,
                    name=sr.name,
                    status="new",
                    encrypted=bool(sr.encrypted),
                    device_type=device_type,
                    sn=sn,
                )

        self._statuses = new_statuses

    async def _scan(self) -> list[ScanResult]:
        try:
            return await scan_devices(timeout=self._config.scan.timeout)
        except Exception:
            logging.warning("BLE scan failed", exc_info=True)
            return []

    def _start_handlers(self):
        for addr, ds in self._statuses.items():
            if ds.status == "online" and addr not in self._handlers:
                self._spawn_handler(addr, ds)

    def _update_handlers(self):
        online_addresses = {addr for addr, ds in self._statuses.items() if ds.status == "online"}

        for addr in list(self._handlers):
            if addr not in online_addresses:
                task = self._handlers.pop(addr)
                task.cancel()

        for addr in online_addresses:
            if addr not in self._handlers:
                ds = self._statuses[addr]
                self._spawn_handler(addr, ds)

    def _spawn_handler(self, address: str, ds: DeviceStatus):
        device = self._devices.get(address)
        if device is None:
            device = _try_build_device(address, ds.name or address)
            if device is None:
                logging.warning(f"Cannot build device for {ds.name} at {address}, skipping")
                return
            self._devices[address] = device
            sr_device = _try_build_device(address, ds.name or address)
            if sr_device is None:
                logging.warning(f"Cannot build device for {ds.name} at {address}, skipping")
                return

        handler = DeviceHandler(
            address=address,
            device=device,
            interval=5,
            bus=self._bus,
            encrypted=ds.encrypted,
        )
        task = asyncio.create_task(handler.run())
        self._handlers[address] = task


def _try_build_device(address: str, name: str):
    try:
        return build_device(address, name)
    except ValueError:
        logging.debug(f"Unsupported device: {name!r} at {address}")
        return None
