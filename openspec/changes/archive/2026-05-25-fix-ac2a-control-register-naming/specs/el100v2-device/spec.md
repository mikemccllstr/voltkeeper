## MODIFIED Requirements

### Requirement: EL100V2 writable control fields

The EL100V2 device class SHALL define a control struct with writable fields including AC output, DC output, power off, DC ECO mode, AC ECO mode, charging mode, system power thresholds, alarm sound, LCD timeout, SOC holding limits, LED control, system time, grid control, feed-in control, output voltage, output frequency, charge limits, grid limits, and feed-in limits. Field names SHALL match the APK's internal naming where available.

#### Scenario: EL100V2 writable fields are queryable
- **WHEN** checking `has_field_setter` for known writable fields
- **THEN** returns True for each field defined in `WRITABLE_FIELD_NAMES`

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
