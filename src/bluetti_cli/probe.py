# ABOUTME: Active register sweep for Bluetti devices — protocol detection, YAML profile emission.
# ABOUTME: Unit 11 per IMPLEMENTATION_UNITS.md.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .bluetooth import _DEVICE_NAME_SN_RE, _device_registry
from .bluetooth.client import BluetoothClient
from .bluetooth.exc import BadConnectionError, ModbusError
from .core.commands import ReadHoldingRegisters

# ── Protocol detection result ─────────────────────────────────────────


@dataclass
class ProtocolInfo:
    kind: str  # "v1" | "v2" | "unknown"
    version: int | None


# ── Register block tables ─────────────────────────────────────────────

V1_BLOCKS: list[tuple[int, int, str]] = [
    (10, 53, "BASE_REAL_DATA"),
    (22, 2, "MCU_STATUS"),
    (70, 87, "ADDITIONAL_DATA"),
    (91, 10, "BMS_PACK"),
    (130, 27, "THREE_PHASE_DATA"),
    (157, 32, "PV_CHARGE_DATA"),
    (190, 1, "WIFI_SWITCH"),
    (3000, 36, "SETTABLE_DATA"),
    (4997, 3, "BLE_MAC"),
    (5000, 49, "INTERNET_STATUS"),
    (5017, 64, "INTERNET_SETTING"),
    (13603, 8, "IOT_BLE_SERVER_KEY"),
]

V2_BLOCKS: list[tuple[int, int, str]] = [
    (100, 62, "APP_HOME_DATA"),
    (1100, 51, "INV_BASE_INFO"),
    (1200, 70, "INV_PV_INFO"),
    (1300, 31, "INV_GRID_INFO"),
    (1400, 48, "INV_LOAD_INFO"),
    (1500, 30, "INV_INV_INFO"),
    (2000, 54, "INV_BASE_SETTINGS"),
]


# ── Protocol detection ─────────────────────────────────────────────────


async def _detect_protocol(client: BluetoothClient, name: str) -> ProtocolInfo:
    """Determine protocol from registry or dynamic probe.

    1. Registry hit: parse BLE name, look up in registry, read
       ``protocol_version`` — no Modbus round-trip needed.
    2. Dynamic probe: read V1 register 16 (MODBUS_PROTOCOL_VER);
       >=2000 → V2, <2000 → V1.
    3. Fallback: if V1 read fails, try V2 register 1100; if that
       succeeds → V2.
    4. Both fail → unknown.
    """
    # ── Registry shortcut ──
    m = _DEVICE_NAME_SN_RE.match(name.strip())
    if m:
        prefix = m[1]
        registry = _device_registry()
        if prefix in registry:
            # Instantiate just to read protocol_version; no Modbus needed.
            sn = m[2]
            device = registry[prefix]("", sn)
            return ProtocolInfo(
                kind="v2" if device.protocol_version >= 2000 else "v1",
                version=device.protocol_version,
            )

    # ── Dynamic probe ──
    try:
        resp = await client.execute(ReadHoldingRegisters(16, 1))
        ver = int.from_bytes(resp, "big")
        return ProtocolInfo(kind="v2" if ver >= 2000 else "v1", version=ver)
    except (ModbusError, BadConnectionError):
        pass

    try:
        await client.execute(ReadHoldingRegisters(1100, 1))
        return ProtocolInfo(kind="v2", version=None)
    except (ModbusError, BadConnectionError):
        pass

    return ProtocolInfo(kind="unknown", version=None)


# ── Device probe ───────────────────────────────────────────────────────


async def probe_device(address: str, name: str, *, encrypted: bool) -> dict:
    """Connect, sweep register blocks, return a structured profile dict."""
    client = BluetoothClient(address, encrypted=encrypted)
    await client.connect()
    profile: dict = {"address": address, "name": name, "encrypted": encrypted}
    try:
        info = await _detect_protocol(client, name)
        profile["protocol"] = info.kind
        profile["protocol_version"] = info.version
        profile["blocks"] = {}

        blocks = V1_BLOCKS if info.kind == "v1" else V2_BLOCKS if info.kind == "v2" else []
        for block_addr, block_size, block_name in blocks:
            try:
                resp = await client.execute(ReadHoldingRegisters(block_addr, block_size))
                profile["blocks"][block_name] = {
                    "address": block_addr,
                    "size": block_size,
                    "raw_hex": resp.hex(),
                }
            except (ModbusError, BadConnectionError):
                profile["blocks"][block_name] = {"address": block_addr, "error": "no response"}
        return profile
    finally:
        await client.disconnect()


# ── YAML emitter ───────────────────────────────────────────────────────


def emit_yaml(profile: dict, output: str | Path) -> None:
    """Write a profile dict to a YAML file."""
    with open(output, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
