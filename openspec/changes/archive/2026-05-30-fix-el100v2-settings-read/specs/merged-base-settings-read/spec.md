## ADDED Requirements

### Requirement: EL100V2 reads base settings as single contiguous block

The EL100V2 device SHALL issue a single `ReadHoldingRegisters(2000, 67)` to read base settings (registers 2000–2066) in one contiguous Modbus operation, matching the APK v3.0.9 `getReadRegLen` count for protocol version 2000 (protocolVer < 2008). The system SHALL NOT split the base settings read into separate commands at different starting addresses.

#### Scenario: EL100V2 control commands contain merged base settings read
- **WHEN** inspecting `El100V2.control_commands`
- **THEN** exactly one `ReadHoldingRegisters` targets address 2000 with quantity 67
- **THEN** no `ReadHoldingRegisters` targets address 2060

#### Scenario: Control struct fields are covered by the merged read
- **WHEN** the merged `Read(2000, 67)` response is parsed
- **THEN** fields at addresses 2000–2066 are available in the parsed result
- **THEN** fields include `ctrl_led` (2007), `charging_mode` (2020), `sys_high_power` (2023), `alarm_sound` (2066)
- **THEN** fields at 2067–2086 (lcd_timeout, soc_holding_low, led_color, soc_holding_high) are write-only — covered by `writable_ranges` but beyond the APK read range for this protocol version

### Requirement: EL100V2 excludes UPS mode from control reads

The EL100V2 device SHALL NOT issue any Modbus read for register 3035 (UPS mode). The APK v3.0.9 does not read this register for V2 devices; `DeviceSettingsWorkingModeActivityV2` hardcodes the UPS display to "Backup" without querying the device.

#### Scenario: control_commands excludes register 3035
- **WHEN** inspecting `El100V2.control_commands`
- **THEN** no `ReadHoldingRegisters` targets address 3035

#### Scenario: ups_mode is not a writable field on EL100V2
- **WHEN** checking `El100V2.WRITABLE_FIELD_NAMES`
- **THEN** `ups_mode` is not present in the list
- **THEN** `has_field_setter("ups_mode")` returns False

### Requirement: EL100V2 overrides writable_ranges to exclude UPS range

The EL100V2 device SHALL override the `writable_ranges` property to return `[range(2000, 2087), range(2200, 2218)]`, excluding the V1_UPS_MODE range that V2Base includes for EP600.

#### Scenario: EL100V2 writable_ranges matches control reads
- **WHEN** inspecting `El100V2.writable_ranges`
- **THEN** the ranges cover addresses 2000–2086 (67 readable, remainder write-only) and 2200–2217 (18 registers from 2200)
- **THEN** the range does not include address 3035
