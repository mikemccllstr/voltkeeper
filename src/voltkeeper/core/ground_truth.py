# ABOUTME: Ground-truth verification — operator-observed device state vs. parsed register values.
# ABOUTME: Used by `voltkeeper verify --ground-truth` to validate field interpretation against hardware.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class ObservationCheck:
    """A single ground-truth observation of the device screen or physical setup."""

    field: str
    prompt: str
    source: str  # "device_screen" | "multimeter" | "app_screenshot"
    status: str = "pending"  # "match" | "mismatch" | "skipped" | "unanchored"
    observation: Any = None
    parsed: Any = None
    raw_ref: Optional[str] = None  # block address key, e.g. "100"
    inferred_scale: Optional[str] = None  # e.g. "÷10"
    note: Optional[str] = None


@dataclass
class ActuateCheck:
    """An actuate-and-confirm check: write a setting, ask operator to confirm."""

    field: str
    prompt: str = ""
    wrote: Any = None
    wrote_raw: int | None = None  # the raw uint16 value to write — set at build time
    readback: Any = None
    device_confirmed: Optional[bool] = None
    confirm_response: Optional[str] = None  # None=skip, "yes", "no", "unsure"
    note: Optional[str] = None


@dataclass
class InducedCheck:
    """An induced-condition check with alarm register capture."""

    condition: str
    alarm_bits: Optional[list[str]] = None  # alarm.*/fault.* keys from parsed HOME
    raw_hex: Optional[str] = None
    device_indicator: Optional[str] = None
    status: str = "pending"  # "captured" | "skipped"
    note: Optional[str] = None


@dataclass
class GroundTruthResult:
    """Container for all ground-truth results from a session."""

    observations: list[ObservationCheck] = field(default_factory=list)
    actuations: list[ActuateCheck] = field(default_factory=list)
    induced_checks: list[InducedCheck] = field(default_factory=list)
    categories: dict[str, str] = field(default_factory=dict)


# ── Observation definitions ────────────────────────────────────────────────────


@dataclass
class ObservationDef:
    """Definition of a single observation to prompt for."""

    id: str
    prompt: str
    field_names: list[str]
    aggregate: str  # "first" | "sum" | "sum_abs"
    source: str  # "device_screen" | "multimeter_or_app"
    tolerance_type: str  # "soc" | "watts" | "voltage" | "frequency" | "firmware_version" | "exact"
    model_filter: Optional[str] = None  # Only applicable to this specific model name


CORE_OBSERVATION_DEFS: list[ObservationDef] = [
    ObservationDef(
        "soc",
        "State of Charge (%) shown on the Bluetti unit's main screen (digits + ring indicator)",
        ["packTotalSoc"],
        "first",
        "device_screen",
        "soc",
    ),
    ObservationDef(
        "output_watts",
        "Total OUTPUT watts shown on the Bluetti unit's main screen",
        ["totalACPower", "totalDCPower"],
        "sum_abs",
        "device_screen",
        "watts",
    ),
    ObservationDef(
        "input_watts",
        "Total INPUT watts shown on the Bluetti unit's main screen",
        ["totalGridPower", "totalPVPower"],
        "sum_abs",
        "device_screen",
        "watts",
    ),
    ObservationDef(
        "ac_output_state",
        "AC output state on the Bluetti unit's main screen — look for the AC icon (on or off)",
        ["ac_output"],
        "first",
        "device_screen",
        "exact",
    ),
    ObservationDef(
        "dc_output_state",
        "DC output state on the Bluetti unit's main screen — look for the DC icon (on or off)",
        ["dc_output"],
        "first",
        "device_screen",
        "exact",
    ),
    ObservationDef(
        "ac_output_frequency",
        "AC output frequency on the Bluetti unit's main screen (50 Hz or 60 Hz indicator)",
        ["frequency"],
        "first",
        "device_screen",
        "frequency",
    ),
    ObservationDef(
        "charging_mode",
        "Charging mode shown on the Bluetti unit: Turbo icon on the main screen, "
        "or full mode on settings page P03 (Settings Mode page)",
        ["charging_mode"],
        "first",
        "device_screen",
        "exact",
    ),
    ObservationDef(
        "firmware_display",
        "The app's device-info page lists several component versions "
        '(ARM, DSP, BMS, IoT). Report the ARM value, shown as e.g. "2186.14"',
        ["arm_version"],
        "first",
        "device_screen",
        "firmware_version",
        model_filter="EL100V2",
    ),
    ObservationDef(
        "ac_output_voltage",
        "AC output voltage (V) — use a multimeter or a pre/post-session app screenshot",
        ["acPhase[0].voltage"],
        "first",
        "multimeter",
        "voltage",
    ),
    ObservationDef(
        "grid_voltage",
        "Grid voltage (V) — use a multimeter or a pre/post-session app screenshot",
        ["gridPhase[0].voltage"],
        "first",
        "multimeter",
        "voltage",
    ),
    ObservationDef(
        "pack_voltage",
        "Pack voltage (V) — use a multimeter or a pre/post-session app screenshot",
        ["packTotalVoltage"],
        "first",
        "multimeter",
        "voltage",
    ),
]

