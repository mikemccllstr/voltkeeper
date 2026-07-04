## Purpose

Define the EL100V2 (Elite 100 V2) portable power station device model — V2 protocol register map, writable control fields, IoT integration, and ctrl_event decoding — matching APK v3.0.10 behavior and verified against physical hardware.
## Requirements
### Requirement: EL100V2 registry entry

The system SHALL include the EL100V2 device in the BLE device registry with BLE name prefix `EL100V2`, mapping to the `El100V2` class.

#### Scenario: Registry lookup for EL100V2
- **WHEN** a BLE device advertises with name matching prefix `EL100V2`
- **THEN** the `build_device` factory creates an `El100V2` instance

#### Scenario: SN extraction from EL100V2 BLE name
- **WHEN** a BLE device advertises name `EL100V2<serial_number>`
- **THEN** the serial number is extracted from the name suffix

### Requirement: EL100V2 inherits V2Base polling

The EL100V2 device class SHALL inherit from `V2Base`, providing all standard V2 register block polling (HOME, INV_BASE_INFO, PV_INFO, GRID_INFO, LOAD_INFO, INV_INFO), TLV-bundled read support, NODE_INFO topology discovery, and time-sliced polling.

#### Scenario: EL100V2 polls standard V2 blocks
- **WHEN** an EL100V2 device is polled
- **THEN** all six standard V2 register blocks are included in the poll
- **THEN** the poll counter increments after each cycle

#### Scenario: EL100V2 uses TLV bundling
- **WHEN** an EL100V2 device is polled with TLV support
- **THEN** a single TLV-bundled read request is sent instead of individual commands

### Requirement: EL100V2 writable control fields

The EL100V2 device class SHALL define a control struct with writable fields including AC output, DC output, power off, DC ECO mode, AC ECO mode, charging mode, alarm sound, LCD timeout, SOC holding limits, LED on/off control, system time, grid control, feed-in control, output voltage, output frequency, charge limits, grid limits, and feed-in limits. Field names SHALL match the APK's internal naming where available.

The device SHALL NOT expose `ups_mode` — the APK v3.0.9 hardcodes UPS mode display to "Backup" for V2 devices and never reads register 3035. Hardware verification confirmed register 3035 returns Modbus exception 3 (illegal).

The device SHALL NOT expose `sys_low_power` (2022) or `sys_high_power` (2023) — APK v3.0.10 sets `sysPowerConditions(null)` specifically for EL100V2 (its EL30V2/PR100V2 siblings keep the feature), and hardware verification (verify-EL100V2-2026-05-30) recorded both fields failing with range discrepancies and a failed restore.

The device SHALL NOT expose `led_color` (2078) — hardware verification recorded values 1–3 rejected with no readback, and the APK's `ledColor` flag is an explicit opt-in that the EL100V2 config chain never sets. On/off `ctrl_led` (2007) remains.

The EL100V2 `ChargingMode` enum SHALL include `CUSTOM = 4` — APK v3.0.10 sets `chgModeCustom=true` for EL100V2 and writes 4 to the CHARGING_MODE register (2020) when custom mode is selected.

`grid_max_current` (2214) SHALL be a plain uint field in whole amps with range `(0, 15)`. Hardware verification (verify-EL100V2-ac-2026-07-03) showed the device accepts raw register values 0–15 and rejects 16+, and the app displays 0 A while its password-gated "Pro Mode" is disabled — so the register holds amps directly (not deciamps) and 0 is a legitimate device state. The APK `maxGridChgCurrent` slider range for the non-high-volt EL100V2 is 1–15 within custom charging mode.

`dc_eco_power` (2016) SHALL enforce range `(5, 20)` and `ac_eco_power` (2019) SHALL enforce range `(10, 40)`, both in watts; `dc_eco_auto_off_time` (2015) and `ac_eco_auto_off_time` (2018) SHALL enforce range `(1, 4)` hours. These match the app's ECO settings screen and the tier-3 probe results from verify-EL100V2-ac-2026-07-03.

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
- **WHEN** calling `build_setter_command("grid_max_current", 16)`
- **THEN** raises `ValueError`
- **WHEN** calling `build_setter_command("grid_max_current", 15)`
- **THEN** returns a `WriteSingleRegister` command with address 2214 and value 15 (whole amps, no decimal scaling)
- **WHEN** calling `build_setter_command("grid_max_current", 0)`
- **THEN** returns a `WriteSingleRegister` command with address 2214 and value 0

