## ADDED Requirements

### Requirement: V2 control register constants added to AC2A

The system SHALL add module-level constants and control struct field definitions in `ac2a.py` for V2 protocol control registers documented in the APK 3.0.9 V2 register map (section 15.9 of modbus-registers.md) that are applicable to the AC2A device model.

#### Scenario: SYSTEM_TIME and timezone are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `SYSTEM_TIME` (address 2001) is included as a writable `Uint32Field`
- **THEN** `SYSTEM_TIME_ZONE` (address 2004) is included as a writable `UintField`

#### Scenario: LED control is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `CTRL_LED` (address 2007) is included as a writable field

#### Scenario: DC ECO settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `DC_ECO_AUTO_OFF_TIME` (address 2015) is included as a writable `UintField`
- **THEN** `DC_ECO_POWER` (address 2016) is included as a writable `UintField`

#### Scenario: AC ECO settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `AC_ECO_AUTO_OFF_TIME` (address 2018) is included as a writable `UintField`
- **THEN** `AC_ECO_POWER` (address 2019) is included as a writable `UintField`

#### Scenario: PV type settings are writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `PV_TYPE_SET` (address 2060) is included as a writable `UintField`
- **THEN** `PV2_TYPE_SET` (address 2061) is included as a writable `UintField`

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
- **THEN** `EMS_CTRL_MODE_SET` (address 2241) is included as a writable `EnumField`

#### Scenario: RV mode is writable on AC2A
- **WHEN** building the control struct for AC2A
- **THEN** `RV_ENABLE_SET` (address 2276) is included as a writable `BoolField`

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