CORE_OBS_MAP: dict[str, ObservationDef] = {d.id: d for d in CORE_OBSERVATION_DEFS}


# ── Value resolution ──────────────────────────────────────────────────────────


def resolve_observation_value(tier1_values: dict, obs_def: ObservationDef) -> Optional[Any]:
    """Resolve the comparison value(s) for an observation from tier1 parsed values."""
    values = []
    for field_name in obs_def.field_names:
        v = tier1_values.get(field_name)
        if v is not None:
            values.append(v)

    if not values:
        return None

    if obs_def.aggregate == "first":
        return values[0]
    elif obs_def.aggregate == "sum":
        return sum(float(v) for v in values)
    elif obs_def.aggregate == "sum_abs":
        return sum(abs(float(v)) for v in values)
    else:
        return values[0]


# ── Tolerances ─────────────────────────────────────────────────────────────────


def _watts_tolerance(parsed_value: float) -> float:
    """±10% or ±10 W, whichever is larger."""
    return max(abs(parsed_value) * 0.10, 10.0)


TOLERANCE_FNS = {
    "soc": lambda _v: 1.0,
    "watts": _watts_tolerance,
    "voltage": lambda _v: 2.0,
    "frequency": lambda _v: 1.0,
    "firmware_version": lambda _v: 0.0,
    "exact": lambda _v: 0.0,
}


# ── Scale inference ────────────────────────────────────────────────────────────


def infer_scale(observed: float, raw_value: int) -> Optional[str]:
    """Try matching observed against raw at candidate decimal scales.

    Returns the scale label (e.g. "÷10") if a match is found, None otherwise.
    """
    if raw_value == 0:
        return None
    for divisor, label in [(10, "÷10"), (100, "÷100")]:
        scaled = raw_value / divisor
        if abs(observed - scaled) <= max(abs(observed), abs(scaled), 1) * 0.01:
            return label
    if abs(observed - raw_value) <= 0.5:
        return "×1 (raw)"
    return None


# ── Comparison ─────────────────────────────────────────────────────────────────


