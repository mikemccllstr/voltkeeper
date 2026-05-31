## MODIFIED Requirements

### Requirement: tier 1 validates read and parse

Tier 1 SHALL poll all blocks returned by the device's `control_commands` and `polling_commands`, parse each response, and verify that every field listed in the device's `WRITABLE_FIELD_NAMES` and expected status fields is present in the parsed result without raising an exception. When the device's `control_commands` include a read of `IOT_BASE_INFO` (11000), tier 1 SHALL include that block in the report.

#### Scenario: All blocks parse cleanly

- **WHEN** tier 1 runs on a device whose BLE responses match the declared register map
- **THEN** each block is recorded as `{status: pass, fields_parsed: N}`
- **THEN** no failures are recorded for tier 1

#### Scenario: A block fails to parse

- **WHEN** tier 1 receives a response that triggers a parse exception for a block
- **THEN** that block is recorded as `{status: fail, error: "<exception message>"}`
- **THEN** tier 1 overall status is `fail`

#### Scenario: IoT block is present and parsed
- **WHEN** tier 1 runs on a device with IoT support and block 11000 responds
- **THEN** a block keyed `"11000"` is recorded with `status: pass` and a positive `fields_parsed` count
