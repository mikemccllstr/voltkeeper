# ABOUTME: CLI tool for Bluetti power stations — scan, connect, and read data over BLE.
# ABOUTME: Uses plain Modbus RTU over BLE (no encryption; AC2A is not ESP32Encrypted).
# ABOUTME: Built with click for proper CLI affordances (help, version, subcommands).
#!/usr/bin/env python3
"""
CLI tool for Bluetti power stations over BLE.

Scan for nearby devices, connect, and read battery SOC and pack data.
"""

import asyncio
import struct
import sys

import click
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

    Returns 2 bytes in little-endian order (low, high).
    """
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
        self._notifications.put_nowait(data)

    async def connect(self) -> None:
        click.echo(f"Connecting to {self.address} …")
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=15.0)
        click.echo("BLE connected.")

        await self.client.start_notify(NOTIFY_UUID, self._on_notification)
        click.echo("Session established.\n")

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
            "packTotalSoc":        data[4]  * 256 + data[5],
            "packChargingStatus":  data[6]  * 256 + data[7],
            "packChgFullTime":     data[8]  * 256 + data[9],
            "packDsgEmptyTime":    data[10] * 256 + data[11],
        }


# ═══════════════════════════════════════════════════════════════════════
#  BLE Device Discovery
# ═══════════════════════════════════════════════════════════════════════

async def _scan_for_bluetti(timeout: float = 10.0) -> list[tuple[str, str]]:
    """Scan for Bluetti devices advertising the GATT service UUID.

    Returns a list of (address, name) tuples.
    """
    click.echo(f"Scanning for Bluetti devices (service {SERVICE_UUID}) …")
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


async def _pick_address_after_scan() -> str:
    """Scan for devices and let the user pick one interactively.

    Returns the selected MAC address. Exits if none found.
    """
    devices = await _scan_for_bluetti()

    if not devices:
        click.secho("\nNo Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    if len(devices) == 1:
        address, name = devices[0]
        click.echo(f"\nFound 1 device → auto-selecting: {address} ({name})")
        return address

    click.echo(f"\nFound {len(devices)} Bluetti devices:\n")
    for i, (addr, name) in enumerate(devices, 1):
        click.echo(f"  [{click.style(str(i), fg='cyan')}] "
                   f"{click.style(addr, fg='green')}  —  {name}")

    click.echo()
    while True:
        try:
            choice = input(f"Select device (1-{len(devices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
        except (ValueError, EOFError, KeyboardInterrupt):
            click.echo()
            sys.exit(1)
        click.echo(f"Enter a number between 1 and {len(devices)}.")


# ═══════════════════════════════════════════════════════════════════════
#  Output Formatting
# ═══════════════════════════════════════════════════════════════════════

def _print_status(home: dict) -> None:
    """Print battery status in a formatted table."""
    sep = "─" * 44
    click.echo(sep)
    click.echo(f"  Battery SOC:       {home['packTotalSoc']:>5.0f} %")
    click.echo(f"  Pack Voltage:      {home['packTotalVoltage']:>5.1f} V")
    click.echo(f"  Pack Current:      {home['packTotalCurrent']:>5.1f} A")
    click.echo(f"  Charging Status:   {home['packChargingStatus']:>5.0f}")
    click.echo(f"  Time to Full:      {home['packChgFullTime']:>5.0f} min")
    click.echo(f"  Time to Empty:     {home['packDsgEmptyTime']:>5.0f} min")
    click.echo(sep)


# ═══════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════

@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(
    version="0.1.0",
    prog_name="bluetti-cli",
    message="%(prog)s %(version)s",
)
@click.pass_context
def cli(ctx: click.Context):
    """Bluetti power station CLI — scan, connect, and read data over BLE.

    \b
    Examples:
      bluetti-cli status              # auto-scan and read battery data
      bluetti-cli status AA:BB:CC:DD:EE:FF  # connect directly
      bluetti-cli scan                # scan for nearby devices
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


@cli.command()
@click.option(
    "--timeout", "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds.",
)
def scan(timeout):
    """Scan for nearby Bluetti devices and display their MAC addresses."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        devices = loop.run_until_complete(_scan_for_bluetti(timeout=timeout))
    finally:
        loop.close()

    if not devices:
        click.secho("No Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    label = click.style(str(len(devices)), fg="cyan", bold=True)
    click.echo(f"\n{label} device(s) found:\n")
    for addr, name in devices:
        click.echo(f"  {click.style(addr, fg='green')}  —  {name}")

    click.echo()
    if len(devices) == 1:
        click.echo("To read data from this device:")
        click.echo(f"  {click.style(f'bluetti-cli status {devices[0][0]}', bold=True)}")
    else:
        click.echo("To read data from a specific device:")
        for addr, _ in devices:
            cmd = click.style(f"bluetti-cli status {addr}", bold=True)
            click.echo(f"  {cmd}")


@cli.command()
@click.argument("address", required=False, default=None)
@click.option(
    "--timeout", "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds (only used when ADDRESS is not provided).",
)
def status(address, timeout):
    """Read battery SOC and pack data from a Bluetti device.

    If ADDRESS is not provided, scans for nearby Bluetti devices and
    lets you pick one interactively.
    """
    if not address:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            address = loop.run_until_complete(_pick_address_after_scan())
        finally:
            loop.close()
        cmd = click.style(f"bluetti-cli status {address}", bold=True)
        click.echo(f"\nTip: next time, run directly with:\n  {cmd}")
    else:
        address = address.upper()

    device = BluettiAC2A(address)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(device.connect())
            home = loop.run_until_complete(device.read_home_data())
        finally:
            loop.close()
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        click.secho(f"\nError: {exc}", fg="red")
        sys.exit(1)

    _print_status(home)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(device.disconnect())
    finally:
        loop.close()
    click.echo("Disconnected.")


if __name__ == "__main__":
    cli()
