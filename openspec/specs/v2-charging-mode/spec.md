## Purpose

Define the V2 charging-mode register 2020 value semantics — the shared `ChargingMode` enum used by V2 devices for writing and interpreting `charging_mode` values, and the EL100V2-specific extension that adds `CUSTOM = 4`.
## Requirements
### Requirement: V2 charging-mode values match device behavior

A single shared V2 `ChargingMode` enum SHALL be defined in `v2_base.py` with `STANDARD = 0`, `SILENT = 1`, `TURBO = 2` — the register-2020 semantics established by APK v3.0.10 `DeviceSettingsChgModeActivity` for non-PLP024 devices and hardware-confirmed on EL100V2 (2026-07-03: writing 1 put the device in Silent mode on its own display; see `hardware-data/verify-EL100V2-2026-07-03-notes.md`).

All V2 device modules that expose `charging_mode` at register 2020 (AC2A, AC180, EL10V2, EL30V2, AC60, EL400) SHALL use the shared enum; their per-module `ChargingMode` classes are deleted. PLP024-series devices use a different mapping (standard=2, turbo=3) — none exist in the tree; any future one MUST NOT use the shared enum without checking its series.

#### Scenario: TURBO writes the turbo value
- **WHEN** calling `build_setter_command("charging_mode", "turbo")` on any V2 device using the shared enum
- **THEN** returns a `WriteSingleRegister` command with address 2020 and value 2

#### Scenario: SILENT writes the silent value
- **WHEN** calling `build_setter_command("charging_mode", "silent")` on any V2 device using the shared enum
- **THEN** returns a `WriteSingleRegister` command with address 2020 and value 1

#### Scenario: register value 1 parses as silent
- **WHEN** parsing a control block whose register 2020 holds 1
- **THEN** the `charging_mode` result is the SILENT member

#### Scenario: single enum definition
- **WHEN** inspecting the V2 device modules without custom charging mode
- **THEN** none defines its own `ChargingMode` class; all import the shared enum from `v2_base`

### Requirement: EL100V2 charging-mode extension carries the corrected values

The EL100V2-local `ChargingMode` (required for `CUSTOM = 4`, which the APK enables only for EL100V2 in this family) SHALL define `STANDARD = 0`, `SILENT = 1`, `TURBO = 2`, `CUSTOM = 4`, matching the shared enum's corrected values.

#### Scenario: EL100V2 turbo/silent corrected
- **WHEN** calling `build_setter_command("charging_mode", "turbo")` and `("charging_mode", "silent")` on EL100V2
- **THEN** the commands write 2 and 1 respectively to register 2020

#### Scenario: EL100V2 CUSTOM unchanged
- **WHEN** calling `build_setter_command("charging_mode", "custom")` on EL100V2
- **THEN** returns a `WriteSingleRegister` command with address 2020 and value 4
