# ABOUTME: DeviceHandler — persistent BLE polling loop that publishes parsed data to EventBus.

import asyncio
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Dict

from bleak import BleakError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .bluetooth.client import BluetoothClient
from .bluetooth.exc import BadConnectionError, ModbusError, ParseError
from .bus import CommandMessage, EventBus, ParserMessage
from .core.devices.bluetti_device import BluettiDevice
from .core.commands import ReadHoldingRegisters


class SourceChangeWatcher:
    """Watches a directory tree for .py file changes via watchdog/inotify."""

    def __init__(self, watch_path: Path):
        self.changed = threading.Event()
        self._observer = Observer()
        self._observer.schedule(
            _PyFileHandler(self.changed), str(watch_path), recursive=True,
        )

    def start(self):
        self._observer.start()

    def stop(self):
        self._observer.stop()
        self._observer.join()


class _PyFileHandler(FileSystemEventHandler):
    def __init__(self, event: threading.Event):
        self._event = event

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            self._event.set()


async def _watch_source_changes(watcher: SourceChangeWatcher):
    """Poll the threading.Event; exit cleanly when source code changes."""
    while not watcher.changed.is_set():
        await asyncio.sleep(1)
    logging.info("Source code changed — exiting so systemd restarts with new code")
    sys.exit(0)


class DeviceHandler:
    def __init__(self, address: str, device: BluettiDevice, interval: int, bus: EventBus):
        self.address = address
        self.device = device
        self.interval = interval
        self.bus = bus
        self.client = BluetoothClient(address)

    async def run(self):
        loop = asyncio.get_running_loop()
        self.bus.add_command_listener(self.handle_command)

        try:
            while True:
                if not self.client.is_connected:
                    try:
                        await self.client.connect()
                        logging.info(f"BLE connected to {self.address}")
                    except (BleakError, asyncio.TimeoutError):
                        logging.info("BLE connect failed, retrying in 5s...")
                        await asyncio.sleep(5)
                        continue

                try:
                    await self._poll_once()
                except (BleakError, BadConnectionError):
                    logging.warning("BLE connection lost, reconnecting...")
                    await self.client.disconnect()
                    await asyncio.sleep(5)
                    continue

                if self.interval > 0:
                    await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            logging.info("Device handler shutting down...")
            await self.client.disconnect()
            raise

    async def handle_command(self, msg: CommandMessage):
        if msg.device is not self.device:
            return
        logging.debug(f"Performing command {msg.device}: {msg.command}")
        await self.client.perform_nowait(msg.command)

    async def _poll_once(self):
        start_time = time.monotonic()

        for command in self.device.polling_commands:
            try:
                response = await self.client.execute(command)
                parsed = self.device.parse(command.starting_address, response)
                await self.bus.put(ParserMessage(self.device, parsed))
            except ParseError:
                logging.debug("Got a parse exception...")
            except ModbusError as err:
                logging.debug(f"Modbus error for {command}: {err}")
            except (BadConnectionError, BleakError) as err:
                logging.debug(f"Connection error: {err}")
                raise

        elapsed = time.monotonic() - start_time
        if self.interval > 0 and self.interval > elapsed:
            await asyncio.sleep(self.interval - elapsed)
