# Design: EL100V2 Improvements from AC2A Implementation

## Context

`AC2A.parse()` overrides `V2Base.parse()` to layer five array parse helpers on top of the struct-based parsing: `_fill_software_versions` (INV_BASE_INFO), `_fill_pv_strings` (INV_PV_INFO), `_fill_grid_phases` (INV_GRID_INFO), `_fill_load_phases` (INV_LOAD_INFO), and `_fill_inv_phases` (INV_INV_INFO). APK v3.0.10's `ProtocolParserV2` performs the equivalent parsing unconditionally for every V2 device — the array layouts are protocol-generic, keyed by counts the device itself reports (`acPvNumber`/`dcPvNumber`, `sysPhaseNumber`).

The EL100V2 polls all five blocks (slow-cycle TLV sections) but only parses the scalar struct fields, so MCU firmware versions, PV string data, and all AC/grid voltage/current readings are dropped.

Separately, the EL100V2 control surface has drift from what the device supports, established by two independent sources that agree: the APK's `DeviceFunction` config for EL100V2 and the hardware verify capture `hardware-data/verify-EL100V2-2026-05-30.yaml`.

## Goals / Non-Goals

**Goals:**

- All V2 devices parse the INV-block arrays; AC2A behavior is byte-for-byte unchanged.
- EL100V2 control surface matches what APK v3.0.10 and hardware verification agree the device supports.
- EL100V2 parse behavior locked in with real captured-bytes fixtures, mirroring the AC2A test approach.

**Non-Goals:**

- The suspected TURBO/SILENT value swap in `ChargingMode` — separate change, pending hardware confirmation (affects AC2A too).
- Consolidating the duplicated per-module `ChargingMode` enums (ac2a.py / el100v2.py) — deferred to the swap change, which touches both enums anyway.
- Support-tier promotion for EL100V2 — the fixtures move it toward HARDWARE_VERIFIED, but promotion follows the device-testing-checklist process, not this change.
- Any new polling commands — all affected blocks are already polled.

## Decisions

### 1. Move the array helpers into `V2Base.parse()` dispatch, delete the AC2A override

The five `_fill_*` helpers move to `V2Base` unchanged (same offsets, same guards), and `V2Base.parse()` calls them in its existing address-range dispatch. `AC2A.parse()` and the helpers in ac2a.py are deleted; AC2A inherits identical behavior.

*Alternative considered:* keep helpers in AC2A and have El100V2 also subclass a shared mixin. Rejected — the APK treats this as base-protocol behavior, and a mixin adds a class for no isolation benefit.

The helpers are already defensive in the right ways for generalization: every array read is length-guarded, PV count is clamped and derived from `acPvNumber`+`dcPvNumber` in the same payload, and phase count comes from `sysPhaseNumber` in the same payload. The `result.get("sysPhaseNumber", 3)` default of 3 is kept as-is (matches APK behavior of iterating up to reported phases; length guards stop iteration on short payloads).

### 2. `_MCU_TYPE_NAMES` becomes a module-level table in v2_base.py

It is APK `DeviceFirmware` enum data, not AC2A data — same category as the alarm name tables already at module level in `_v2_alarm_tables.py` / `v2_base.py`.

### 3. `CUSTOM = 4` added to EL100V2's `ChargingMode` only

APK sets `chgModeCustom=true` for EL100V2; `DeviceSettingsChgModeActivity` writes 4 to the same CHARGING_MODE register (2020). AC2A's enum is untouched — the APK does not set `chgModeCustom` for the AC2A chain, and the enums are separate per-module classes. Note the gap between existing values 2 and 4 is real (3 is PLP024-series turbo; EL100V2 is not PLP024).

### 4. Field removals are full removals, not read-only demotions

`sys_low_power`, `sys_high_power`, `led_color` come out of both the control struct and `WRITABLE_FIELD_NAMES`. The APK never displays these for EL100V2, so there is no read value worth surfacing, and a struct field that parses garbage invites false telemetry. `writable_ranges` is unchanged (it describes the register window, not per-field support).

*Alternative considered:* keep as read-only struct fields. Rejected — verify capture shows the registers hold values the device won't honor (writes of 1–3 to led_color get no readback), so the read values are not meaningful state.

### 5. `grid_max_current` gets `range=(1, 15)`

Matches APK `maxGridChgCurrent` for non-high-volt EL100V2 and explains the verify-capture failures probing 0–2 A. `build_setter_command` already enforces ranges on `DecimalField`, so this is declarative only.

### 6. Fixtures are captured hex blobs, EL100V2-local

Mirror the AC2A pattern in `tests/conftest.py`: hex strings captured in a single live BLE session, one fixture per register block (HOME, INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO, base settings), documented with the device state at capture time. Capture comes from the `verify-raw-capture` change (a prerequisite of the hardware-session tasks): the raw-capture-enabled verify run records scrubbed per-block hex in its report, and fixtures are hand-promoted from there per the workflow documented in verify.md. Capture must happen before the parse tests can be written.

## Risks / Trade-offs

- [Other V2 devices (EL30V2) silently gain new telemetry keys] → keys only appear when the device reports nonzero counts/versions, and MQTT publishing is key-driven; call it out in the docs task. This is the same mechanism as any parse widening.
- [Removing writable fields breaks existing MQTT/HA consumers of `sys_low_power`/`sys_high_power`/`led_color` on EL100V2] → acceptable and intended: the device never honored them. Marked **BREAKING** in the proposal; documented in the user guide.
- [Hardware capture session needed before fixture tests can land, and it now also depends on `verify-raw-capture` being implemented] → sequence tasks so the code-move work (fully covered by existing AC2A tests) is independent of the fixture work; `verify-raw-capture` is small (tier 1 already holds the bytes) and lands first; if the capture session slips, the change is still archivable minus the fixture tasks only with Mike's explicit say-so.
- [Phase-array offsets could differ per model within V2] → offsets come from the APK's generic parser, and the AC2A hardware validated them; EL100V2 fixture tests will validate them a second time on different hardware.

## Open Questions

- Whether EL100V2's device firmware accepts `charging_mode = 4` — the verify capture only probed 0–2. The write path will allow it after this change; a hardware probe of 4 during the fixture-capture session confirms it (and its readback).
