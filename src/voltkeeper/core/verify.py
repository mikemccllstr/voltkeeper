# ABOUTME: Six-tier device integration test — field classification, tier runners, report builder.
# ABOUTME: Used by `voltkeeper verify` to validate device model accuracy against real hardware.

from __future__ import annotations

import datetime
import os
import struct
from dataclasses import dataclass
from dataclasses import field as dc_field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from .commands import ReadHoldingRegisters, TlvReadHoldingRegisters, WriteSingleRegister
from .devices.bluetti_device import BluettiDevice
from .devices.v2_base import IOT_BASE_INFO
from .struct import BcdSerialField, BoolField, DecimalField, DeviceStruct, EnumField, Uint8Field, UintField
from .tlv import TlvParser

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
# exists (system_time, system_timezone), the register does not support
# read-after-write on known hardware (ja12_enable times out on AC2A), or the
# register uses write-only/toggle semantics (ctrl_led).
SKIP_AUTO: frozenset[str] = frozenset({"system_time", "system_timezone", "ja12_enable", "ctrl_led"})


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
    current_value: Optional[int] = None
    probes_count: Optional[int] = None
    probed_range: Optional[list[int]] = None
    probe_cap_hit: Optional[bool] = None
    declared_range: Optional[list[int]] = None
    in_range_rejected: Optional[list[int]] = None


