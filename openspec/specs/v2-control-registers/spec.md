## ADDED Requirements

### Requirement: V2 control register constants added to AC2A

The system SHALL add module-level constants and control struct field definitions in `ac2a.py` for V2 protocol control registers documented in the APK 3.0.9 V2 register map (section 15.9 of modbus-registers.md) that are applicable to the AC2A device model. Field names SHALL match the APK's internal naming where available.

#### Scenario: SYSTEM_TIME is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SYSTEM_TIME` (address 2001) is included as a writable `Uint32Field`

#### Scenario: system_timezone is unverified on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SYSTEM_TIME_ZONE` (address 2004) is included as a readable `UintField`
- **THEN** the field is annotated with a comment noting the APK does not parse this register in `parseInvBaseSettings`

#### Scenario: LED control is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `CTRL_LED` (address 2007) is included as a writable field

#### Scenario: LCD timeout is writable on AC2A with declared range
- **WHEN** building the control struct for AC2A
- **THEN** `LCD_TIMEOUT` (address 2067) is included as a writable `UintField` with range (0, 255)

#### Scenario: DC ECO settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `DC_ECO_AUTO_OFF_TIME` (address 2015) is included as a writable `UintField`
- **THEN** `DC_ECO_POWER` (address 2016) is included as a writable `UintField`

#### Scenario: AC ECO settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `AC_ECO_AUTO_OFF_TIME` (address 2018) is included as a writable `UintField`
- **THEN** `AC_ECO_POWER` (address 2019) is included as a writable `UintField`

#### Scenario: System power thresholds are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SYS_LOW_POWER` (address 2022, APK name `sysLowPower`) is included as a writable `UintField` with range (0, 100)
- **THEN** `SYS_HIGH_POWER` (address 2023, APK name `sysHighPower`) is included as a writable `UintField` with range (0, 100)

#### Scenario: PV type settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `pv_type_set` (address 2060) is included as a writable `EnumField` using `PvType`
- **THEN** `pv2_type_set` (address 2061) is included as a writable `EnumField` using `Pv2Type`

#### Scenario: SOC holding limits are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SOC_HOLDING_LOW` (address 2075, APK name `socHoldingLow`) is included as a writable `UintField` with range (0, 100)
- **THEN** `SOC_HOLDING_HIGH` (address 2083, APK name `socHoldingHigh`) is included as a writable `UintField` with range (0, 100)

#### Scenario: SOC holding limits are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SOC_HOLDING_LOW` (address 2075, APK name `socHoldingLow`) is included as a writable `UintField` with range (0, 100)
- **THEN** `SOC_HOLDING_HIGH` (address 2083, APK name `socHoldingHigh`) is included as a writable `UintField` with range (0, 100)

#### Scenario: PV advanced and 12V output are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `PV_ADV_SET` (address 2084) is included as a writable `UintField`
- **THEN** `JA12_ENABLE` (address 2086) is included as a writable `BoolField`

#### Scenario: Grid and feed-in controls are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `CTRL_GRID` (address 2207) is included as a writable field
- **THEN** `CTRL_FEED` (address 2208) is included as a writable field

#### Scenario: Charge and grid limits are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `CHG_MAX_VOLTAGE` (address 2211) is included as a writable `DecimalField`
- **THEN** `CHG_MAX_CURRENT` (address 2212) is included as a writable `DecimalField`
- **THEN** `GRID_MAX_POWER` (address 2213) is included as a writable `UintField`
- **THEN** `GRID_MAX_CURRENT` (address 2214) is included as a writable `DecimalField`

#### Scenario: Feed-in limits are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `FEED_MAX_POWER` (address 2215) is included as a writable `UintField`
- **THEN** `FEED_MAX_CURRENT` (address 2216) is included as a writable `DecimalField`

#### Scenario: EMS mode is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `EMS_CTRL_MODE_SET` (address 2241) is included as a writable `EnumField` using `EmsCtrlMode`

#### Scenario: AC2A advanced controls are documented with APK visibility
- **WHEN** the protocol documentation lists grid max, charge max, feed max, and inv_voltage fields
- **THEN** each field is annotated with a note that `InvAdvancedParamsConfig` flags for AC2A are `false`, meaning the official Bluetti app hides these controls in Expert Mode

### Requirement: V2 control registers shared with AC60

The AC60 device class SHALL include the subset of new V2 control registers that are applicable to the AC60 model, based on the APK's `DeviceFunction.flags` for that model.

#### Scenario: AC60 inherits applicable controls
- **WHEN** building the control struct for AC60
- **THEN** registers that overlap with the existing AC60 control struct AND appear in the new V2 register documentation are included
- **THEN** AC60-specific unsupported registers are excluded

### Requirement: MQTT client exposes new V2 fields

