## MODIFIED Requirements

### Requirement: EL100V2 writable control fields

The EL100V2 device class SHALL define a control struct with writable fields including AC output, DC output, power off, DC ECO mode, AC ECO mode, charging mode, alarm sound, LCD timeout, SOC holding limits, LED on/off control, system time, grid control, feed-in control, output voltage, output frequency, charge limits, grid limits, and feed-in limits. Field names SHALL match the APK's internal naming where available.

The device SHALL NOT expose `ups_mode` — the APK v3.0.9 hardcodes UPS mode display to "Backup" for V2 devices and never reads register 3035. Hardware verification confirmed register 3035 returns Modbus exception 3 (illegal).

The device SHALL NOT expose `sys_low_power` (2022) or `sys_high_power` (2023) — APK v3.0.10 sets `sysPowerConditions(null)` specifically for EL100V2 (its EL30V2/PR100V2 siblings keep the feature), and hardware verification (verify-EL100V2-2026-05-30) recorded both fields failing with range discrepancies and a failed restore.

The device SHALL NOT expose `led_color` (2078) — hardware verification recorded values 1–3 rejected with no readback, and the APK's `ledColor` flag is an explicit opt-in that the EL100V2 config chain never sets. On/off `ctrl_led` (2007) remains.

The EL100V2 `ChargingMode` enum SHALL include `CUSTOM = 4` — APK v3.0.10 sets `chgModeCustom=true` for EL100V2 and writes 4 to the CHARGING_MODE register (2020) when custom mode is selected.

`grid_max_current` (2214) SHALL enforce range `(1, 15)`, matching the APK `maxGridChgCurrent` range for the non-high-volt EL100V2. In the APK, custom charging mode exposes a grid-current slider that writes this register.

`control_commands` SHALL issue base settings as `ReadHoldingRegisters(2000, 67)`, matching the APK v3.0.9 `getReadRegLen` count for protocol version 2000 (protocolVer < 2008). `control_commands` SHALL also include `ReadHoldingRegisters(11000, 70)` for IoT module data — hardware-probed on EL100V2 (FW SW#3) to respond successfully. `writable_ranges` SHALL return `[range(2000, 2087), range(2200, 2218)]`.

#### Scenario: EL100V2 writable fields are queryable
- **WHEN** checking `has_field_setter` for known writable fields
- **THEN** returns True for each field defined in `WRITABLE_FIELD_NAMES`
- **THEN** returns False for `ups_mode`

#### Scenario: EL100V2 builds setter commands
- **WHEN** calling `build_setter_command("ac_output", True)`
- **THEN** returns a `WriteSingleRegister` command with address 2011 and value 1

#### Scenario: EL100V2 rejects unknown fields
- **WHEN** calling `build_setter_command("nonexistent", 1)`
- **THEN** raises `ValueError`

#### Scenario: EL100V2 does not expose system power thresholds
- **WHEN** checking `has_field_setter("sys_low_power")` or `has_field_setter("sys_high_power")`
- **THEN** returns False
- **THEN** the control struct defines no field at address 2022 or 2023

#### Scenario: EL100V2 does not expose LED color
- **WHEN** checking `has_field_setter("led_color")`
- **THEN** returns False
- **THEN** `has_field_setter("ctrl_led")` returns True

#### Scenario: EL100V2 accepts CUSTOM charging mode
- **WHEN** calling `build_setter_command("charging_mode", "custom")`
- **THEN** returns a `WriteSingleRegister` command with address 2020 and value 4

#### Scenario: EL100V2 enforces grid_max_current range
- **WHEN** calling `build_setter_command("grid_max_current", 0)` or with value 16
- **THEN** raises `ValueError`
- **WHEN** calling `build_setter_command("grid_max_current", 15)`
- **THEN** returns a `WriteSingleRegister` command with address 2214

#### Scenario: EL100V2 SOC holding limits match APK naming
- **WHEN** building the control struct for EL100V2
- **THEN** `soc_holding_low` (address 2075) is included as a writable `UintField`
- **THEN** `soc_holding_high` (address 2083) is included as a writable `UintField`

#### Scenario: EL100V2 control_commands uses merged base settings read
- **WHEN** inspecting `El100V2.control_commands`
- **THEN** exactly three `ReadHoldingRegisters` are returned: one at address 2000 with quantity 67, one at address 2200 with quantity 18, one at address 11000 with quantity 70, and none at address 2060 or 3035

#### Scenario: EL100V2 writable_ranges excludes UPS
- **WHEN** inspecting `El100V2.writable_ranges`
- **THEN** the returned list contains two ranges covering 2000–2086 and 2200–2217
- **THEN** the list does not include a range containing address 3035

## ADDED Requirements

### Requirement: EL100V2 parse behavior verified against captured register data

The test suite SHALL include register-block fixtures captured from a live EL100V2 BLE session (HOME, INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO, and base settings), documented with the device state at capture time, and parse tests exercising `El100V2.parse()` against them — mirroring the AC2A fixture approach.

#### Scenario: Captured home data parses
- **WHEN** the captured HOME block bytes are parsed
- **THEN** battery, power, and energy fields match the documented device state at capture time

#### Scenario: Captured INV blocks parse
- **WHEN** the captured INV_BASE_INFO, PV, GRID, LOAD, and INV block bytes are parsed
- **THEN** firmware version, phase, and PV keys are present as reported by the hardware
