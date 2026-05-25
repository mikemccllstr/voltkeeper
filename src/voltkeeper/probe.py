# ABOUTME: Active register sweep for Bluetti devices — protocol detection, YAML profile emission.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


# ── V1 per-protocolVer block size helpers ─────────────────────────────


def _v1_base_real_data_size(ver: int) -> int:
    if ver <= 0:
        return 53
    if ver < 1017:
        return 53
    if ver <= 1022:
        return 58
    return 59


def _v1_bms_pack_size(ver: int) -> int:
    if ver <= 0:
        return 10
    if ver < 1017:
        return 10
    if ver <= 1021:
        return 115
    return 127


def _v1_settable_data_size(ver: int) -> int:
    if ver <= 0:
        return 36
    if ver < 1016:
        return 36
    if ver < 1019:
        return 62
    if ver < 1021:
        return 67
    if ver < 1023:
        return 82
    if ver < 1026:
        return 90
    return 91


# ── Register block tables ─────────────────────────────────────────────

# V1 blocks include a size function: (address, name, fn(protoVer) → size)
V1_BLOCKS: list[tuple[int, str, Callable[[int], int]]] = [
    (10, "BASE_REAL_DATA", _v1_base_real_data_size),
    (22, "MCU_STATUS", lambda _: 2),
    (70, "ADDITIONAL_DATA", lambda _: 87),
    (91, "BMS_PACK", _v1_bms_pack_size),
    (130, "THREE_PHASE_DATA", lambda _: 27),
    (157, "PV_CHARGE_DATA", lambda _: 32),
    (190, "WIFI_SWITCH", lambda _: 1),
    (3000, "SETTABLE_DATA", _v1_settable_data_size),
    (4997, "BLE_MAC", lambda _: 3),
    (5000, "INTERNET_STATUS", lambda _: 49),
    (5017, "INTERNET_SETTING", lambda _: 64),
    (13603, "IOT_BLE_SERVER_KEY", lambda _: 8),
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
    profile: dict = {"address": address, "name": name, "encrypted": encrypted}
    try:
        await client.connect()
    except Exception:
        # Resilience: unreachable device, BLE adapter down, timeout.
        # Still emit a valid YAML so the human can submit address+flag info.
        profile["protocol"] = "unknown"
        profile["protocol_version"] = None
        profile["blocks"] = {}
        return profile

    try:
        info = await _detect_protocol(client, name)
        profile["protocol"] = info.kind
        profile["protocol_version"] = info.version
        profile["blocks"] = {}

        if info.kind == "v1":
            ver = info.version or 0
            for addr, block_name, size_fn in V1_BLOCKS:
                block_size = size_fn(ver)
                try:
                    resp = await client.execute(ReadHoldingRegisters(addr, block_size))
                    profile["blocks"][block_name] = {
                        "address": addr,
                        "size": block_size,
                        "raw_hex": resp.hex(),
                    }
                except (ModbusError, BadConnectionError):
                    profile["blocks"][block_name] = {"address": addr, "error": "no response"}
        elif info.kind == "v2":
            for addr, block_size, block_name in V2_BLOCKS:
                try:
                    resp = await client.execute(ReadHoldingRegisters(addr, block_size))
                    profile["blocks"][block_name] = {
                        "address": addr,
                        "size": block_size,
                        "raw_hex": resp.hex(),
                    }
                except (ModbusError, BadConnectionError):
                    profile["blocks"][block_name] = {"address": addr, "error": "no response"}
        return profile
    finally:
        await client.disconnect()


# ── YAML emitter ───────────────────────────────────────────────────────


def emit_yaml(profile: dict, output: str | Path) -> None:
    """Write a profile dict to a YAML file."""
    with open(output, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