#### Scenario: EL100V2 enforces ECO field ranges
- **WHEN** calling `build_setter_command("ac_eco_power", 9)` or with value 41
- **THEN** raises `ValueError`
- **WHEN** calling `build_setter_command("dc_eco_power", 4)` or with value 21
- **THEN** raises `ValueError`
- **WHEN** calling `build_setter_command("ac_eco_auto_off_time", 0)` or `build_setter_command("dc_eco_auto_off_time", 5)`
- **THEN** raises `ValueError`

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

### Requirement: EL100V2 ctrl_event decoding

The EL100V2 device class SHALL support ctrl_event bitmask decoding using the standard V2 capability bits.

#### Scenario: EL100V2 decodes ctrl_event
- **WHEN** ctrl_event value 0x0407 is decoded
- **THEN** power_control, ac_control, dc_control are True
- **THEN** inv_control is False

#### Scenario: EL100V2 ctrl_event displays all bits
- **WHEN** ctrl_event value is 0
- **THEN** all 11 capability flags are False

### Requirement: EL100V2 pack voltage uses centivolt scaling

`El100V2` SHALL override `DEFAULT_PACK_VOLTAGE_SCALE = 2` so `packTotalVoltage` is parsed as raw ÷ 100, matching AC2A/EL10V2/EL30V2. Evidence: the 2026-07-03 captures hold raw 5350 (0x14E6) at 100% SoC and 5333 at 99% — 53.50 V / 53.33 V for a 56 V-class LiFePO4 pack, while the inherited ÷10 default reported a physically impossible 530.5 V.

#### Scenario: captured AC-run pack voltage parses to physical volts
- **WHEN** the grid-connected HOME fixture bytes are parsed
- **THEN** `packTotalVoltage` is 53.50

#### Scenario: captured DC-run pack voltage parses to physical volts
- **WHEN** the on-battery HOME fixture bytes are parsed
- **THEN** `packTotalVoltage` is 53.33

### Requirement: EL100V2 parse behavior verified against captured register data

The test suite SHALL include register-block fixtures promoted from the 2026-07-03 bench captures, documented with the device state at capture time (per `hardware-data/verify-EL100V2-2026-07-03-notes.md`), and parse tests exercising `El100V2.parse()` against them — mirroring the AC2A fixture approach in `tests/conftest.py`.

Fixtures SHALL come from two captures covering two operating states:

- **Grid-connected** (`verify-EL100V2-ac-2026-07-03.yaml`, tier-1 `raw` hex): HOME (100), INV_BASE_INFO (1100), INV_GRID_INFO (1300), INV_LOAD_INFO (1400), INV_INV_INFO (1500), base settings (2000), and control block (2200). Capture state: SoC 100%, ~45 W AC load, 16 W DC load, grid at ~119 V.
- **On-battery with DC/PV input** (`verify-EL100V2-dc2-2026-07-03.yaml`): HOME (100) and INV_PV_INFO (1200). Capture state: SoC 99%, DC input ~102 W, no grid.

#### Scenario: Captured home data parses
- **WHEN** the grid-connected HOME bytes are parsed
- **THEN** the SoC field is 100
- **WHEN** the on-battery HOME bytes are parsed
- **THEN** the SoC field is 99

#### Scenario: Captured firmware versions parse
- **WHEN** the captured INV_BASE_INFO bytes are parsed
- **THEN** `arm_version` is 218614, `dsp_version` is 220013, and `bms_version` is 108307 — the values the Bluetti app displays as v2186.14 / v2200.13 / v1083.07

#### Scenario: Captured PV string parses
- **WHEN** the on-battery INV_PV_INFO bytes are parsed
- **THEN** one PV string is reported (`dcPvNumber` 1) with `pv[0].inputPower` 102, `pv[0].inputVoltage` 12.5, and `pv[0].inputCurrent` 8.1 — matching the ~102 W DC input observed in the app

#### Scenario: Captured grid and load phases parse
- **WHEN** the grid-connected INV_GRID_INFO bytes are parsed
- **THEN** `gridPhase[0].power` is 46 and `gridPhase[0].voltage` is 119.3
- **WHEN** the grid-connected INV_LOAD_INFO bytes are parsed
- **THEN** `acPhase[0].power` is 46 and `acPhase[0].voltage` is 119.4

#### Scenario: Captured inverter phase parses
- **WHEN** the grid-connected INV_INV_INFO bytes are parsed
- **THEN** `invPhase[0]` keys are present with voltage 119.4

#### Scenario: Captured control blocks parse
- **WHEN** the grid-connected base-settings (2000) and control (2200) bytes are parsed
- **THEN** the writable fields parse without error and `grid_max_current` is 4 (whole amps)

