## ADDED Requirements

### Requirement: InvFrequency enum defined in commands.py

The system SHALL define an `InvFrequency` enum in `src/voltkeeper/core/commands.py` with values `HZ_50 = 0` and `HZ_60 = 1`. The enum SHALL replace the existing V1-specific `InverterFrequency(HZ50=50, HZ60=60)` in `ac200l.py`, `ac300.py`, and `ac500.py`.

#### Scenario: InvFrequency enum values
- **WHEN** inspecting `InvFrequency`
- **THEN** `InvFrequency.HZ_50.value == 0`
- **THEN** `InvFrequency.HZ_60.value == 1`

#### Scenario: InvFrequency display via CLI
- **WHEN** a V2 device returns `inv_freq = 1`
- **THEN** the CLI verbose display shows `"hz_60"` (via `val.name.lower()`)

### Requirement: PvType enum defined in commands.py

The system SHALL define a `PvType` enum with values `PV = 0` and `OTHER = 3`.

#### Scenario: PvType values
- **WHEN** inspecting `PvType`
- **THEN** `PvType.PV.value == 0`
- **THEN** `PvType.OTHER.value == 3`

### Requirement: Pv2Type enum defined in commands.py

The system SHALL define a `Pv2Type` enum with values `PV = 0`, `OTHER = 3`, and `ALTERNATOR = 4`.

#### Scenario: Pv2Type values
- **WHEN** inspecting `Pv2Type`
- **THEN** `Pv2Type.PV.value == 0`
- **THEN** `Pv2Type.ALTERNATOR.value == 4`

### Requirement: LedColor enum defined in commands.py

The system SHALL define a `LedColor` enum with values `OFF = 0`, `COOL = 1`, `WARM = 2`, `SOS = 3`. On devices without color support (brightness-only), the same values SHALL be interpreted as `OFF = 0`, `HALF = 1`, `FULL = 2`, `SOS = 3`.

#### Scenario: LedColor values
- **WHEN** inspecting `LedColor`
- **THEN** `LedColor.OFF.value == 0`
- **THEN** `LedColor.WARM.value == 2`
- **THEN** `LedColor.SOS.value == 3`

### Requirement: EmsCtrlMode enum defined in commands.py

The system SHALL define an `EmsCtrlMode` enum with values `DISABLE = 0`, `CLOUD = 3`, `LOCAL = 4`, `DYNAMIC_PRICE = 5`, `AI = 8`.

#### Scenario: EmsCtrlMode values
- **WHEN** inspecting `EmsCtrlMode`
- **THEN** `EmsCtrlMode.LOCAL.value == 4`
- **THEN** `EmsCtrlMode.AI.value == 8`

### Requirement: V2 device classes use EnumField for enumerated registers

All V2 device classes (AC2A, AC60, AC180, EL10V2, EL30V2, EL100V2, EL400) SHALL convert the following fields from `add_uint_field` to `add_enum_field` with the appropriate enum:

- `inv_freq` (2210) → `InvFrequency`
- `pv_type_set` (2060) → `PvType`
- `pv2_type_set` (2061) → `Pv2Type`
- `led_color` (2078) → `LedColor`
- `ems_ctrl_mode_set` (2241) → `EmsCtrlMode` (AC2A only)

#### Scenario: AC2A uses enum fields
- **WHEN** inspecting AC2A's `_build_control_struct()`
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`
- **THEN** `led_color` is defined as `add_enum_field("led_color", 2078, LedColor)`

#### Scenario: AC60 uses applicable enum fields
- **WHEN** inspecting AC60's `_build_control_struct()`
- **THEN** `inv_freq` is defined as `add_enum_field("inv_freq", 2210, InvFrequency)`

#### Scenario: Enum fields display human-readable in verbose output
- **WHEN** CLI verbose output renders a device with `led_color = LedColor.OFF`
- **THEN** the display shows `"off"` (via `val.name.lower()`)

#### Scenario: Enum fields accept string names on write
- **WHEN** user writes `led_color = "warm"` via CLI
- **THEN** `build_setter_command` resolves `LedColor["WARM"].value` and sends 2 to register 2078

#### Scenario: Enum fields accept integer values on write
- **WHEN** user writes `led_color = 3` via API
- **THEN** `build_setter_command` resolves `LedColor(3).value` and sends 3 to register 2078

### Requirement: V1 InverterFrequency replaced with shared InvFrequency

V1 device classes (AC200L, AC300, AC500) that currently define a local `InverterFrequency` enum SHALL import and use the shared `InvFrequency` from `commands.py` instead.

#### Scenario: AC200L uses shared InvFrequency
- **WHEN** building the control struct for AC200L
- **THEN** `inv_frequency` is defined as `add_enum_field("inv_frequency", INVERTER_FREQUENCY, InvFrequency)`

### Requirement: inv_voltage documented with voltType dependency

`inv_voltage` (register 2209) SHALL remain as `UintField` with a comment documenting the known enum mapping and the `voltType` dependency. The comment SHALL list both the low-voltage mapping (0=100V, 1=120V, 2=208V) and the high-voltage mapping (0=220V, 1=230V, 2=240V), and note that `voltType` is not currently discoverable.

#### Scenario: inv_voltage comment present
- **WHEN** inspecting any V2 device class that defines `inv_voltage`
- **THEN** a comment near the field definition documents both voltage mappings and the voltType dependency

### Requirement: build_setter_command validates range on write

`build_setter_command` in both `v1_base.py` and `v2_base.py` SHALL call `in_range()` on `UintField` and `DecimalField` instances before constructing the `WriteSingleRegister`. If the value is out of range, a `ValueError` SHALL be raised with a message including the field name and valid range.

#### Scenario: Out-of-range value rejected
- **WHEN** user writes `sys_low_power = 150` to a device (range is 0-100)
- **THEN** `build_setter_command` raises `ValueError("sys_low_power: value 150 not in range (0, 100)")`

#### Scenario: In-range value accepted
- **WHEN** user writes `sys_low_power = 20` to a device (range is 0-100)
- **THEN** `build_setter_command` returns `WriteSingleRegister(2022, 20)`

#### Scenario: Field without range constraint passes through
- **WHEN** user writes `led_color = 2` to a device (LedColor enum, no range)
- **THEN** `build_setter_command` returns the command normally with no range check

### Requirement: invWorkingStatus display mapping in CLI

The CLI verbose output SHALL display `invWorkingStatus` with a human-readable label in addition to the raw value. The mapping SHALL be: 3/4/5 = "Normal", 7 = "Abnormal", all others = "Unknown (N)".

#### Scenario: Normal status displayed
- **WHEN** a device returns `invWorkingStatus = 4`
- **THEN** the MISC section shows `"Inv Status=4 (Normal)"`

#### Scenario: Abnormal status displayed
- **WHEN** a device returns `invWorkingStatus = 7`
- **THEN** the MISC section shows `"Inv Status=7 (Abnormal)"`

#### Scenario: Unknown status displayed
- **WHEN** a device returns `invWorkingStatus = 2`
- **THEN** the MISC section shows `"Inv Status=2 (Unknown)"`