The `NORMAL_DEVICE_FIELDS` mapping in `mqtt_client.py` SHALL include new V2 control fields that are meaningful for Home Assistant MQTT auto-discovery (e.g., grid control, feed-in control, charge limits).

#### Scenario: Grid control published over MQTT
- **WHEN** a device state update occurs and `CTRL_GRID` has a value
- **THEN** `CTRL_GRID` is published to MQTT as a writable switch entity via Home Assistant discovery
## ADDED Requirements

### Requirement: WORKING_MODE register writable on V2 devices

The system SHALL add `WORKING_MODE = 2005` constant to `v2_base.py` and support it as a writable `EnumField` via the `WorkingMode` enum defined in `commands.py`. The field SHALL be included in INV_BASE_SETTINGS parsing at data index 11.

#### Scenario: WORKING_MODE constant defined in v2_base
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `WORKING_MODE = 2005` is defined

#### Scenario: WORKING_MODE writable on AC2A
- **WHEN** user writes `working_mode = "Standard UPS"` to an AC2A
- **THEN** the system sends WriteSingleRegister to address 2005 with value 3

### Requirement: Child Lock registers available on V2 devices

The system SHALL add `CTRL_CHILD_LOCK = 2072` and `CHILD_LOCK_LEVEL = 2076` constants to `v2_base.py`. Devices whose APK `DeviceFunction.childLockCtrl = true` SHALL expose these as writable BoolField and IntField respectively.

#### Scenario: Child lock constants defined in v2_base
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `CTRL_CHILD_LOCK = 2072` and `CHILD_LOCK_LEVEL = 2076` are defined

#### Scenario: Child lock writable on AC180
- **WHEN** user writes `child_lock = on` to an AC180
- **THEN** the system sends WriteSingleRegister to address 2072 with value 0x20

### Requirement: Sleep configuration registers on V2 devices

The system SHALL add sleep configuration register constants to `v2_base.py`: `AUTO_SLEEP_DAYS = 2073`, `REMOTE_STARTUP_SOC = 2074`, `SLEEP_POWER_THRESHOLD = 2079`. These SHALL be exposed as writable fields on device classes whose APK feature flags enable remote power control or sleep mode (e.g., EL400).

#### Scenario: Sleep register constants defined
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `AUTO_SLEEP_DAYS = 2073`, `REMOTE_STARTUP_SOC = 2074`, `SLEEP_POWER_THRESHOLD = 2079` are defined

#### Scenario: Sleep fields writable on EL400
- **WHEN** user writes `remote_startup_soc = 50` to an EL400
- **THEN** the system sends WriteSingleRegister to address 2074 with value 50

### Requirement: SYSTEM_POWER_OFF multi-value encoding documented

The protocol documentation SHALL document that SYSTEM_POWER_OFF (V2: 2013, V1: 3060) accepts values 1-4 with the following semantics: 1=shutdown, 2=power down (V1 protocol), 3=power down (V2 protocol with powerOffFuncV2), 4=sleep mode.

#### Scenario: SYSTEM_POWER_OFF value documentation
- **WHEN** reading `modbus-registers.md`
- **THEN** SYSTEM_POWER_OFF entry lists values 1-4 with descriptions

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

### Requirement: SystemPowerOff enum lives in shared commands module

The `SystemPowerOff(Enum)` SHALL be defined in `src/voltkeeper/core/commands.py` alongside `WorkingMode` and `ChargingMode`, with members `NORMAL=0`, `SHUTDOWN=1`, `POWER_DOWN_V1=2`, `POWER_DOWN_V2=3`, `SLEEP=4`. The integer values match the V2 `SYSTEM_POWER_OFF` register semantics documented in `docs/source/protocol/modbus-registers.md`.

#### Scenario: Enum importable from commands module
- **WHEN** importing `SystemPowerOff` from `voltkeeper.core.commands`
- **THEN** the import succeeds with all five members accessible
- **THEN** `SystemPowerOff.SLEEP.value == 4`

### Requirement: EL400 system-power register modeled as a single enum

The EL400 device class SHALL model V2 register 2013 (`SYSTEM_POWER_OFF`) as a single `EnumField` named `system_power` using the `SystemPowerOff` enum. It SHALL NOT expose two BoolFields on the same address (the previous `power_off` + `sleep_mode` modeling caused read-side collisions). Writes SHALL accept the enum member name (`"sleep"`, `"shutdown"`, etc.) or the integer value, and SHALL emit the corresponding integer to register 2013 via `WriteSingleRegister`.

#### Scenario: Read register 2013 with sleep value
- **WHEN** EL400 parses register 2013 with raw value `4`
- **THEN** the parsed result contains `system_power = SystemPowerOff.SLEEP`
- **THEN** the result does NOT contain `power_off` or `sleep_mode` keys

#### Scenario: Write sleep mode
- **WHEN** user runs `voltkeeper write <addr> system_power sleep` on an EL400
- **THEN** the system sends `WriteSingleRegister(address=2013, value=4)`