def compare_observation(
    observed_str: str,
    comparison_value: Any,
    tolerance_type: str,
    raw_value: Optional[int] = None,
) -> dict:
    """Compare operator observation against comparison value.

    Returns a dict with match, observation (parsed), note, inferred_scale.
    """
    result: dict[str, Any] = {"match": None, "observation": None, "note": None, "inferred_scale": None}

    if tolerance_type == "exact":
        if isinstance(comparison_value, bool):
            obs_val: Any = observed_str.strip().lower() in ("on", "yes", "true", "1", "y")
            result["match"] = obs_val == comparison_value
            result["observation"] = obs_val
        elif hasattr(comparison_value, "name"):
            observed_norm = observed_str.strip().upper()
            actual_norm = str(comparison_value.name).upper()
            result["match"] = observed_norm == actual_norm
            result["observation"] = observed_str.strip()
        else:
            result["match"] = str(observed_str).strip() == str(comparison_value).strip()
            result["observation"] = observed_str.strip()
        return result

    try:
        observed = float(observed_str)
    except (ValueError, TypeError):
        result["note"] = f"could not parse observation '{observed_str}' as numeric"
        return result

    parsed = float(comparison_value) if comparison_value is not None else 0.0

    if tolerance_type == "firmware_version":
        # Parsed value is raw register value (e.g. 218614); device displays raw / 100.
        display_val = parsed / 100.0
        result["match"] = abs(observed - display_val) < 0.01
        result["observation"] = observed
        if not result["match"] and raw_value is not None:
            scale = infer_scale(observed, raw_value)
            if scale is not None:
                result["inferred_scale"] = scale
                result["note"] = f"matches raw value at {scale}"
        return result

    tolerance = TOLERANCE_FNS[tolerance_type](parsed)
    diff = abs(observed - parsed)
    result["match"] = diff <= tolerance
    result["observation"] = observed

    if not result["match"] and raw_value is not None:
        scale = infer_scale(observed, raw_value)
        if scale is not None:
            result["inferred_scale"] = scale
            result["note"] = f"matches raw value at {scale}"

    return result


# ── Observation building ──────────────────────────────────────────────────────


def build_observation_items(
    device: Any,
    tier1_values: dict,
    source_override: Optional[str] = None,
    selected_categories: Optional[frozenset[str]] = None,
) -> list[ObservationCheck]:
    """Build the list of observation checks for a device and its tier1 values.

    Filters by model, resolves comparison values, and flags unanchorable fields.
    When source_override is given (e.g. "app_live"), "device_screen" sources
    are replaced with the override value.
    When selected_categories is given and does not include "observations",
    returns an empty list.
    """
    if selected_categories is not None and "observations" not in selected_categories:
        return []

    model_name = getattr(device, "type", device.__class__.__name__)
    items: list[ObservationCheck] = []

    for obs_def in CORE_OBSERVATION_DEFS:
        if obs_def.model_filter is not None and model_name != obs_def.model_filter:
            continue

        comparison = resolve_observation_value(tier1_values, obs_def)
        if comparison is None:
            items.append(
                ObservationCheck(
                    field=obs_def.id,
                    prompt=obs_def.prompt,
                    source=obs_def.source,
                    status="unanchored",
                    note="no tier1 value available for this field",
                )
            )
            continue

        source = obs_def.source
        if source_override is not None:
            source = source_override

        items.append(
            ObservationCheck(
                field=obs_def.id,
                prompt=obs_def.prompt,
                source=source,
                parsed=comparison,
            )
        )

    return items


def _lookup_raw_value(device: Any, field_names: list[str], tier1_blocks: dict) -> tuple[Optional[int], Optional[str]]:
    """Return (raw_value, block_key) for the first matched field.

    Searches all device struct fields for matching names, then scans every
    tier-1 block to find the one whose address range contains the field's
    register.  Falls back to a hard-coded map for synthesized keys
    (acPhase[0].voltage, gridPhase[0].voltage) that have no struct entry.
    """
    import struct

    # Synthesized-key overrides: keys produced by phase fills that are not
    # struct fields.  (block_start, register_address).
    SYNTH_REGISTERS: dict[str, tuple[int, int]] = {
        "acPhase[0].voltage": (1400, 1431),
        "gridPhase[0].voltage": (1300, 1314),
    }

    # 1. Try struct fields
    for attr in vars(device).values():
        if not hasattr(attr, "fields"):
            continue
        for f in attr.fields:
            if f.name not in field_names:
                continue
            for addr_key, block in tier1_blocks.items():
                if block.raw is None:
                    continue
                try:
                    block_start = int(addr_key)
                except ValueError:
                    continue
                raw_bytes = bytes.fromhex(block.raw)
                reg_count = len(raw_bytes) // 2
                if block_start <= f.address < block_start + reg_count:
                    offset = 2 * (f.address - block_start)
                    if offset + 2 <= len(raw_bytes):
                        return struct.unpack("!H", raw_bytes[offset : offset + 2])[0], addr_key

    # 2. Try synthesized-key overrides
    for name in field_names:
        if name in SYNTH_REGISTERS:
            block_start, reg_addr = SYNTH_REGISTERS[name]
            for addr_key, block in tier1_blocks.items():
                if block.raw is None:
                    continue
                try:
                    bs = int(addr_key)
                except ValueError:
                    continue
                raw_bytes = bytes.fromhex(block.raw)
                reg_count = len(raw_bytes) // 2
                if bs <= reg_addr < bs + reg_count:
                    offset = 2 * (reg_addr - bs)
                    if offset + 2 <= len(raw_bytes):
                        return struct.unpack("!H", raw_bytes[offset : offset + 2])[0], addr_key

    return None, None


