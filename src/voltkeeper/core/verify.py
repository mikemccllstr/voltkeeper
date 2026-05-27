# ABOUTME: Six-tier device integration test — field classification, tier runners, report builder.
# ABOUTME: Used by `voltkeeper verify` to validate device model accuracy against real hardware.

from __future__ import annotations

import struct
from dataclasses import dataclass
from dataclasses import field as dc_field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from .commands import ReadHoldingRegisters, WriteSingleRegister
from .devices.bluetti_device import BluettiDevice
from .struct import BoolField, DecimalField, EnumField, UintField

# Global field risk classification.  Fields not listed default to tier 2/3 (automatic).
FIELD_TIERS: dict[str, int] = {
    # Tier 4 — load-affecting
    "ac_output": 4,
    "dc_output": 4,
    "ctrl_grid": 4,
    "ctrl_feed": 4,
    "power_lifting": 4,
    "ac_eco_mode": 4,
    "dc_eco_mode": 4,
    # Tier 5 — mode-changing
    "working_mode": 5,
    "ups_mode": 5,
    # Tier 6 — irreversible
    "factory_reset": 6,
    "system_power": 6,
    "power_off": 6,
}

# Fields excluded from automatic tier 2/3 testing — either no safe default
# exists (system_time, system_timezone) or the register does not support
# read-after-write on known hardware (ja12_enable times out on AC2A).
SKIP_AUTO: frozenset[str] = frozenset({"system_time", "system_timezone", "ja12_enable"})


@dataclass
class ProbeResult:
    wrote: int
    readback: Optional[int]
    result: str  # "accepted" | "rejected" | "no-readback"


@dataclass
class FieldResult:
    status: str  # "pass" | "fail" | "skipped"
    read: Any = None
    wrote: Optional[int] = None
    readback: Optional[int] = None
    match: Optional[bool] = None
    note: Optional[str] = None
    probes: Optional[list[ProbeResult]] = None
    discovered_range: Optional[list[int]] = None
    range_discrepancy: Optional[bool] = None
    restore_failed: bool = False
    last_known_value: Optional[int] = None


@dataclass
class BlockResult:
    status: str  # "pass" | "fail"
    fields_parsed: int = 0
    error: Optional[str] = None


@dataclass
class TierResult:
    tier: int
    status: str  # "pass" | "fail" | "skipped" | "partial"
    reason: Optional[str] = None
    consent: Optional[str] = None
    blocks: dict[str, BlockResult] = dc_field(default_factory=dict)
    fields: dict[str, FieldResult] = dc_field(default_factory=dict)

    @property
    def failure_count(self) -> int:
        return sum(1 for b in self.blocks.values() if b.status == "fail") + sum(
            1 for f in self.fields.values() if f.status == "fail"
        )


# ── Pure helpers ───────────────────────────────────────────────────────────────


def safe_default(device_field: Any) -> int:
    """Return a safe raw uint16 integer to write when no current value is known."""
    if isinstance(device_field, BoolField):
        return 0
    if isinstance(device_field, EnumField):
        return min(m.value for m in device_field.enum)
    if isinstance(device_field, (UintField, DecimalField)):
        if device_field.range is not None:
            return int(device_field.range[0])
    return 0


def _to_raw_int(device_field: Any, parsed_value: Any) -> int:
    """Convert a parsed field value back to the raw uint16 register integer."""
    if isinstance(device_field, DecimalField):
        return int(Decimal(str(parsed_value)) * 10**device_field.scale)
    if isinstance(device_field, BoolField):
        return 1 if parsed_value else 0
    if isinstance(device_field, EnumField):
        if isinstance(parsed_value, Enum):
            return parsed_value.value
        return int(parsed_value)
    return int(parsed_value)


