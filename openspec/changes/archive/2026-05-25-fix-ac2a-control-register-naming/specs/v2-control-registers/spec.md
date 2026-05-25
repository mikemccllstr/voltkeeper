## MODIFIED Requirements

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
- **THEN** `PV_TYPE_SET` (address 2060) is included as a writable `UintField`
- **THEN** `PV2_TYPE_SET` (address 2061) is included as a writable `UintField`

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
- **THEN** `EMS_CTRL_MODE_SET` (address 2241) is included as a writable `EnumField`

#### Scenario: AC2A advanced controls are documented with APK visibility
- **WHEN** the protocol documentation lists grid max, charge max, feed max, and inv_voltage fields
- **THEN** each field is annotated with a note that `InvAdvancedParamsConfig` flags for AC2A are `false`, meaning the official Bluetti app hides these controls in Expert Mode

## REMOVED Requirements

### Requirement: RV mode is writable on AC2A
**Reason**: Register 2276 (`RV_ENABLE_SET`) was added speculatively but does not exist in the APK v3.0.9 protocol parser for base info, base settings, or advanced settings blocks. No evidence the AC2A supports this register.
**Migration**: Remove the `rv_enable_set` field from AC2A's control struct and `WRITABLE_FIELD_NAMES` if present.