# ── Observation runner ────────────────────────────────────────────────────────


async def run_observations(
    items: list[ObservationCheck],
    tier1_blocks: dict,
    device: Any,
    prompt_fn: Callable[[str, str], Any],
) -> None:
    """Run observation prompts, mutating items in-place with results.

    Args:
        items: ObservationCheck list from build_observation_items (mutated).
        tier1_blocks: BlockResult dict from tier 1.
        device: The device object for struct field lookup.
        prompt_fn: async callable(prompt_text, source) → operator_str or None (skip).
    """
    for item in items:
        if item.status == "unanchored":
            continue

        obs_def = CORE_OBS_MAP.get(item.field)
        tolerance_type = obs_def.tolerance_type if obs_def else "exact"
        is_secondary = obs_def.source in ("multimeter", "app_screenshot") if obs_def else False

        prompt_text = item.prompt
        if item.parsed is not None:
            from .verify import _serialize

            parsed_display = _serialize(item.parsed)
            if item.source in ("app_live", "device_screen"):
                where = "the app" if item.source == "app_live" else "the screen"
                prompt_text = f"{item.prompt} (voltkeeper parsed: {parsed_display}) — type what {where} shows"
            else:
                prompt_text = f"{item.prompt} (voltkeeper parsed: {parsed_display})"

        response = await prompt_fn(prompt_text, item.source)
        if response is None or response.strip() == "":
            if is_secondary:
                item.status = "unanchored"
                item.note = "no secondary source available"
            else:
                item.status = "skipped"
                item.note = "operator skipped"
            continue

        response = response.strip()

        # Alternating-value pattern: operator enters two levels separated by "/"
        if "/" in response and tolerance_type not in ("exact", "firmware_version"):
            parts = [p.strip() for p in response.split("/", 1)]
            alts = []
            for p in parts:
                try:
                    alts.append(float(p))
                except (ValueError, TypeError):
                    pass
            if len(alts) == 2:
                raw_int, raw_ref = _lookup_raw_value(device, obs_def.field_names if obs_def else [], tier1_blocks)
                item.raw_ref = raw_ref
                for alt_idx, alt_val in enumerate(alts):
                    cmp = compare_observation(str(alt_val), item.parsed, tolerance_type, raw_int)
                    if cmp["match"] is True:
                        item.status = "match"
                        item.observation = response
                        item.inferred_scale = cmp["inferred_scale"]
                        item.note = f"alternating values, matched level {alt_idx + 1} ({alt_val})"
                        break
                else:
                    item.status = "mismatch"
                    item.observation = response
                    item.note = "alternating values, neither within tolerance"
                continue

        raw_int, raw_ref = _lookup_raw_value(device, obs_def.field_names if obs_def else [], tier1_blocks)
        item.raw_ref = raw_ref

        cmp = compare_observation(response, item.parsed, tolerance_type, raw_int)
        item.observation = cmp["observation"]
        item.inferred_scale = cmp["inferred_scale"]
        item.note = cmp["note"]

        if cmp["match"] is True:
            item.status = "match"
        elif cmp["match"] is False:
            item.status = "mismatch"
        else:
            item.status = "mismatch"


# ── Actuate-and-confirm ───────────────────────────────────────────────────────


def _actuate_skip_set() -> frozenset[str]:
    from .verify import SKIP_AUTO

    return SKIP_AUTO


