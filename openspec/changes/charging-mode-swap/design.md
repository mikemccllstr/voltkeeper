# Design: Charging-Mode Swap and EL100V2 Pack-Voltage Scale

## Context

Seven V2 device modules define byte-identical `ChargingMode` enums (STANDARD=0, TURBO=1, SILENT=2) attached to register 2020: ac2a.py, el100v2.py (plus CUSTOM=4), ac180.py, el10v2.py, el30v2.py, ac60.py, el400.py. The mapping traces to an early assumption, not the APK: `DeviceSettingsChgModeActivity` writes standard=0, **silent=1, turbo=2**, custom=4 for non-PLP024 devices. The 2026-07-03 EL100V2 bench session settled it — writing 1 put the device in Silent on its own display (`hardware-data/verify-EL100V2-2026-07-03-notes.md`). AC2A's "hardware verified" status never covered labels: verify does write/readback round-trips, which pass equally with swapped names.

Separately, `V2Base.DEFAULT_PACK_VOLTAGE_SCALE = 1` (÷10) and El100V2 does not override it, so the 0x14E6 HOME register parses as 530.5 V. AC2A, EL10V2, and EL30V2 already override to 2 (÷100). The captured evidence (5350 → 53.50 V at 100% SoC on grid; 5333 → 53.33 V at 99% on battery) matches a 56 V-class LiFePO4 pack exactly at ÷100.

## Goals / Non-Goals

**Goals:**

- `charging_mode` labels match physical device behavior on every V2 device that writes register 2020.
- One shared enum definition instead of seven copies.
- EL100V2 `packTotalVoltage` reports physical volts, anchored by captured-bytes fixture tests.

**Non-Goals:**

- V1 charging-mode enums (ac300.py, ac500.py, ac200l.py) — different registers and value sets, no evidence of a problem.
- PLP024-series mapping (standard=2, turbo=3 per APK) — no PLP024-series device exists in the tree; documented for whoever adds one.
- Auditing other devices' pack-voltage scales (AC180's ÷10 default is unverified on hardware but has no contradicting evidence; the ac180-device spec records it as-is).
- MQTT topic/schema changes — labels flow through existing plumbing.

## Decisions

### 1. Shared enum lives in v2_base.py as `ChargingMode`

STANDARD=0, SILENT=1, TURBO=2, defined once in v2_base.py next to the other shared V2 tables (`_MCU_TYPE_NAMES`, alarm tables). The six devices without CUSTOM import it; their local enum classes are deleted. commands.py was considered (WorkingMode lives there) but this enum is V2-register-2020-specific, not protocol-wide.

### 2. EL100V2 keeps a local extension for CUSTOM

Python enums cannot be subclassed with new members, so el100v2.py keeps a local `ChargingMode` (STANDARD=0, SILENT=1, TURBO=2, CUSTOM=4). CUSTOM stays EL100V2-only: the APK sets `chgModeCustom` for EL100V2 and not for the others in this family, and CUSTOM=4 was hardware-accepted only on EL100V2. One duplicate remains by necessity; a comment cross-references the shared enum.

### 3. Values are corrected in-place; no compatibility aliasing

`TURBO` writes 2 and `SILENT` writes 1, full stop. No accept-both shims, no deprecation window: the old labels wrote the wrong mode, so preserving them preserves a bug. Breaking, marked in the proposal.

### 4. EL100V2 sets `DEFAULT_PACK_VOLTAGE_SCALE = 2`

One-line override matching AC2A/EL10V2/EL30V2. The v2_base.py comment calling AC2A "the known exception" is factually stale (three devices override today, four after this change) and is updated to describe the actual split, keeping its verify-with-a-multimeter guidance.

### 5. Fixture anchors pin both fixes

The EL100V2 HOME fixtures (el100v2-improvements) gain value assertions: `packTotalVoltage == 53.50` (AC capture) and `53.33` (DC capture). The DC control fixture's charging-mode assertion flips from `TURBO` to `SILENT` — the device really was in Silent at capture, so the test finally states the physical truth; its tripwire comment is removed as part of this change (that is the update the comment demands). `tests/fixtures/ac2a_baseline.json` stores `chargingMode` as a raw int from HOME telemetry and is unaffected; the conftest AC2A `_CONTROL_HEX` comment ("charging_mode=TURBO=1") is corrected to SILENT.

## Risks / Trade-offs

- [Users with automations keyed on `turbo`/`silent` see behavior flip] → intended correction; release notes and write.md call it out. The alternative — keeping labels that do the opposite of what they say — is worse for every future user.
- [Other V2 devices' swap is confirmed only via APK, not hardware] → the register and activity code are shared across the family and EL100V2 confirms the APK is right where they conflict; the risk of the APK being wrong for siblings is negligible next to the certainty that the current labels are wrong for EL100V2.
- [Pack-voltage fix divides the reported EL100V2 voltage by 10; existing dashboards/graphs show a step] → one-time discontinuity, documented as breaking.
