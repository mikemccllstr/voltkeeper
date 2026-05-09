# ABOUTME: BLE scan utilities — service-UUID-based scan, device factory.

import re
import sys

import click
from bleak import BleakScanner

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
_DEVICE_NAME_SN_RE = re.compile(r"^(AC2A|AC60|EP600|EP500|EB3A)(\d+)$")


def _parse_sn(name: str) -> str:
    m = _DEVICE_NAME_SN_RE.match(name.strip())
    if m:
        return m[2]
    return name.replace(":", "").replace("-", "")


async def lookup_device_name(address: str, timeout: float = 5.0) -> str:
    devices = await BleakScanner.discover(
        timeout=timeout,
        service_uuids=[SERVICE_UUID],
        return_adv=True,
    )
    for addr, (device, adv) in devices.items():
        if addr.upper() == address.upper():
            name = (device.name or adv.local_name or "").strip()
            if name:
                return name
    return address


async def scan_devices(timeout: float = 10.0) -> list[tuple[str, str]]:
    click.echo(f"Scanning for Bluetti devices (service {SERVICE_UUID}) ...")
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


async def pick_address_after_scan() -> tuple[str, str]:
    devices = await scan_devices()

    if not devices:
        click.secho("\nNo Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    if len(devices) == 1:
        address, name = devices[0]
        click.echo(f"\nFound 1 device \u2192 auto-selecting: {address} ({name})")
        return address, name

    click.echo(f"\nFound {len(devices)} Bluetti devices:\n")
    for i, (addr, name) in enumerate(devices, 1):
        click.echo(f"  [{click.style(str(i), fg='cyan')}] {click.style(addr, fg='green')}  \u2014  {name}")

    click.echo()
    while True:
        try:
            choice = input(f"Select device (1-{len(devices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            click.echo()
            sys.exit(1)
        click.echo(f"Enter a number between 1 and {len(devices)}.")


def _device_registry() -> dict[str, type]:
    from ..core.devices.ac2a import AC2A

    return {"AC2A": AC2A}


def build_device(address: str, name: str):
    sn = _parse_sn(name)
    prefix_match = _DEVICE_NAME_SN_RE.match(name.strip())
    prefix: str | None = prefix_match[1] if prefix_match else None
    registry = _device_registry()
    cls = registry.get(prefix) if prefix else None
    if cls is None:
        raise ValueError(f"Unsupported device model: {name!r}. Known prefixes: {sorted(registry)}")
    return cls(address, sn)
