## ADDED Requirements

### Requirement: EL100V2 registry entry

The system SHALL include the EL100V2 device in the BLE device registry with BLE name prefix `EL100V2`, mapping to the `El100V2` class.

#### Scenario: Registry lookup for EL100V2
- **WHEN** a BLE device advertises with name matching prefix `EL100V2`
- **THEN** the `build_device` factory creates an `El100V2` instance

#### Scenario: SN extraction from EL100V2 BLE name
- **WHEN** a BLE device advertises name `EL100V2<serial_number>`
- **THEN** the serial number is extracted from the name suffix

### Requirement: EL100V2 inherits V2Base polling

The EL100V2 device class SHALL inherit from `V2Base`, providing all standard V2 register block polling (HOME, INV_BASE_INFO, PV_INFO, GRID_INFO, LOAD_INFO, INV_INFO), TLV-bundled read support, NODE_INFO topology discovery, and time-sliced polling.

#### Scenario: EL100V2 polls standard V2 blocks
- **WHEN** an EL100V2 device is polled
- **THEN** all six standard V2 register blocks are included in the poll
- **THEN** the poll counter increments after each cycle

#### Scenario: EL100V2 uses TLV bundling
- **WHEN** an EL100V2 device is polled with TLV support
- **THEN** a single TLV-bundled read request is sent instead of individual commands

### Requirement: EL100V2 writable control fields

The EL100V2 device class SHALL define a control struct with writable fields including AC output, DC output, power off, DC ECO mode, AC ECO mode, charging mode, battery range, alarm sound, LCD timeout, SOC limits, LED control, system time, grid control, feed-in control, output voltage, output frequency, charge limits, grid limits, and feed-in limits.

#### Scenario: EL100V2 writable fields are queryable
- **WHEN** checking `has_field_setter` for known writable fields
- **THEN** returns True for each field defined in `WRITABLE_FIELD_NAMES`

#### Scenario: EL100V2 builds setter commands
- **WHEN** calling `build_setter_command("ac_output", True)`
- **THEN** returns a `WriteSingleRegister` command with address 2011 and value 1

#### Scenario: EL100V2 rejects unknown fields
- **WHEN** calling `build_setter_command("nonexistent", 1)`
- **THEN** raises `ValueError`

### Requirement: EL100V2 ctrl_event decoding

The EL100V2 device class SHALL support ctrl_event bitmask decoding using the standard V2 capability bits.

#### Scenario: EL100V2 decodes ctrl_event
- **WHEN** ctrl_event value 0x0407 is decoded
- **THEN** power_control, ac_control, dc_control are True
- **THEN** inv_control is False

#### Scenario: EL100V2 ctrl_event displays all bits
- **WHEN** ctrl_event value is 0
- **THEN** all 11 capability flags are False
