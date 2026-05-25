## ADDED Requirements

### Requirement: Probe decodes ctrl_event capabilities

When probing a V2 device, the system SHALL decode the ctrl_event register (address 124, within APP_HOME_DATA at 100) into named capability flags and include them in the probe YAML output.

#### Scenario: ctrl_event decoded in probe output for V2 device
- **WHEN** a V2 device is probed and APP_HOME_DATA is successfully read
- **THEN** the profile dict includes a `capabilities` section with a `ctrl_event` key containing the raw integer value and a `decoded` key with a dict of boolean capability flags

#### Scenario: ctrl_event skipped when APP_HOME_DATA fails
- **WHEN** a V2 device is probed but APP_HOME_DATA read fails with an error
- **THEN** no `capabilities` section is included in the profile output

#### Scenario: ctrl_event not emitted for V1 devices
- **WHEN** a V1 device is probed
- **THEN** no `capabilities` section is included in the profile output

### Requirement: Probe ctrl_event bit definitions

The system SHALL use the AC2A's `CTRL_EVENT_BITS` as the canonical bit definitions for decoding ctrl_event in probes. Each bit SHALL be decoded as a boolean flag with the bit's label as the key.

#### Scenario: ctrl_event bit 0 is power_control
- **WHEN** ctrl_event value has bit 0 set
- **THEN** the decoded capabilities include `power_control: true`

#### Scenario: all bits off
- **WHEN** ctrl_event value is 0
- **THEN** all decoded capability flags are `false`