def _serialize(val: Any) -> Any:
    """Convert a parsed field value to a YAML-safe Python scalar."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, Enum):
        return val.name.lower()
    if isinstance(val, Decimal):
        return float(val)
    return val


def _field_range_raw(device_field: Any) -> Optional[tuple[int, int]]:
    """Return (low, high) range as raw uint16 integers, or None if no range declared."""
    if not hasattr(device_field, "range") or device_field.range is None:
        return None
    lo, hi = device_field.range[0], device_field.range[1]
    if isinstance(device_field, DecimalField):
        lo = int(Decimal(str(lo)) * 10**device_field.scale)
        hi = int(Decimal(str(hi)) * 10**device_field.scale)
    return int(lo), int(hi)


def _get_control_field(device: Any, field_name: str) -> Optional[Any]:
    """Return the DeviceField from control_struct matching field_name, or None."""
    return next((f for f in device.control_struct.fields if f.name == field_name), None)


def build_tier_plan(device: Any) -> dict[int, list[str]]:
    """Partition WRITABLE_FIELD_NAMES by risk tier.

    Tiers 2 and 3 operate on the same field list (automatic tiers).
    Fields in SKIP_AUTO are omitted from automatic tiers.
    """
    auto: list[str] = []
    t4: list[str] = []
    t5: list[str] = []
    t6: list[str] = []

    for name in device.WRITABLE_FIELD_NAMES:
        tier = FIELD_TIERS.get(name, 3)
        if tier >= 6:
            t6.append(name)
        elif tier == 5:
            t5.append(name)
        elif tier == 4:
            t4.append(name)
        elif name not in SKIP_AUTO:
            auto.append(name)

    return {2: auto, 3: auto, 4: t4, 5: t5, 6: t6}


# ── BLE helpers ────────────────────────────────────────────────────────────────


async def _read_raw(client: Any, address: int) -> bytes:
    """Execute a single-register read and return the 2 raw payload bytes."""
    return await client.execute(ReadHoldingRegisters(address, 1))


async def read_single_register(client: Any, device: BluettiDevice, address: int) -> tuple[bytes, dict]:
    """Read one register; returns (raw_2_bytes, parsed_dict)."""
    raw = await _read_raw(client, address)
    parsed = device.parse(address, raw)
    return raw, parsed


# ── Tier runners ───────────────────────────────────────────────────────────────


async def run_tier1(client: Any, device: BluettiDevice) -> tuple[TierResult, dict]:
    """Poll all blocks, parse each, record per-block results.

    Returns (TierResult, merged_values_dict).
    """
    result = TierResult(tier=1, status="pass")
    merged: dict = {}

    control_cmds = list(getattr(device, "control_commands", []))
    all_cmds = list(device.polling_commands) + control_cmds

    for cmd in all_cmds:
        addr_key = str(cmd.starting_address)
        try:
            raw = await client.execute(cmd)
            parsed = device.parse(cmd.starting_address, raw)
            merged.update(parsed)
            result.blocks[addr_key] = BlockResult(status="pass", fields_parsed=len(parsed))
        except Exception as exc:
            result.blocks[addr_key] = BlockResult(status="fail", error=str(exc))
            result.status = "fail"

    return result, merged


async def run_tier2(
    client: Any,
    device: BluettiDevice,
    tier1_values: dict,
    fields: list[str],
) -> TierResult:
    """Identity write: for each field, write current value (or safe default), verify roundtrip."""
    result = TierResult(tier=2, status="pass")

    for name in fields:
        device_field = _get_control_field(device, name)
        if device_field is None:
            result.fields[name] = FieldResult(status="skipped", note="not in control_struct")
            continue

        current = tier1_values.get(name)
        note: Optional[str] = None

        if current is None:
            raw_int = safe_default(device_field)
            note = "no status value — used safe default"
        else:
            try:
                raw_int = _to_raw_int(device_field, current)
            except Exception as exc:
                result.fields[name] = FieldResult(
                    status="fail",
                    read=_serialize(current),
                    note=f"could not encode current value: {exc}",
                )
                result.status = "fail"
                continue

        try:
            await client.execute(WriteSingleRegister(device_field.address, raw_int))
        except Exception as exc:
            result.fields[name] = FieldResult(
                status="fail",
                read=_serialize(current),
                wrote=raw_int,
                note=f"write rejected: {exc}",
            )
            result.status = "fail"
            continue

        try:
            raw_back, _ = await read_single_register(client, device, device_field.address)
            readback_int = struct.unpack("!H", raw_back)[0]
        except Exception as exc:
            result.fields[name] = FieldResult(
                status="fail",
                read=_serialize(current),
                wrote=raw_int,
                note=f"readback failed: {exc}",
            )
            result.status = "fail"
            continue

        match = raw_int == readback_int
        result.fields[name] = FieldResult(
            status="pass" if match else "fail",
            read=_serialize(current),
            wrote=raw_int,
            readback=readback_int,
            match=match,
            note=note,
        )
        if not match:
            result.status = "fail"

    return result


async def _probe_restore(client: Any, address: int, original: int) -> bool:
    """Write original value back and verify readback matches. Returns True on success."""
    try:
        await client.execute(WriteSingleRegister(address, original))
        raw = await _read_raw(client, address)
        return struct.unpack("!H", raw)[0] == original
    except Exception:
        return False


async def run_tier3_bool(
    client: Any,
    device_field: Any,
    current_int: int,
) -> FieldResult:
    """Toggle a bool field and restore it."""
    toggle_val = 1 - (current_int & 1)
    probes: list[ProbeResult] = []
    restore_failed = False
    last_known = current_int

    try:
        await client.execute(WriteSingleRegister(device_field.address, toggle_val))
        raw = await _read_raw(client, device_field.address)
        rb = struct.unpack("!H", raw)[0]
        probes.append(
            ProbeResult(
                wrote=toggle_val,
                readback=rb,
                result="accepted" if rb == toggle_val else "no-readback",
            )
        )
        last_known = rb
    except Exception:
        probes.append(ProbeResult(wrote=toggle_val, readback=None, result="rejected"))

    if not await _probe_restore(client, device_field.address, current_int):
        restore_failed = True
    else:
        last_known = current_int

    return FieldResult(
        status="fail" if restore_failed else "pass",
        probes=probes,
        restore_failed=restore_failed,
        last_known_value=last_known if restore_failed else None,
    )


async def run_tier3_enum(
    client: Any,
    device_field: Any,
    current_int: int,
) -> FieldResult:
    """Cycle through all enum members and restore after each."""
    probes: list[ProbeResult] = []
    restore_failed = False
    last_known = current_int

    for member in sorted(device_field.enum, key=lambda m: m.value):
        val = member.value
        try:
            await client.execute(WriteSingleRegister(device_field.address, val))
            raw = await _read_raw(client, device_field.address)
            rb = struct.unpack("!H", raw)[0]
            probes.append(
                ProbeResult(
                    wrote=val,
                    readback=rb,
                    result="accepted" if rb == val else "no-readback",
                )
            )
            last_known = rb
        except Exception:
            probes.append(ProbeResult(wrote=val, readback=None, result="rejected"))

        if val != current_int:
            if not await _probe_restore(client, device_field.address, current_int):
                restore_failed = True
                break
            last_known = current_int

    return FieldResult(
        status="fail" if restore_failed else "pass",
        probes=probes,
        restore_failed=restore_failed,
        last_known_value=last_known if restore_failed else None,
    )


async def run_tier3_numeric(
    client: Any,
    device_field: Any,
    current_int: int,
) -> FieldResult:
    """Probe boundary values for numeric fields, infer discovered range."""
    raw_range = _field_range_raw(device_field)

    if raw_range is not None:
        low, high = raw_range
        sequence = [current_int, low, high, low - 1, high + 1, high + 2, 0, 65535]
    else:
        ci = current_int
        sequence = [ci, 0, 255, 65535, ci + 1, max(0, ci - 1)]

    seen: set[int] = set()
    probes_to_run: list[int] = []
    for v in sequence:
        if 0 <= v <= 65535 and v not in seen:
            seen.add(v)
            probes_to_run.append(v)

    probes: list[ProbeResult] = []
    accepted: list[int] = []
    restore_failed = False
    last_known = current_int

    for probe_val in probes_to_run:
        try:
            await client.execute(WriteSingleRegister(device_field.address, probe_val))
        except Exception:
            probes.append(ProbeResult(wrote=probe_val, readback=None, result="rejected"))
            continue

        try:
            raw = await _read_raw(client, device_field.address)
            rb = struct.unpack("!H", raw)[0]
        except Exception:
            probes.append(ProbeResult(wrote=probe_val, readback=None, result="no-readback"))
            if not await _probe_restore(client, device_field.address, current_int):
                restore_failed = True
                last_known = probe_val
                break
            last_known = current_int
            continue

        if rb == probe_val:
            probes.append(ProbeResult(wrote=probe_val, readback=rb, result="accepted"))
            accepted.append(probe_val)
        else:
            probes.append(ProbeResult(wrote=probe_val, readback=rb, result="no-readback"))
        last_known = rb

        if probe_val != current_int:
            if not await _probe_restore(client, device_field.address, current_int):
                restore_failed = True
                last_known = probe_val
                break
            last_known = current_int

    range_vals = [v for v in accepted if v <= 65534]
    discovered_range = [min(range_vals), max(range_vals)] if range_vals else None

    range_discrepancy: Optional[bool] = None
    if raw_range is not None and discovered_range is not None:
        range_discrepancy = discovered_range != list(raw_range)

    return FieldResult(
        status="fail" if restore_failed else "pass",
        probes=probes,
        discovered_range=discovered_range,
        range_discrepancy=range_discrepancy,
        restore_failed=restore_failed,
        last_known_value=last_known if restore_failed else None,
    )


async def run_tier3(
    client: Any,
    device: BluettiDevice,
    tier1_values: dict,
    fields: list[str],
) -> TierResult:
    """Dispatch probe writes by field type for each automatic field."""
    result = TierResult(tier=3, status="pass")

    for name in fields:
        device_field = _get_control_field(device, name)
        if device_field is None:
            result.fields[name] = FieldResult(status="skipped", note="not in control_struct")
            continue

        current = tier1_values.get(name)
        current_int = _to_raw_int(device_field, current) if current is not None else safe_default(device_field)

        if isinstance(device_field, BoolField):
            fr = await run_tier3_bool(client, device_field, current_int)
        elif isinstance(device_field, EnumField):
            fr = await run_tier3_enum(client, device_field, current_int)
        elif isinstance(device_field, (UintField, DecimalField)):
            fr = await run_tier3_numeric(client, device_field, current_int)
        else:
            fr = FieldResult(
                status="skipped",
                note=f"unsupported field type: {type(device_field).__name__}",
            )

        result.fields[name] = fr
        if fr.status == "fail":
            result.status = "fail"

    return result


async def run_tier_supervised(
    client: Any,
    device: BluettiDevice,
    tier1_values: dict,
    fields: list[str],
    tier_num: int,
    consent: Optional[str] = None,
) -> TierResult:
    """Identity-write for supervised tiers (4/5/6) — same logic as tier 2."""
    t2 = await run_tier2(client, device, tier1_values, fields)
    return TierResult(
        tier=tier_num,
        status=t2.status,
        consent=consent,
        fields=t2.fields,
    )


# ── Report builder ─────────────────────────────────────────────────────────────


_FIRMWARE_FIELD_SUBSTRINGS = ("ver", "version", "firmware", "software")


def _tier_result_to_dict(tr: TierResult) -> dict:
    d: dict = {"status": tr.status}
    if tr.reason:
        d["reason"] = tr.reason
    if tr.consent:
        d["consent"] = tr.consent
    if tr.blocks:
        d["blocks"] = {}
        for k, b in tr.blocks.items():
            bd: dict = {"status": b.status, "fields_parsed": b.fields_parsed}
            if b.error:
                bd["error"] = b.error
            d["blocks"][k] = bd
    if tr.fields is not None:
        d["fields"] = {}
        for name, fr in tr.fields.items():
            fd: dict = {"status": fr.status}
            if fr.read is not None:
                fd["read"] = fr.read
            if fr.wrote is not None:
                fd["wrote"] = fr.wrote
            if fr.readback is not None:
                fd["readback"] = fr.readback
            if fr.match is not None:
                fd["match"] = fr.match
            if fr.note:
                fd["note"] = fr.note
            if fr.probes:
                fd["probes"] = [{"wrote": p.wrote, "readback": p.readback, "result": p.result} for p in fr.probes]
            if fr.discovered_range is not None:
                fd["discovered_range"] = fr.discovered_range
            if fr.range_discrepancy is not None:
                fd["range_discrepancy"] = fr.range_discrepancy
            if fr.restore_failed:
                fd["restore_failed"] = True
            if fr.last_known_value is not None:
                fd["last_known_value"] = fr.last_known_value
            d["fields"][name] = fd
    return d


def build_report(
    device: BluettiDevice,
    sn: str,
    address: str,
    tier_results: list[TierResult],
    tier1_values: dict,
    scrub: bool = True,
    voltkeeper_version: str = "unknown",
) -> dict:
    """Assemble the full report dict ready for YAML serialization."""
    import datetime

    display_sn = "VKTEST000000" if scrub else sn
    display_address = "AA:BB:CC:DD:EE:FF" if scrub else address.upper()

    firmware = {k: v for k, v in tier1_values.items() if any(sub in k.lower() for sub in _FIRMWARE_FIELD_SUBSTRINGS)}

    report: dict = {
        "voltkeeper_version": voltkeeper_version,
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "device": {"model": device.type, "sn": display_sn, "ble_address": display_address},
    }
    if firmware:
        report["device"]["firmware"] = firmware

    for tr in tier_results:
        report[f"tier_{tr.tier}"] = _tier_result_to_dict(tr)

    return report


def write_report(report: dict, path: str) -> None:
    """Serialize report dict to YAML at path."""
    import yaml

    with open(path, "w") as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
