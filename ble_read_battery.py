# ABOUTME: BLE client for Bluetti AC2A — reads battery SOC and pack data.
# ABOUTME: Uses plain Modbus RTU over BLE (no encryption; AC2A is not ESP32Encrypted).
# ABOUTME: If no MAC address is given, scans for local Bluetti devices automatically.
#!/usr/bin/env python3
"""
Connect to a Bluetti AC2A over BLE and read battery SOC.

Usage:
    uv run ble_read_battery.py                           # scan for devices
    uv run ble_read_battery.py AA:BB:CC:DD:EE:FF         # connect directly

Dependencies: bleak
    pip install bleak
"""

import asyncio
import sys
import struct
from bleak import BleakClient, BleakScanner

# ── BLE GATT Identifiers ────────────────────────────────────────────────
SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
WRITE_UUID   = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000ff01-0000-1000-8000-00805f9b34fb"


# ═══════════════════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════════════════

def crc16_modbus(data: bytes) -> bytes:
    """CRC-16-Modbus (poly 0xA001, init 0xFFFF).
    Returns 2 bytes in little-endian order (low, high)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b & 0xFF
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


# ═══════════════════════════════════════════════════════════════════════
#  BLE Connection & Protocol
# ═══════════════════════════════════════════════════════════════════════

class BluettiAC2A:
    def __init__(self, address: str):
        self.address = address
        self.client = None  # BleakClient
        self._notifications = asyncio.Queue()

    def _on_notification(self, _sender, data: bytes):
        print(f"  [NOTIFY] received {len(data)} bytes: {data.hex()}")
        self._notifications.put_nowait(data)

    async def connect(self) -> None:
        print(f"Connecting to {self.address} …")
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=15.0)
        print("BLE connected.")

        await self.client.start_notify(NOTIFY_UUID, self._on_notification)
        print("Session established.\n")

    async def read_home_data(self) -> dict:
        """Read home data (register 100, 6 registers) and parse."""
        return await self._read_modbus_register(100, 6)

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    async def _read_modbus_register(self, addr: int, count: int) -> dict:
        """Send a plain Modbus RTU read request and parse the response."""
        frame = b"\x01\x03" + struct.pack(">H", addr) + struct.pack(">H", count)
        frame += crc16_modbus(frame)

        await self.client.write_gatt_char(WRITE_UUID, frame, response=False)

        resp = await asyncio.wait_for(self._notifications.get(), timeout=15.0)
        resp_bytes = bytes(resp)

        # Modbus response: [slave][func][byte_count][data…][crc]
        func = resp_bytes[1]
        if func & 0x80:
            raise RuntimeError(
                f"Modbus error: func=0x{func:02X} code=0x{resp_bytes[2]:02X}"
            )

        byte_count = resp_bytes[2]
        data = resp_bytes[3 : 3 + byte_count]

        return self._parse_home_data(data)

    @staticmethod
    def _parse_home_data(data: bytes) -> dict:
        """Parse V2 'APP_HOME_DATA' payload.
        Field layout mirrors ProtocolParserV2.parseHomeData()."""
        return {
            "packTotalVoltage":   (data[0]  * 256 + data[1])  / 10.0,
            "packTotalCurrent":   (data[2]  * 256 + data[3])  / 10.0,
            "packTotalSoc":        data[4]  * 256 + data[5],           # 0‑100 %
            "packChargingStatus":  data[6]  * 256 + data[7],
            "packChgFullTime":     data[8]  * 256 + data[9],
            "packDsgEmptyTime":    data[10] * 256 + data[11],
        }


# ═══════════════════════════════════════════════════════════════════════
#  BLE Device Discovery
# ═══════════════════════════════════════════════════════════════════════

async def scan_for_bluetti(timeout: float = 10.0) -> list[tuple[str, str]]:
    """Scan for Bluetti devices advertising the GATT service UUID.

    Returns a list of (address, name) tuples.
    """
    print(f"Scanning for Bluetti devices (service {SERVICE_UUID}) …")
    devices = await BleakScanner.discover(
        timeout=timeout,
        service_uuids=[SERVICE_UUID],
        return_adv=True,
    )

    found: list[tuple[str, str]] = []
    for address, (device, adv) in devices.items():
        name = (device.name or adv.local_name or "").strip()
        if not name:
            name = "(unknown)"
        found.append((address, name))

    return sorted(found, key=lambda x: x[0])


async def pick_address() -> str:
    """Scan for Bluetti devices and let the user pick one.

    Returns the selected MAC address, or exits if none found.
    """
    devices = await scan_for_bluetti()

    if not devices:
        print("\nNo Bluetti devices found.")
        print("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    if len(devices) == 1:
        address, name = devices[0]
        print(f"\nFound 1 device → auto-selecting: {address} ({name})")
        return address

    print(f"\nFound {len(devices)} Bluetti devices:\n")
    for i, (addr, name) in enumerate(devices, 1):
        print(f"  [{i}] {addr}  —  {name}")

    print()
    while True:
        try:
            choice = input(f"Select device (1-{len(devices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
        except (ValueError, EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        print(f"Enter a number between 1 and {len(devices)}.")


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

async def main():
    if len(sys.argv) >= 2:
        address = sys.argv[1].upper()
    else:
        address = await pick_address()
        script = sys.argv[0] if "/" in sys.argv[0] else f"./{sys.argv[0]}"
        print(f"\nTip: next time run directly with:")
        print(f"  uv run {script} {address}")

    device = BluettiAC2A(address)

    try:
        await device.connect()
        home = await device.read_home_data()

        print("─" * 44)
        print(f"  Battery SOC:       {home['packTotalSoc']:>5} %")
        print(f"  Pack Voltage:      {home['packTotalVoltage']:>5.1f} V")
        print(f"  Pack Current:      {home['packTotalCurrent']:>5.1f} A")
        print(f"  Charging Status:   {home['packChargingStatus']:>5}")
        print(f"  Time to Full:      {home['packChgFullTime']:>5} min")
        print(f"  Time to Empty:     {home['packDsgEmptyTime']:>5} min")
        print("─" * 44)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        print(f"\nError: {exc}")
        raise
    finally:
        await device.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