@dataclass
class BlockResult:
    status: str  # "pass" | "fail"
    fields_parsed: int = 0
    error: Optional[str] = None
    raw: Optional[str] = None
    # True when raw holds an unsplittable TLV bundle rather than this block's
    # own payload: block offsets don't apply, so scrubbing drops it and the
    # report keys it as raw_bundle.
    raw_is_bundle: bool = False


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
        if isinstance(cmd, TlvReadHoldingRegisters):
            try:
                raw = await client.execute(cmd)
            except Exception as exc:
                for start_addr, _ in cmd.sections:
                    result.blocks[str(start_addr)] = BlockResult(status="fail", error=str(exc))
                result.status = "fail"
                continue
            try:
                items = TlvParser.parse(raw)
            except Exception as exc:
                # Bundle bytes can't be split into blocks, so they can't be
                # offset-scrubbed; raw_is_bundle tells the scrubber to drop
                # them and the report to key them as raw_bundle.
                for start_addr, _ in cmd.sections:
                    result.blocks[str(start_addr)] = BlockResult(
                        status="fail", error=str(exc), raw=raw.hex(), raw_is_bundle=True
                    )
                result.status = "fail"
                continue
            for item in items:
                addr_key = str(item.reg_addr)
                try:
                    parsed = device.parse(item.reg_addr, item.value)
                    merged.update(parsed)
                    result.blocks[addr_key] = BlockResult(
                        status="pass", fields_parsed=len(parsed), raw=item.value.hex()
                    )
                except Exception as exc:
                    result.blocks[addr_key] = BlockResult(status="fail", error=str(exc), raw=item.value.hex())
                    result.status = "fail"
        else:
            addr_key = str(cmd.starting_address)
            payload: Optional[bytes] = None
            try:
                payload = await client.execute(cmd)
                parsed = device.parse(cmd.starting_address, payload)
                merged.update(parsed)
                result.blocks[addr_key] = BlockResult(status="pass", fields_parsed=len(parsed), raw=payload.hex())
            except Exception as exc:
                result.blocks[addr_key] = BlockResult(
                    status="fail", error=str(exc), raw=payload.hex() if payload is not None else None
                )
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
    """Exhaustive 0–255 sweep for numeric fields with pre/in/post-range state machine."""
    raw_range = _field_range_raw(device_field)
    declared_range = list(raw_range) if raw_range is not None else None

    accepted: list[int] = []
    restore_failed = False
    last_known = current_int
    probes_count = 0
    last_probed = 0

    # State machine: "pre" → "in" → "post"
    zone = "pre"
    consecutive_post_rejections = 0

    for probe_val in range(256):
        last_probed = probe_val

        # Write the probe value
        try:
            await client.execute(WriteSingleRegister(device_field.address, probe_val))
        except Exception:
            # Exception counts as rejection; treat as readback == current_int for restore logic
            probes_count += 1
            if zone == "in":
                zone = "post"
                consecutive_post_rejections = 1
            elif zone == "post":
                consecutive_post_rejections += 1
                if consecutive_post_rejections >= 2:
                    break
            continue

        # Read back
        try:
            raw = await _read_raw(client, device_field.address)
            rb = struct.unpack("!H", raw)[0]
        except Exception:
            probes_count += 1
            # Unknown state — must restore
            if not await _probe_restore(client, device_field.address, current_int):
                restore_failed = True
                last_known = probe_val
                break
            last_known = current_int
            if zone == "in":
                zone = "post"
                consecutive_post_rejections = 1
            elif zone == "post":
                consecutive_post_rejections += 1
                if consecutive_post_rejections >= 2:
                    break
            continue

        probes_count += 1

        if rb == probe_val:
            accepted.append(probe_val)
            last_known = rb
            zone = "in"
            consecutive_post_rejections = 0
            # Restore: skip if readback already equals original
            if rb != current_int:
                if not await _probe_restore(client, device_field.address, current_int):
                    restore_failed = True
                    last_known = probe_val
                    break
                last_known = current_int
        else:
            # Rejected
            last_known = rb
            if zone == "in":
                zone = "post"
                consecutive_post_rejections = 1
            elif zone == "post":
                consecutive_post_rejections += 1
                if consecutive_post_rejections >= 2:
                    break
            # Restore optimisation: skip if readback already equals original
            if rb != current_int:
                if not await _probe_restore(client, device_field.address, current_int):
                    restore_failed = True
                    last_known = probe_val
                    break
                last_known = current_int

    probed_range = [0, last_probed]
    probe_cap_hit = last_probed == 255 and zone == "in" and not restore_failed

    discovered_range = [min(accepted), max(accepted)] if accepted else None

    range_discrepancy: Optional[bool] = None
    if declared_range is not None and discovered_range is not None:
        range_discrepancy = discovered_range != declared_range

    in_range_rejected: list[int] = []
    if raw_range is not None:
        lo, hi = raw_range
        in_range_rejected = [v for v in range(lo, hi + 1) if v not in accepted and v <= last_probed]

    return FieldResult(
        status="fail" if restore_failed else "pass",
        discovered_range=discovered_range,
        range_discrepancy=range_discrepancy,
        restore_failed=restore_failed,
        last_known_value=last_known if restore_failed else None,
        current_value=current_int,
        probes_count=probes_count,
        probed_range=probed_range,
        probe_cap_hit=probe_cap_hit,
        declared_range=declared_range,
        in_range_rejected=in_range_rejected if in_range_rejected else None,
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
        elif isinstance(device_field, (UintField, DecimalField, Uint8Field)):
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

# Fixed byte offsets of identifying data in the IOT_BASE_INFO block, per
# _parse_iot_info. These are not struct fields, so they can't be derived
# the way SN fields are.
# NODE_INFO (21000) payloads nest pack blocks (with pack serials) inside a
# TLV structure and are NOT scrubbed here; no current device polls it
# (has_sub_devices is False everywhere). Revisit when pack devices land.
_IOT_SCRUB_RANGES: list[tuple[int, int]] = [
    (12, 8),  # iot_sn
    (40, 4),  # wifi_ip
    (44, 4),  # wifi_gateway
    (48, 4),  # wifi_mask
    (54, 6),  # wifi_mac
    (60, 6),  # ble_mac
]


def _device_bcd_sn_fields(device: BluettiDevice) -> list[BcdSerialField]:
    """Collect BCD serial-number fields from all of the device's structs."""
    fields: list[BcdSerialField] = []
    for attr in vars(device).values():
        if isinstance(attr, DeviceStruct):
            fields.extend(f for f in attr.fields if isinstance(f, BcdSerialField))
    return fields


def _scrub_block_raw(hex_str: str, block_addr: int, sn_fields: list[BcdSerialField]) -> str:
    """Zero sensitive bytes in one block's raw hex.

    Any BCD SN field whose registers fall inside the block's read window
    [block_addr, block_addr + payload_regs) is zeroed at its offset within
    the payload; IOT_BASE_INFO additionally gets its fixed MAC/IP/SN ranges.
    """
    data = bytearray(bytes.fromhex(hex_str))
    reg_count = len(data) // 2
    for field in sn_fields:
        if block_addr <= field.address < block_addr + reg_count:
            offset = 2 * (field.address - block_addr)
            end = min(offset + 2 * field.size, len(data))
            data[offset:end] = b"\x00" * (end - offset)
    if block_addr == IOT_BASE_INFO:
        for offset, size in _IOT_SCRUB_RANGES:
            end = min(offset + size, len(data))
            if offset < end:
                data[offset:end] = b"\x00" * (end - offset)
    return bytes(data).hex()


def _scrub_tier_results_raw(device: BluettiDevice, tier_results: list[TierResult]) -> None:
    """Mutate tier_results in-place: zero sensitive bytes in block raw hex strings."""
    sn_fields = _device_bcd_sn_fields(device)
    for tr in tier_results:
        for addr_key, block in tr.blocks.items():
            if block.raw is None:
                continue
            if block.raw_is_bundle:
                # Bundle-shaped bytes can't be offset-scrubbed safely; drop.
                block.raw = None
                continue
            try:
                block_addr = int(addr_key)
            except ValueError:
                continue
            block.raw = _scrub_block_raw(block.raw, block_addr, sn_fields)


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
            if b.raw is not None:
                bd["raw_bundle" if b.raw_is_bundle else "raw"] = b.raw
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
            if fr.current_value is not None:
                fd["current_value"] = fr.current_value
            if fr.probes_count is not None:
                fd["probes_count"] = fr.probes_count
            if fr.probed_range is not None:
                fd["probed_range"] = fr.probed_range
            if fr.probe_cap_hit is not None:
                fd["probe_cap_hit"] = fr.probe_cap_hit
            if fr.declared_range is not None:
                fd["declared_range"] = fr.declared_range
            if fr.in_range_rejected:
                fd["in_range_rejected"] = fr.in_range_rejected
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

    if scrub:
        _scrub_tier_results_raw(device, tier_results)

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


def _unique_path(path: str) -> str:
    """Return path with _v<N> inserted before suffix if path already exists.

    Chooses the smallest N ≥ 2 that yields a non-existent path.
    Non-existent paths are returned unchanged.
    """
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while True:
        candidate = f"{base}_v{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _build_default_output_path(
    device_type: str,
    ground_truth: bool = False,
    now: "datetime.datetime | None" = None,
) -> str:
    """Build the default report path from mode, model, and UTC timestamp."""
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    else:
        now = now.astimezone(datetime.timezone.utc)
    mode = "verify-ground-truth" if ground_truth else "verify"
    timestamp = now.strftime("%Y-%m-%dT%H%MZ")
    return f"hardware-data/{mode}_{device_type}_{timestamp}.yaml"


def write_report(report: dict, path: str) -> str:
    """Serialize report dict to YAML at path, never overwriting an existing file.

    Returns the actual path written (may differ from `path` when a unique suffix was added).
    """
    import yaml

    path = _unique_path(path)
    with open(path, "w") as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path
