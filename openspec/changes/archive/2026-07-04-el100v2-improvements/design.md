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

### 5. `grid_max_current` is a uint in whole amps, range `(0, 15)`

The change originally declared `range=(1, 15)` on the existing DecimalField (÷10), from the APK `maxGridChgCurrent` slider range. The 2026-07-03 bench sweep corrected this: the device accepts raw register values 0–15 and rejects 16+, and the app shows 0 A while its password-gated Pro Mode is disabled. So register 2214 holds whole amps (a DecimalField write of "15 A" would send raw 150 and be rejected), and 0 is a legitimate state meaning Pro Mode disabled — hence uint, range `(0, 15)`.

### 5a. ECO fields get bench-confirmed ranges

The same session established `dc_eco_power` 5–20 W, `ac_eco_power` 10–40 W, and both ECO auto-off times 1–4 h, each confirmed twice over (app settings screen + tier-3 probe results). Declared as ranges on the existing uint fields; registers hold watts and hours directly.

### 6. Fixtures are captured hex blobs, EL100V2-local, from two operating states

Mirror the AC2A pattern in `tests/conftest.py`: hex strings hand-promoted from verify reports per the workflow documented in verify.md, one fixture per register block, documented with the device state at capture time. The 2026-07-03 bench session produced captures in two states, and fixtures draw on both: the grid-connected run (`verify-EL100V2-ac-2026-07-03.yaml`) supplies HOME, INV_BASE_INFO, GRID, LOAD, INV, and both control blocks (live grid/load phase data, ~45 W AC + 16 W DC load at 100% SoC); the on-battery run (`verify-EL100V2-dc2-2026-07-03.yaml`, tier-1-only) supplies a second HOME and the PV block (one live DC string at ~102 W, SoC 99%). Anchor values in the spec scenarios were cross-confirmed against the Bluetti app at capture time; full session context is in `hardware-data/verify-EL100V2-2026-07-03-notes.md`.

## Risks / Trade-offs

- [Other V2 devices (EL30V2) silently gain new telemetry keys] → keys only appear when the device reports nonzero counts/versions, and MQTT publishing is key-driven; call it out in the docs task. This is the same mechanism as any parse widening.
- [Removing writable fields breaks existing MQTT/HA consumers of `sys_low_power`/`sys_high_power`/`led_color` on EL100V2] → acceptable and intended: the device never honored them. Marked **BREAKING** in the proposal; documented in the user guide.
- [Hardware capture session needed before fixture tests can land, and it now also depends on `verify-raw-capture` being implemented] → sequence tasks so the code-move work (fully covered by existing AC2A tests) is independent of the fixture work; `verify-raw-capture` is small (tier 1 already holds the bytes) and lands first; if the capture session slips, the change is still archivable minus the fixture tasks only with Mike's explicit say-so.
- [Phase-array offsets could differ per model within V2] → offsets come from the APK's generic parser, and the AC2A hardware validated them; EL100V2 fixture tests will validate them a second time on different hardware.

## Open Questions

- Whether EL100V2's device firmware accepts `charging_mode = 4` — the verify capture only probed 0–2. The write path will allow it after this change; a hardware probe of 4 during the fixture-capture session confirms it (and its readback). **ANSWERED (2026-07-03 bench): accepted, readback 4.**