# Fields not confirmable on device screen (see design.md device-screen inventory).
# Standard vs. Silent on AC2A: only a Turbo icon, no mode distinction on display.
NOT_CONFIRMABLE: dict[str, frozenset[str]] = {
    "AC2A": frozenset({"charging_mode"}),
    "EL100V2": frozenset(),  # EL100V2: P03 settings page shows full charging mode
}


def _actuate_field_tier(field_name: str) -> int:
    """Return the risk tier for a field, defaulting to tier 3 (safe auto)."""
    from .verify import FIELD_TIERS

    return FIELD_TIERS.get(field_name, 3)


def _is_actuate_candidate(device_field: Any, consented_tiers: frozenset[int]) -> bool:
    """Check if a field is eligible for actuate-and-confirm.

    Excludes: SKIP_AUTO fields, non-bool/non-enum fields, tier-6 fields (never actuated),
    and tier-4/5 fields when the run did not consent to that tier.
    """
    from .struct import BoolField, EnumField

    if device_field.name in _actuate_skip_set():
        return False
    if not isinstance(device_field, (BoolField, EnumField)):
        return False
    tier = _actuate_field_tier(device_field.name)
    if tier >= 6:
        return False
    if tier >= 4 and tier not in consented_tiers:
        return False
    return True


def _other_value(device_field: Any, current_raw: int) -> Optional[int]:
    """Return a different value to write for actuate-and-confirm."""
    from .struct import BoolField, EnumField

    if isinstance(device_field, BoolField):
        return 1 - (current_raw & 1)
    if isinstance(device_field, EnumField):
        members = sorted(device_field.enum, key=lambda m: m.value)
        current_member = next((m for m in members if m.value == current_raw), None)
        others = [m for m in members if m is not current_member]
        return others[0].value if others else None
    return None


def build_actuation_items(
    device: Any,
    tier1_values: dict,
    consented_tiers: frozenset[int],
    selected_categories: Optional[frozenset[str]] = None,
) -> list[ActuateCheck]:
    """Build the list of actuate-and-confirm checks for a device.

    Only includes fields whose risk tier was consented to in the verify run.
    Tier-6 fields are never actuated.
    When selected_categories is given, tier-4 fields are excluded when
    "load_actuations" is not in the set, and tier-5 fields are excluded when
    "mode_actuations" is not in the set.
    """
    from .prompt_metadata import get_field_prompt_info
    from .struct import BoolField, EnumField

    items: list[ActuateCheck] = []
    model_name = getattr(device, "type", device.__class__.__name__)
    not_confirmable = NOT_CONFIRMABLE.get(model_name, frozenset())

    cs = getattr(device, "control_struct", None)
    control_fields = list(cs.fields) if cs is not None else []

    for f in control_fields:
        if not _is_actuate_candidate(f, consented_tiers):
            tier = _actuate_field_tier(f.name)
            if tier in (4, 5) and tier not in consented_tiers:
                item = ActuateCheck(field=f.name, note=f"tier_{tier}_not_consented")
                items.append(item)
            continue

        if selected_categories is not None:
            tier = _actuate_field_tier(f.name)
            if tier == 4 and "load_actuations" not in selected_categories:
                continue
            if tier == 5 and "mode_actuations" not in selected_categories:
                continue

        current = tier1_values.get(f.name)
        if current is None:
            continue

        if isinstance(f, BoolField):
            current_raw = 1 if current else 0
        elif isinstance(f, EnumField):
            if hasattr(current, "value"):
                current_raw = current.value
            else:
                try:
                    current_raw = int(current)
                except (ValueError, TypeError):
                    continue
        else:
            continue

        other = _other_value(f, current_raw)
        if other is None:
            continue

        item = ActuateCheck(field=f.name, wrote=None, wrote_raw=other, readback=None)

        if isinstance(f, EnumField) and hasattr(current, "name"):
            other_member = next((m for m in f.enum if m.value == other), None)
            other_label = other_member.name.lower() if other_member else str(other)
            current_label = current.name.lower()
        elif isinstance(f, BoolField):
            other_label = "on" if other == 1 else "off"
            current_label = "on" if current_raw == 1 else "off"
        else:
            other_label = str(other)
            current_label = str(current_raw)

        item.wrote = other_label

        if f.name in not_confirmable:
            item.device_confirmed = None
            item.note = "not_confirmable_on_device"
            item.prompt = ""
        else:
            meta = get_field_prompt_info(device, f.name)
            item.prompt = (
                f"About to switch {meta.friendly_name} from {current_label} to {other_label} on the Bluetti unit."
            )

        items.append(item)

    return items