#### Scenario: Write shutdown
- **WHEN** user runs `voltkeeper write <addr> system_power shutdown` on an EL400
- **THEN** the system sends `WriteSingleRegister(address=2013, value=1)`

#### Scenario: Invalid value rejected
- **WHEN** user writes `system_power = "wakeup"` (not an enum member)
- **THEN** `build_setter_command` raises `KeyError` or `ValueError` before sending any BLE traffic
## ADDED Requirements

### Requirement: V2 alarm and fault name tables ported from ConnConstantsV2

The system SHALL maintain table sets in `src/voltkeeper/core/devices/_v2_alarm_tables.py` mirroring the APK's `ConnConstantsV2` arrays:

- `LOW_POWER_WARN_NAMES` / `LOW_POWER_FAULT_NAMES` (single-phase portable inverters)
- `HIGH_POWER_WARN_NAMES` / `HIGH_POWER_FAULT_NAMES` (3-phase / home-power inverters)
- `MICRO_INV_WARN_NAMES` / `MICRO_INV_FAULT_NAMES` (BalconySolar / micro-inverter family)
- `PACK_HIGH_VOLT_ALARM_NAMES` / `PACK_HIGH_VOLT_ERROR_NAMES` (high-voltage battery packs)
- `BMU_WARN_NAMES` (BMU-level warnings)

Each table SHALL be a `dict[int, list[str | None]]` where the integer key is the 1-based word index and the list contains 16 entries (one per bit), with `None` for unused positions. Names SHALL be transcribed verbatim from APK string resources, preserving any spelling quirks.

#### Scenario: Module importable with all tables
- **WHEN** importing the alarm-tables module
- **THEN** all eight named tables are present as module-level constants
- **THEN** each table is a `dict[int, list[str | None]]`

### Requirement: V2Base selects alarm tables via per-class profile

`V2Base` SHALL expose `V2_ALARM_PROFILE: str = "low_power"` as a class attribute. Subclasses SHALL override this attribute to `"high_power"` for 3-phase devices (EP500, EP600, any future home-power class) or `"micro_inv"` for micro-inverter devices. The class attribute `PACK_ALARM_PROFILE: str | None = None` SHALL select a pack alarm table set, with `"high_volt"` enabling high-voltage pack alarm decoding.

#### Scenario: Default profile for portable power stations
- **WHEN** inspecting `AC2A.V2_ALARM_PROFILE`
- **THEN** the value is `"low_power"`

#### Scenario: High-power override
- **WHEN** inspecting `EP600.V2_ALARM_PROFILE`
- **THEN** the value is `"high_power"`

### Requirement: V2 alarm bits decoded into named keys

When `V2Base.parse()` processes an `APP_HOME_DATA` block (address 100), it SHALL call `_fill_v2_alarms(result, data)`. That method SHALL extract alarm-info (bytes 52–59, 4 × 16-bit words) and fault-info (bytes 66–77, 6 × 16-bit words) from the data payload and, for each set bit, add a key `alarm.<name>` or `fault.<name>` (value `True`) to the result dict using the table selected by `V2_ALARM_PROFILE`. Bits with `None` names SHALL be skipped silently.

#### Scenario: No alarms set
- **WHEN** parsing an `APP_HOME_DATA` block with all alarm/fault bytes zero
- **THEN** the result contains no keys starting with `alarm.` or `fault.`

#### Scenario: One alarm bit set
- **WHEN** parsing an `APP_HOME_DATA` block with alarm-word 1 bit 0 set, profile `"low_power"`
- **THEN** the result contains `alarm.<the name at low-power warn word 1 bit 0> = True`

#### Scenario: Profile selection affects output names
- **WHEN** identical input bytes are parsed on a `low_power` profile device vs a `high_power` profile device
- **THEN** the emitted alarm names differ, matching the respective table set

### Requirement: V2 pack alarm bits decoded with sub-device prefix

When pack alarm bytes are present in a parsed `PACK_MAIN_INFO` block (address 6000) on a device whose `PACK_ALARM_PROFILE` is set, the system SHALL emit `alarm.<name>` / `fault.<name>` keys. When the pack arrives via `_parse_node_info` with a non-zero slave address, the keys SHALL be prefixed with `sub[<slave_addr>].`.

#### Scenario: Pack alarm via direct read
- **WHEN** parsing `PACK_MAIN_INFO` on a device with `PACK_ALARM_PROFILE="high_volt"` and a set alarm bit
- **THEN** the result contains `alarm.<the corresponding pack alarm name> = True` (no `sub[...]` prefix)

#### Scenario: Pack alarm via NODE_INFO
- **WHEN** `_parse_node_info` returns a TLV item with `slave_addr=41` and `reg_addr=PACK_MAIN_INFO`, alarm bit set
- **THEN** the result contains `sub[41].alarm.<the corresponding pack alarm name> = True`
