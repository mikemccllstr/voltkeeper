## MODIFIED Requirements

### Requirement: EL100V2 writable control fields

The EL100V2 device class SHALL define a control struct with writable fields including AC output, DC output, power off, DC ECO mode, AC ECO mode, charging mode, system power thresholds, alarm sound, LCD timeout, SOC holding limits, LED control, system time, grid control, feed-in control, output voltage, output frequency, charge limits, grid limits, and feed-in limits. The device SHALL NOT expose `ups_mode` — the APK v3.0.9 hardcodes UPS mode display to "Backup" for V2 devices and never reads register 3035. Hardware verification confirmed register 3035 returns Modbus exception 3 (illegal). Field names SHALL match the APK's internal naming where available.

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

#### Scenario: EL100V2 system power thresholds match APK naming
- **WHEN** building the control struct for EL100V2
- **THEN** `sys_low_power` (address 2022) is included as a writable `UintField`
- **THEN** `sys_high_power` (address 2023) is included as a writable `UintField`

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