async def run_actuations(
    items: list[ActuateCheck],
    client: Any,
    device: Any,
    tier1_values: dict,
    prompt_fn: Callable[[str, str], Any],
) -> None:
    """Run actuate-and-confirm checks using the five-beat prompt script.

    Five-beat script for confirmable fields:
      1. Announce: what is about to change, naming the specific output/setting.
      2. Watch-for: what the operator should see on the unit display / appliance.
      3. Ready gate: Enter=proceed, s=skip (caution fields: y=proceed, Enter=skip).
      4. Write + readback (unchanged from before).
      5. Confirm: y / n / unsure.

    Write-before-confirm is deliberate per the spec: the operator confirms
    the effect of a write that has already happened.
    """
    from .commands import WriteSingleRegister
    from .prompt_metadata import get_field_prompt_info
    from .verify import _get_control_field, _to_raw_int

    for item in items:
        device_field = _get_control_field(device, item.field)
        if device_field is None:
            item.note = "field not in control_struct"
            continue

        current = tier1_values.get(item.field)
        if current is None:
            item.note = "no tier1 value"
            continue

        current_raw = _to_raw_int(device_field, current)

        if item.wrote_raw is None:
            if item.note is None:
                item.note = "no alternative value"
            continue

        other_raw = item.wrote_raw

        # not_confirmable: write, readback, restore — no prompts
        if item.note == "not_confirmable_on_device":
            try:
                await client.execute(WriteSingleRegister(device_field.address, other_raw))
            except Exception as exc:
                item.note = f"write failed: {exc}"
                continue

            readback_int = await _readback_value(client, device_field)
            if isinstance(readback_int, int):
                item.readback = _format_readback(device_field, readback_int)
            else:
                item.readback = None
                item.note = f"readback failed: {readback_int}"
                try:
                    await client.execute(WriteSingleRegister(device_field.address, current_raw))
                except Exception:
                    pass
                continue

            try:
                await client.execute(WriteSingleRegister(device_field.address, current_raw))
            except Exception:
                if item.note is None:
                    item.note = "restore failed"
            continue

        # ── Five-beat script for confirmable fields ─────────────────
        meta = get_field_prompt_info(device, item.field)

        # Beat 1+2: announce + watch-for
        announce_lines = [item.prompt]
        if meta.caution:
            announce_lines.append(f"CAUTION: {meta.caution}")
        announce_lines.append(f"What to watch: {meta.watch_for}")
        if meta.where:
            announce_lines.append(f"Where to look on the Bluetti unit: {meta.where}")
        await prompt_fn("\n".join(announce_lines), "device_screen")

        # Beat 3: ready gate
        has_caution = meta.caution is not None
        if has_caution:
            gate_response = await prompt_fn(
                "Type 'y' to proceed despite the caution, or press Enter to skip:",
                "device_screen",
            )
            if gate_response is None or gate_response.strip().lower() not in ("y", "yes"):
                item.device_confirmed = None
                item.confirm_response = None
                item.note = "operator skipped at ready gate"
                continue
        else:
            gate_response = await prompt_fn(
                "Press Enter to proceed, or type 's' to skip:",
                "device_screen",
            )
            if gate_response is not None and gate_response.strip().lower() in ("s", "skip"):
                item.device_confirmed = None
                item.confirm_response = None
                item.note = "operator skipped at ready gate"
                continue

        # Beat 4: write
        try:
            await client.execute(WriteSingleRegister(device_field.address, other_raw))
        except Exception as exc:
            item.note = f"write failed: {exc}"
            continue

        # Read back
        readback_int = await _readback_value(client, device_field)
        if not isinstance(readback_int, int):
            item.readback = None
            item.note = f"readback failed: {readback_int}"
            try:
                await client.execute(WriteSingleRegister(device_field.address, current_raw))
            except Exception:
                pass
            continue

        item.readback = _format_readback(device_field, readback_int)

        # Beat 5: confirm
        confirm_response = await prompt_fn(
            "Type 'y' if the Bluetti unit display confirms the change, "
            "'n' if it does not, or 'unsure' if you cannot tell (y/n/unsure):",
            "device_screen",
        )
        if confirm_response is None or confirm_response.strip() == "":
            item.device_confirmed = None
            item.confirm_response = None
            if item.note is None:
                item.note = "operator skipped"
        else:
            resp = confirm_response.strip().lower()
            if resp in ("y", "yes"):
                item.device_confirmed = True
                item.confirm_response = "yes"
            elif resp in ("unsure", "u"):
                item.device_confirmed = None
                item.confirm_response = "unsure"
            else:
                item.device_confirmed = False
                item.confirm_response = "no"
                if readback_int == other_raw:
                    if item.note is None:
                        item.note = "denial with readback match — possible label mapping error"

        # Restore original value
        try:
            await client.execute(WriteSingleRegister(device_field.address, current_raw))
        except Exception:
            if item.note is None:
                item.note = "restore failed"


