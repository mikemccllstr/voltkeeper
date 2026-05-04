# ABOUTME: BLE client for Bluetti devices — connect, execute Modbus commands, disconnect. No auto-reconnect.

import asyncio

from bleak import BleakClient, BleakError

from ..core.commands import DeviceCommand
from .exc import BadConnectionError, ModbusError, ParseError

RESPONSE_TIMEOUT = 5
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
MAX_RETRIES = 5


class BluetoothClient:
    def __init__(self, address: str):
        self.address = address
        self.client: BleakClient = None
        self._notify_response = bytearray()
        self._notify_future: asyncio.Future = None
        self._current_cmd: DeviceCommand = None

    async def connect(self, timeout: float = 15.0) -> None:
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=timeout)
        await self.client.start_notify(NOTIFY_UUID, self._on_notification)

    @property
    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_connected

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except BleakError:
                pass

    async def execute(self, cmd: DeviceCommand) -> bytes:
        loop = asyncio.get_running_loop()
        retries = 0

        while True:
            self._current_cmd = cmd
            self._notify_future = loop.create_future()
            self._notify_response = bytearray()

            try:
                await self.client.write_gatt_char(
                    WRITE_UUID, bytes(cmd), response=False
                )
                resp = await asyncio.wait_for(
                    self._notify_future, timeout=RESPONSE_TIMEOUT
                )
            except ParseError:
                retries += 1
                if retries >= MAX_RETRIES:
                    raise BadConnectionError(f"Too many retries on {cmd}")
                continue
            except asyncio.TimeoutError:
                retries += 1
                if retries >= MAX_RETRIES:
                    raise BadConnectionError(f"Timeout on {cmd} after {MAX_RETRIES} retries")
                continue

            if cmd.is_exception_response(resp):
                raise ModbusError(f"Modbus exception code: {resp[2]}")
            return cmd.parse_response(resp)

    async def perform_nowait(self, cmd: DeviceCommand) -> None:
        await self.execute(cmd)

    def _on_notification(self, _sender: int, data: bytearray) -> None:
        if not self._notify_future or self._notify_future.done():
            return

        if data == b"AT+NAME?\r" or data == b"AT+ADV?\r":
            self._notify_future.set_exception(
                BadConnectionError("Got AT+ notification")
            )
            return

        self._notify_response.extend(data)

        if len(self._notify_response) == self._current_cmd.response_size():
            if self._current_cmd.is_valid_response(self._notify_response):
                self._notify_future.set_result(bytes(self._notify_response))
            else:
                self._notify_future.set_exception(ParseError("CRC check failed"))
