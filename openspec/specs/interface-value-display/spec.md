## ADDED Requirements

### Requirement: CLI verbose display adds unit suffixes

The CLI verbose output SHALL append unit suffixes to fields whose `UintField.unit` attribute is set. The source of truth for which fields carry which unit is the device's control struct definition, not a hardcoded name list in the display layer.

This broadens coverage to include the AC200L, AC300, and AC500 naming variants (`eco_off_time` → `h`, `eco_auto_off` → `h`) which were previously omitted.

#### Scenario: ECO timeout shown with hours suffix
- **WHEN** CLI verbose output renders `ac_eco_auto_off_time = 4` (any device)
- **THEN** the display shows `"4h"`

#### Scenario: ECO power shown with watts suffix
- **WHEN** CLI verbose output renders `dc_eco_power = 10` (any device)
- **THEN** the display shows `"10W"`

#### Scenario: AC300 eco_off_time shown with hours suffix
- **WHEN** CLI verbose output renders `eco_off_time = 2` on an AC300
- **THEN** the display shows `"2h"`

#### Scenario: AC200L eco_auto_off shown with hours suffix
- **WHEN** CLI verbose output renders `eco_auto_off = 1` on an AC200L
- **THEN** the display shows `"1h"`

#### Scenario: Fields with no unit are unaffected
- **WHEN** CLI verbose output renders `lcd_timeout = 30`
- **THEN** the display shows `"30"` with no suffix

### Requirement: CLI write command shows field help

The `write` command SHALL accept a `--help-field FIELD` option that displays the type, valid values, and range constraints for a specific writable field. Without `--help-field`, an error on unknown field SHALL display a terse help line showing how to get per-field help.

#### Scenario: Help for an enum field
- **WHEN** user runs `voltkeeper write --help-field charging_mode`
- **THEN** the output shows `"charging_mode: EnumField[ChargingMode] (values: standard, turbo, silent)"`

#### Scenario: Help for a ranged numeric field
- **WHEN** user runs `voltkeeper write --help-field sys_low_power`
- **THEN** the output shows `"sys_low_power: UintField (range: 0-100)"`

#### Scenario: Help for a boolean field
- **WHEN** user runs `voltkeeper write --help-field ac_output`
- **THEN** the output shows `"ac_output: BoolField (values: on, off)"`

### Requirement: CLI write unknown-field error suggests --help-field

When the user provides an unknown writable field name, the error message SHALL include a hint to use `--help-field` for per-field documentation.

#### Scenario: Unknown field error with help hint
- **WHEN** user runs `voltkeeper write AA:BB:CC:DD:EE:FF nonexistent 1`
- **THEN** the output includes `"Unknown writable field: nonexistent"`
- **THEN** the output includes `"Use --help-field <field> to see valid values for a specific field"`

### Requirement: CLI _parse_field_value delegates to API validation

The daemon-mode `_parse_field_value` in `cli.py` SHALL NOT hardcode enum value mappings. Instead, it SHALL send the raw user string as the value in the API POST, relying on the server's `build_setter_command` to validate and convert.

#### Scenario: Daemon mode sends raw string for enum
- **WHEN** user runs `voltkeeper write --daemon mydevice charging_mode turbo`
- **THEN** the API POST body includes `{"field": "charging_mode", "value": "turbo"}`
- **THEN** the server's `build_setter_command` resolves `ChargingMode["TURBO"].value`

#### Scenario: Daemon mode sends raw string for bool
- **WHEN** user runs `voltkeeper write --daemon mydevice ac_output on`
- **THEN** the API POST body includes `{"field": "ac_output", "value": "on"}`
- **THEN** the server's `build_setter_command` converts `"on"` to `1`

### Requirement: HTTP API returns descriptive validation errors

When `build_setter_command` raises `ValueError` during a write request, the HTTP API SHALL return a 400 response with a JSON body containing the field name and error message.

#### Scenario: Out-of-range write returns descriptive error
- **WHEN** API receives `{"field": "sys_low_power", "value": 150}`
- **THEN** the response is 400 with body `{"error": "sys_low_power: value 150 not in range (0, 100)"}`

#### Scenario: Invalid enum value returns descriptive error
- **WHEN** API receives `{"field": "charging_mode", "value": "fast"}`
- **THEN** the response is 400 with body containing the invalid value and available options

### Requirement: Web UI charging_mode sends string name not integer string

The Web UI SHALL send the enum member name (e.g., `"TURBO"`) rather than the integer string (e.g., `"1"`) when the user changes the charging mode dropdown, so that `build_setter_command` can correctly resolve the string to an enum value.

#### Scenario: Charging mode dropdown sends string name
- **WHEN** user selects "Turbo" from the charging mode dropdown
- **THEN** the `sendCommand` call sends `"TURBO"` as the value

### Requirement: Web UI writable fields discovered dynamically

The Web UI SHALL fetch the list of writable fields from `GET /api/device/{address}/fields` instead of using a hardcoded array. The endpoint SHALL return each field's name, type, enum values (if applicable), and range (if applicable).

#### Scenario: Fields endpoint returns field metadata
- **WHEN** calling `GET /api/device/{address}/fields`
- **THEN** the response includes `{"fields": [{"name": "charging_mode", "type": "enum", "values": ["standard", "turbo", "silent"]}, {"name": "ac_output", "type": "bool"}, {"name": "sys_low_power", "type": "int", "range": [0, 100]}]}`

#### Scenario: Web UI renders enum fields as dropdowns
- **WHEN** the fields endpoint returns an enum-typed field
- **THEN** the Web UI renders a `<select>` dropdown with an option for each enum value

#### Scenario: Web UI renders bool fields as toggles
- **WHEN** the fields endpoint returns a bool-typed field
- **THEN** the Web UI renders a toggle checkbox

#### Scenario: Web UI renders ranged int fields as number inputs
- **WHEN** the fields endpoint returns an int-typed field with a range
- **THEN** the Web UI renders a `<input type="number">` with min/max attributes set

### Requirement: MQTT client exposes new enum fields

The `NORMAL_DEVICE_FIELDS` mapping in `mqtt_client.py` SHALL include entries for the newly-enumified writable fields: `inv_freq` (ENUM), `pv_type_set` (ENUM), `pv2_type_set` (ENUM), `led_color` (ENUM), and `ems_ctrl_mode_set` (ENUM for AC2A). Each SHALL have a Home Assistant select entity configuration.

#### Scenario: LED color exposed over MQTT
- **WHEN** a device state update occurs and `led_color` has a value
- **THEN** the value is published to MQTT with its enum name
- **THEN** a Home Assistant select entity is auto-discovered with options matching the LedColor enum

#### Scenario: inv_freq exposed over MQTT
- **WHEN** a device state update occurs and `inv_freq` has a value
- **THEN** the value is published to MQTT with its enum name
- **THEN** a Home Assistant select entity is auto-discovered with "50Hz" and "60Hz" options