async def _readback_value(client: Any, device_field: Any) -> int | str:
    """Read a single register and return the raw uint16, or an error string."""
    import struct

    from .verify import _read_raw

    try:
        raw = await _read_raw(client, device_field.address)
        return struct.unpack("!H", raw)[0]
    except Exception as exc:
        return str(exc)


def _format_readback(device_field: Any, raw_value: int) -> Any:
    """Format a raw register value as a label or bool for the report."""
    from .struct import BoolField, EnumField

    if isinstance(device_field, BoolField):
        return (raw_value & 1) == 1
    elif isinstance(device_field, EnumField):
        member = next((m for m in device_field.enum if m.value == raw_value), None)
        return member.name.lower() if member else raw_value
    else:
        return raw_value


# ── Induced-condition checks ─────────────────────────────────────────────────


def build_induced_checks(device: Any) -> list[dict]:
    """Build the list of induced-condition checks for a device.

    Computes the overload suggestion from the device's declared rated AC output.
    Omits the overload check when no rating is declared.
    """
    rating = getattr(device, "RATED_AC_OUTPUT_W", None)
    if rating is None:
        return []

    suggested_watts = int(rating * 1.15)
    return [
        {
            "condition": "ac_overload",
            "description": (
                f"AC overload check: the Bluetti unit is rated for {rating} W AC output.\n"
                f"Apply a resistive load of roughly {suggested_watts} W — "
                f"for example, a space heater or incandescent bulbs.\n"
                "The device's designed protection will trip — this is safe and non-damaging."
            ),
            "confirmation_phrase": "I am applying an overload",
            "rationale": (
                "AC overload trips the device's designed over-current protection, which is "
                "a non-destructive, self-resetting safety feature. The device is rated for "
                "this response per the manufacturer's specifications."
            ),
        }
    ]


