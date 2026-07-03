## MODIFIED Requirements

### Requirement: tier 1 validates read and parse

Tier 1 SHALL poll all blocks returned by the device's `control_commands` and `polling_commands`, parse each response, and verify that every field listed in the device's `WRITABLE_FIELD_NAMES` and expected status fields is present in the parsed result without raising an exception. When the device's `control_commands` include a read of `IOT_BASE_INFO` (11000), tier 1 SHALL include that block in the report.

Tier 1 SHALL record the raw payload of every block it reads as a hex string in that block's report entry, for both plain reads and TLV-bundled reads (TLV items recorded per `reg_addr`, matching the parse dispatch). Raw payloads SHALL be recorded even when parsing the block fails.

#### Scenario: All blocks parse cleanly

- **WHEN** tier 1 runs on a device whose BLE responses match the declared register map
- **THEN** each block is recorded as `{status: pass, fields_parsed: N, raw: "<hex>"}`
- **THEN** no failures are recorded for tier 1

#### Scenario: A block fails to parse

- **WHEN** tier 1 receives a response that triggers a parse exception for a block
- **THEN** that block is recorded as `{status: fail, error: "<exception message>", raw: "<hex>"}`
- **THEN** tier 1 overall status is `fail`

#### Scenario: IoT block is present and parsed
- **WHEN** tier 1 runs on a device with IoT support and block 11000 responds
- **THEN** a block keyed `"11000"` is recorded with `status: pass`, a positive `fields_parsed` count, and the block's raw hex

#### Scenario: TLV items record raw payloads individually
- **WHEN** tier 1 executes a TLV-bundled read returning items for multiple register addresses
- **THEN** each item's block entry records that item's own payload hex under `raw`

### Requirement: output report is a scrubbed YAML file

The system SHALL write a YAML report to `hardware-data/verify-<MODEL>-<YYYY-MM-DD>.yaml` by default (overridable with `--output`). The report SHALL replace the device serial number with `VKTEST000000` and the BLE MAC address with `AA:BB:CC:DD:EE:FF` unless `--no-scrub` is passed. The report SHALL contain a top-level section per tier. Tier 3 numeric fields SHALL use the summary output format defined in the tier 3 requirement (no `probes` list; summary fields instead). Tier 3 bool and enum fields retain their existing `probes` list format.

Raw block payloads recorded by tier 1 SHALL also be scrubbed unless `--no-scrub` is passed: bytes belonging to serial-number fields (located via the device's struct field definitions, e.g. BCD SN fields in the HOME, INV_BASE_INFO, and PACK_MAIN_INFO blocks) and the IOT block's MAC and IP bytes SHALL be zeroed in the recorded hex.

#### Scenario: Report written to hardware-data by default

- **WHEN** the user runs `voltkeeper verify AA:BB:CC:DD:EE:FF` without `--output`
- **THEN** the YAML report is created at `hardware-data/verify-<MODEL>-<DATE>.yaml` relative to the current working directory

#### Scenario: Tier 3 numeric field output uses summary format

- **WHEN** the verify run completes and the report is written
- **THEN** numeric tier 3 fields contain `probes_count`, `probed_range`, `probe_cap_hit`, `declared_range`, `discovered_range`, `range_discrepancy`, and `current_value`
- **THEN** numeric tier 3 fields do NOT contain a `probes` list

#### Scenario: Report is written after run completes

- **WHEN** the verify run finishes (all tiers attempted or user exits)
- **THEN** the YAML report file exists at the specified path
- **THEN** no real SN or MAC address appears in the file

#### Scenario: Raw payloads are scrubbed by default

- **WHEN** a verify run completes without `--no-scrub` on a device whose HOME block contains a BCD-encoded serial number
- **THEN** the recorded HOME block hex has the SN register bytes zeroed
- **THEN** the recorded IOT block hex (if present) has MAC and IP bytes zeroed
- **THEN** parsing the scrubbed HOME hex succeeds and yields SN `0`

#### Scenario: --no-scrub preserves raw payloads

- **WHEN** a verify run completes with `--no-scrub`
- **THEN** recorded block hex is byte-identical to what the device returned

#### Scenario: Skipped tiers are documented

- **WHEN** the user declines tier 4
- **THEN** the report contains `tier_4: {status: skipped, reason: "user declined", fields: {}}` rather than omitting tier 4 entirely

#### Scenario: Report includes firmware version

- **WHEN** the tier-1 parse result contains firmware version fields
- **THEN** the report's `device` section includes the firmware fields parsed from the device
