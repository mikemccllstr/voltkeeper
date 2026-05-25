## ADDED Requirements

### Requirement: AC180 device base class

The system SHALL provide an `AC180` device class in `src/voltkeeper/core/devices/ac180.py` that inherits from `V2Base` and defines the writable registers applicable to the AC180/AC180P/PLP022 portable power station family. The class SHALL NOT be registered in the device registry (it is a base class). Voltage SHALL be 56V nominal.

#### Scenario: AC180 inherits V2Base
- **WHEN** inspecting `AC180` class
- **THEN** it inherits from `V2Base`
- **THEN** `protocol_version = 2000`

#### Scenario: AC180 defines writable fields
- **WHEN** inspecting AC180's `_build_control_struct()` method
- **THEN** the following writable fields are defined: `ac_switch`, `dc_switch`, `dc_eco_mode`, `ac_eco_mode`, `charging_mode`, `power_lifting`, `working_mode`, `ups_mode`, `inv_frequency`, `child_lock`, `child_lock_level`, `sys_low_power`, `sys_high_power`
- **THEN** WRITABLE_FIELD_NAMES includes all of these

#### Scenario: AC180 voltage is 56V
- **WHEN** creating an AC180 instance
- **THEN** `DEFAULT_PACK_VOLTAGE_SCALE = 1` (default 56V nominal)
- **THEN** pack voltage fields use the default scaling

### Requirement: EL10V2 device class

The system SHALL provide an `EL10V2` device class in `src/voltkeeper/core/devices/el10v2.py` that inherits from `AC180` and customizes for the Elite 10 V2 model (model #62, 25V).

#### Scenario: EL10V2 inherits AC180
- **WHEN** inspecting `EL10V2` class
- **THEN** it inherits from `AC180`
- **THEN** `type = "EL10V2"`

#### Scenario: EL10V2 voltage is 25V
- **WHEN** creating an EL10V2 instance
- **THEN** `DEFAULT_PACK_VOLTAGE_SCALE` is overridden to handle 25V nominal voltage
- **THEN** pack voltage fields use 25V-compatible scaling

#### Scenario: EL10V2 registered in device registry
- **WHEN** a BLE device with name prefix "EL10V2" is scanned
- **THEN** `build_device("EL10V2...")` returns an `EL10V2` instance
- **THEN** the device name regex matches "EL10V2"

### Requirement: EL30V2 device class

The system SHALL provide an `EL30V2` device class in `src/voltkeeper/core/devices/el30v2.py` that inherits from `V2Base` and defines the writable registers for the Elite 30 V2 model (model #32, 25V). The class SHALL mirror the EL100V2 register layout with its unique additions.

#### Scenario: EL30V2 inherits V2Base
- **WHEN** inspecting `EL30V2` class
- **THEN** it inherits from `V2Base`
- **THEN** `type = "EL30V2"`
- **THEN** `protocol_version = 2000`

#### Scenario: EL30V2 has EL100V2-equivalent writable fields
- **WHEN** inspecting EL30V2's WRITABLE_FIELD_NAMES
- **THEN** it includes the same writable fields as EL100V2: `ac_switch`, `dc_switch`, `dc_eco_mode`, `ac_eco_mode`, `charging_mode`, `power_lifting`, `working_mode`, `inv_voltage`, `inv_freq`, `chg_max_voltage`, `chg_max_current`, `grid_max_power`, `grid_max_current`, `soc_holding_low`, `soc_holding_high`, `grid_max_input_current`, `ctrl_grid`, `ctrl_feed`, `feed_max_power`

#### Scenario: EL30V2 voltage is 25V
- **WHEN** creating an EL30V2 instance
- **THEN** `DEFAULT_PACK_VOLTAGE_SCALE` is overridden to handle 25V nominal voltage
- **THEN** pack voltage fields use 25V-compatible scaling

### Requirement: EL400 device class

The system SHALL provide an `EL400` device class in `src/voltkeeper/core/devices/el400.py` that inherits from `V2Base` and defines the writable registers for the Elite 400 model (model #29, 56V). EL400 SHALL include remote power control and sleep mode support in addition to the standard writable fields.

#### Scenario: EL400 inherits V2Base
- **WHEN** inspecting `EL400` class
- **THEN** it inherits from `V2Base`
- **THEN** `type = "EL400"`
- **THEN** `protocol_version = 2000`

#### Scenario: EL400 includes remote power and sleep controls
- **WHEN** inspecting EL400's WRITABLE_FIELD_NAMES
- **THEN** it includes `remote_power_ctrl` (write value 3/4 to SYSTEM_POWER_OFF 2013)
- **THEN** it includes `sleep_power_threshold` (register 2079)
- **THEN** it includes `remote_startup_soc` (register 2074)

#### Scenario: EL400 includes all standard writable fields
- **WHEN** inspecting EL400's `_build_control_struct()` method
- **THEN** it includes `ac_switch`, `dc_switch`, `dc_eco_mode`, `ac_eco_mode`, `charging_mode`, `power_lifting`, `working_mode`, `ups_mode`, `inv_voltage`, `inv_freq`, `chg_max_voltage`, `chg_max_current`, `grid_max_power`, `grid_max_current`, `grid_max_input_current`, `ctrl_grid`, `soc_holding_low`, `soc_holding_high`

#### Scenario: EL400 voltage is 56V
- **WHEN** creating an EL400 instance
- **THEN** `DEFAULT_PACK_VOLTAGE_SCALE = 1` (56V nominal)

### Requirement: New device classes marked hardware-unverified

All new device class files (ac180.py, el10v2.py, el30v2.py, el400.py) SHALL include `# TODO(hardware): verify against physical device` comments at the top of the class definition.

#### Scenario: New files have TODO comments
- **WHEN** inspecting any new device class file
- **THEN** the class definition includes a `# TODO(hardware):` comment

### Requirement: Device name regex matches new model prefixes

The `_DEVICE_NAME_SN_RE` regex in `bluetooth/__init__.py` SHALL match `EL10V2`, `EL30V2`, and `EL400` device name prefixes. AC180 and PLP022 are not registered (they are base classes).

#### Scenario: EL10V2 name matches regex
- **WHEN** a BLE device advertises name "EL10V225010101001"
- **THEN** the regex matches with group(1)="EL10V2"

#### Scenario: EL400 name matches regex
- **WHEN** a BLE device advertises name "EL40025010101001"
- **THEN** the regex matches with group(1)="EL400"

### Requirement: Device registry includes new model entries

The `_device_registry()` function in `bluetooth/__init__.py` SHALL map `"EL10V2"` → `EL10V2`, `"EL30V2"` → `EL30V2`, and `"EL400"` → `EL400` device classes.

#### Scenario: EL400 is in the registry
- **WHEN** `build_device("EL40025010101001")` is called
- **THEN** an `EL400` instance is returned