async def run_induced_check(
    check: dict,
    client: Any,
    device: Any,
    prompt_fn: Callable[[str, str], Any],
) -> InducedCheck:
    """Run a single induced-condition check.

    Requires typed confirmation (tier-6 pattern) before proceeding.
    """
    result = InducedCheck(condition=check["condition"])

    # Typed confirmation (tier-6 pattern)
    confirmation = await prompt_fn(
        f"INDUCED CONDITION: {check['description']}\n"
        f"Rationale: {check['rationale']}\n\n"
        f'Type "{check["confirmation_phrase"]}" to proceed, or press Enter to skip:',
        "device_screen",
    )
    if confirmation is None or confirmation.strip() != check["confirmation_phrase"]:
        result.status = "skipped"
        result.note = "operator declined typed confirmation"
        return result

    # Capture HOME block and decode alarm/fault bits via the device's own parser.
    # V2 alarmInfo is at bytes 52–59, faultInfo at bytes 66–77 within the HOME payload
    # and is decoded by _fill_v2_alarms into tier1_values keys like alarm.overload.
    raw_home: Optional[str] = None
    alarm_keys: list[str] = []

    try:
        from .commands import ReadHoldingRegisters

        home_cmd = ReadHoldingRegisters(100, 62)
        raw_home_bytes = await client.execute(home_cmd)
        raw_home = raw_home_bytes.hex()
        parsed_home = device.parse(100, raw_home_bytes)
        alarm_keys = sorted(k for k in parsed_home if k.startswith("alarm.") or k.startswith("fault."))
    except Exception as exc:
        result.note = f"home read/parse failed: {exc}"

    if raw_home:
        result.raw_hex = raw_home

    result.alarm_bits = alarm_keys

    # Ask operator what the device showed
    indicator = await prompt_fn(
        "Which alarm indicators appeared on the device display? (e.g., overload icon, fault light, error code)",
        "device_screen",
    )
    if indicator and indicator.strip():
        result.device_indicator = indicator.strip()

    result.status = "captured"
    return result


async def run_induced_checks(
    client: Any,
    device: Any,
    prompt_fn: Callable[[str, str], Any],
    selected_categories: Optional[frozenset[str]] = None,
) -> list[InducedCheck]:
    """Run all induced-condition checks.

    When selected_categories is given and does not include "induced",
    returns an empty list.
    """
    if selected_categories is not None and "induced" not in selected_categories:
        return []
    results: list[InducedCheck] = []
    checks = build_induced_checks(device)
    for check in checks:
        result = await run_induced_check(check, client, device, prompt_fn)
        results.append(result)
    return results


# ── Report serialization ──────────────────────────────────────────────────────


def ground_truth_to_report_section(result: GroundTruthResult) -> dict:
    """Convert a GroundTruthResult to the report's ground_truth section dict."""
    from .verify import _serialize

    def _obs_to_dict(o: ObservationCheck) -> dict:
        d: dict = {
            "field": o.field,
            "prompt": o.prompt,
            "source": o.source,
            "status": o.status,
        }
        if o.observation is not None:
            d["observation"] = _serialize(o.observation)
        if o.parsed is not None:
            d["parsed"] = _serialize(o.parsed)
        if o.raw_ref is not None:
            d["raw_ref"] = o.raw_ref
        if o.inferred_scale is not None:
            d["inferred_scale"] = o.inferred_scale
        if o.note:
            d["note"] = o.note
        return d

    def _act_to_dict(a: ActuateCheck) -> dict:
        d: dict = {"field": a.field}
        if a.prompt:
            d["prompt"] = a.prompt
        if a.wrote is not None:
            d["wrote"] = _serialize(a.wrote)
        if a.readback is not None:
            d["readback"] = _serialize(a.readback)
        if a.device_confirmed is not None:
            d["device_confirmed"] = a.device_confirmed
        if a.confirm_response is not None:
            d["confirm_response"] = a.confirm_response
        if a.note:
            d["note"] = a.note
        return d

    def _ind_to_dict(i: InducedCheck) -> dict:
        d: dict = {"condition": i.condition, "status": i.status}
        if i.alarm_bits is not None:
            d["alarm_bits"] = i.alarm_bits
        if i.raw_hex is not None:
            d["raw_hex"] = i.raw_hex
        if i.device_indicator is not None:
            d["device_indicator"] = i.device_indicator
        if i.note:
            d["note"] = i.note
        return d

    section: dict = {}

    if result.categories:
        section["categories"] = dict(result.categories)
    if result.observations:
        section["observations"] = [_obs_to_dict(o) for o in result.observations]
    if result.actuations:
        section["actuations"] = [_act_to_dict(a) for a in result.actuations]
    if result.induced_checks:
        section["induced_checks"] = [_ind_to_dict(i) for i in result.induced_checks]

    return section
