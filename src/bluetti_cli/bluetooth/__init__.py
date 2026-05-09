# ABOUTME: BLE scan utilities — service-UUID-based scan, device factory, encryption classification.

import re
import sys
from dataclasses import dataclass

import click
from bleak import BleakScanner

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
_DEVICE_NAME_SN_RE = re.compile(r"^(AC2A|AC60|EP600|EP500|EB3A)(\d+)$")

PREFIX_PLAINTEXT = bytes.fromhex("424c5545545449")
PREFIX_ENCRYPTED = (
    bytes.fromhex("424c5545545445"),
    bytes.fromhex("424c5545545446"),
)


@dataclass(frozen=True)
class ScanResult:
    address: str
    name: str
    encrypted: bool | None

    def display(self) -> str:
        flag = "encrypted" if self.encrypted else "plaintext" if self.encrypted is False else "unknown"
        return f"{self.address}  —  {self.name}  [{flag}]"


def _parse_sn(name: str) -> str:
    m = _DEVICE_NAME_SN_RE.match(name.strip())
    if m:
        return m[2]
    return name.replace(":", "").replace("-", "")


async def lookup_scan_result(address: str, timeout: float = 5.0) -> ScanResult:
    devices = await BleakScanner.discover(
        timeout=timeout,
        service_uuids=[SERVICE_UUID],
        return_adv=True,
    )
    for addr, (device, adv) in devices.items():
        if addr.upper() == address.upper():
            name = (device.name or adv.local_name or "").strip()
            if not name:
                name = address
            encrypted = _classify(adv)
            return ScanResult(address=address, name=name, encrypted=encrypted)
    return ScanResult(address=address, name=address, encrypted=None)


def _classify(adv) -> bool | None:
    for blob in adv.manufacturer_data.values():
        if blob.startswith(PREFIX_PLAINTEXT):
            return False
        if any(blob.startswith(p) for p in PREFIX_ENCRYPTED):
            return True
    return None


async def scan_devices(timeout: float = 10.0) -> list[ScanResult]:
    click.echo(f"Scanning for Bluetti devices (service {SERVICE_UUID}) ...")
    devices = await BleakScanner.discover(
        timeout=timeout,
        service_uuids=[SERVICE_UUID],
        return_adv=True,
    )

    found: list[ScanResult] = []
    for address, (device, adv) in devices.items():
        name = (device.name or adv.local_name or "").strip()
        if not name:
            name = "(unknown)"
        encrypted = _classify(adv)
        found.append(ScanResult(address=address, name=name, encrypted=encrypted))

    return sorted(found, key=lambda x: x.address)


async def pick_address_after_scan() -> ScanResult:
    devices = await scan_devices()

    if not devices:
        click.secho("\nNo Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    if len(devices) == 1:
        sr = devices[0]
        click.echo(f"\nFound 1 device \u2192 auto-selecting: {sr.display()}")
        return sr

    click.echo(f"\nFound {len(devices)} Bluetti devices:\n")
    for i, sr in enumerate(devices, 1):
        click.echo(f"  [{click.style(str(i), fg='cyan')}] {sr.display()}")

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


def device_registry() -> dict[str, type]:
    return _device_registry()


def is_supported_device_type(prefix: str) -> bool:
    return prefix in _device_registry()


def build_device(address: str, name: str):
    sn = _parse_sn(name)
    prefix_match = _DEVICE_NAME_SN_RE.match(name.strip())
    prefix: str | None = prefix_match[1] if prefix_match else None
    registry = _device_registry()
    cls = registry.get(prefix) if prefix else None
    if cls is None:
        raise ValueError(f"Unsupported device model: {name!r}. Known prefixes: {sorted(registry)}")
    return cls(address, sn)
