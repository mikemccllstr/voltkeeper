# ABOUTME: Profile validation — parse probe YAML, assess field sanity, report verdicts.

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml

from .bluetooth import _DEVICE_NAME_SN_RE, _device_registry

# ── Field verdiction ───────────────────────────────────────────────────


@dataclass
class FieldVerdict:
    name: str
    value: object
    status: Literal["ok", "suspect", "error"]
    note: str = ""

    def __repr__(self) -> str:
        return f"FieldVerdict(name={self.name!r}, value={self.value!r}, status={self.status!r})"


def assess_field(name: str, value: object, expected_range: tuple[int, int] | None = None) -> FieldVerdict:
    """Classify a parsed field value as ok or suspect.

    Flags stuck-at sentinel values (0, 0xFFFF, 0xFFFFFFFF) and
    values outside an optional *expected_range*.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0 or value == 0xFFFF or value == 0xFFFFFFFF:
            return FieldVerdict(name, value, "suspect", "stuck-at value")
        if expected_range and not (expected_range[0] <= value <= expected_range[1]):
            return FieldVerdict(name, value, "suspect", f"value {value} out of range {expected_range}")
    return FieldVerdict(name, value, "ok")


# ── Profile validation ─────────────────────────────────────────────────


def validate_profile(yaml_path: str) -> list[FieldVerdict]:
    """Load a probe YAML, parse known blocks, return field verdicts.

    Unknown models or blocks without raw_hex are silently skipped.
    Errors during parsing are captured as ``status="error"`` verdicts.
    """
    with open(yaml_path) as f:
        profile = yaml.safe_load(f)

    if not isinstance(profile, dict):
        return []

    name = profile.get("name", "")
    verdicts: list[FieldVerdict] = []

    # ── Determine device class ──
    device = None
    m = _DEVICE_NAME_SN_RE.match((name or "").strip())
    if m:
        prefix = m[1]
        registry = _device_registry()
        if prefix in registry:
            sn = m[2]
            device = registry[prefix]("", sn)

    if device is None:
        return []  # unknown model — no field-level parsing possible

    # ── Parse each block ──
    blocks = profile.get("blocks", {})
    if not isinstance(blocks, dict):
        return []

    for block_name, block_info in blocks.items():
        if not isinstance(block_info, dict):
            continue
        raw_hex = block_info.get("raw_hex")
        addr = block_info.get("address")
        if not raw_hex or addr is None:
            continue

        try:
            data = bytes.fromhex(raw_hex)
        except (ValueError, TypeError):
            continue

        try:
            parsed = device.parse(addr, data)
        except Exception as exc:
            verdicts.append(FieldVerdict(f"{block_name}.parse", str(exc), "error"))
            continue

        for field_name, field_value in parsed.items():
            verdicts.append(assess_field(field_name, field_value))

    return verdicts
