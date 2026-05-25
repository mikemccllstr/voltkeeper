## MODIFIED Requirements

### Requirement: PV type settings are writable on AC2A

The system SHALL include `pv_type_set` (address 2060) and `pv2_type_set` (address 2061) as writable `EnumField` instances using `PvType` and `Pv2Type` enums respectively.

#### Scenario: PV type settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `pv_type_set` (address 2060) is included as a writable `EnumField` using `PvType`
- **THEN** `pv2_type_set` (address 2061) is included as a writable `EnumField` using `Pv2Type`

### Requirement: EMS mode is writable on AC2A

The system SHALL include `ems_ctrl_mode_set` (address 2241) as a writable `EnumField` using the `EmsCtrlMode` enum.

#### Scenario: EMS mode is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `EMS_CTRL_MODE_SET` (address 2241) is included as a writable `EnumField` using `EmsCtrlMode`

## ADDED Requirements

### Requirement: InvFrequency field writable on all V2 devices

All V2 device classes that include an `inv_freq` writable field SHALL define it as `add_enum_field("inv_freq", 2210, InvFrequency)` using the shared `InvFrequency` enum from `commands.py`.

#### Scenario: AC2A inv_freq is EnumField
- **WHEN** building the control struct for AC2A
- **THEN** `inv_freq` (address 2210) is included as a writable `EnumField` using `InvFrequency`

### Requirement: LedColor field writable on applicable V2 devices

V2 device classes whose APK `DeviceFunction` flags enable LED color control SHALL define `led_color` (address 2078) as `add_enum_field("led_color", 2078, LedColor)`.

#### Scenario: EL10V2 led_color is EnumField
- **WHEN** building the control struct for EL10V2
- **THEN** `led_color` (address 2078) is included as a writable `EnumField` using `LedColor`

### Requirement: inv_voltage documented with voltType dependency

All V2 device classes that include an `inv_voltage` field SHALL document the known enum mapping and voltType dependency in a comment near the field definition.

#### Scenario: AC2A inv_voltage has documentation comment
- **WHEN** inspecting AC2A's `_build_control_struct()`
- **THEN** a comment near the `inv_voltage` field documents the low-voltage (0=100V, 1=120V, 2=208V) and high-voltage (0=220V, 1=230V, 2=240V) mappings

### Requirement: Range validation enforced on writes

`build_setter_command` in `v2_base.py` SHALL validate that `UintField` and `DecimalField` values are within their declared range before constructing the Modbus command, raising `ValueError` with the field name and valid range for out-of-range values.

#### Scenario: Out-of-range ECO power rejected
- **WHEN** user writes `dc_eco_power = 100` (no explicit range on ac2a.py, so no rejection for fields without range)
- **THEN** for fields WITH range like `sys_low_power`, writing 150 to a field with range (0, 100) raises `ValueError`
