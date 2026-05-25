## ADDED Requirements

### Requirement: UintField carries an optional unit attribute

`UintField` SHALL accept an optional `unit: str | None` parameter. `DeviceStruct.add_uint_field` SHALL accept and pass through the same parameter. When `unit` is `None`, behaviour is unchanged.

#### Scenario: UintField with unit
- **WHEN** a `UintField` is constructed with `unit="h"`
- **THEN** `field.unit == "h"`

#### Scenario: UintField without unit
- **WHEN** a `UintField` is constructed without `unit`
- **THEN** `field.unit is None`

### Requirement: Eco time and power fields annotated with units in all device files

All device files that define eco timeout fields (dc_eco_auto_off_time, ac_eco_auto_off_time, eco_off_time, eco_auto_off) SHALL pass `unit="h"`. All device files that define eco power fields (dc_eco_power, ac_eco_power) SHALL pass `unit="W"`. Affected devices: el30v2, el10v2, el100v2, el400, ac180, ac60, ac2a, ac200l, ac300, ac500.

#### Scenario: Eco auto-off time has unit h
- **WHEN** inspecting the control struct for any V2 device with dc_eco_auto_off_time
- **THEN** the field's `unit` is `"h"`

#### Scenario: Eco power has unit W
- **WHEN** inspecting the control struct for any device with dc_eco_power
- **THEN** the field's `unit` is `"W"`

### Requirement: build_setter_command strips unit suffix before parsing

When `build_setter_command` processes a `UintField` with a non-None `unit`, it SHALL strip that unit suffix from string input before converting to int. Both suffixed and bare inputs SHALL be accepted.

#### Scenario: Suffixed input accepted
- **WHEN** user writes `dc_eco_auto_off_time = "2h"` to a device
- **THEN** `build_setter_command` sends `WriteSingleRegister` with value `2`

#### Scenario: Bare input still accepted
- **WHEN** user writes `dc_eco_auto_off_time = "2"` to a device
- **THEN** `build_setter_command` sends `WriteSingleRegister` with value `2`

#### Scenario: Suffix stripping is case-sensitive and exact
- **WHEN** `field.unit` is `"h"` and input is `"2H"`
- **THEN** the suffix is not stripped and the conversion proceeds on `"2H"` (which will raise ValueError at int conversion — this is acceptable)

### Requirement: CONTROLS verbose output shows a dimmed hint column

The CONTROLS section of `voltkeeper status --verbose` SHALL render a third column for each field, styled dim, showing the valid values or range. The hint format SHALL be:
- `[on|off]` for BoolField
- `[opt1|opt2|...]` for EnumField (member names lowercased)
- `[lo-hi]` for ranged UintField with no unit
- `[lo-hi]unit` for ranged UintField with a unit
- `[integer]` for unranged UintField with no unit
- `[integer]unit` for unranged UintField with a unit
- Empty string for fields that do not match any of the above (e.g. system_timezone)

#### Scenario: Bool field hint
- **WHEN** verbose CONTROLS renders `ac_output = on`
- **THEN** the line includes a dim `[on|off]` hint

#### Scenario: Enum field hint
- **WHEN** verbose CONTROLS renders `charging_mode = standard`
- **THEN** the line includes a dim hint listing all ChargingMode member names lowercased

#### Scenario: Ranged uint field hint
- **WHEN** verbose CONTROLS renders `sys_low_power = 20`
- **THEN** the line includes a dim `[0-100]` hint

#### Scenario: Unit field hint
- **WHEN** verbose CONTROLS renders `dc_eco_auto_off_time = 2h`
- **THEN** the line includes a dim `[integer]h` hint

#### Scenario: Unranged uint with no unit
- **WHEN** verbose CONTROLS renders `lcd_timeout = 30`
- **THEN** the line includes a dim `[integer]` hint

### Requirement: _show_field_help uses the same hint logic

The `--help-field` output SHALL use `_field_hint()` to generate the valid-value description, so it is consistent with the inline hint.

#### Scenario: --help-field for a bool field
- **WHEN** user runs `voltkeeper write --help-field ac_output`
- **THEN** the output includes `[on|off]`

#### Scenario: --help-field for an enum field
- **WHEN** user runs `voltkeeper write --help-field charging_mode`
- **THEN** the output includes the same enum hint as shown in verbose CONTROLS
