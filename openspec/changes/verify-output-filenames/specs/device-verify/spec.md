## MODIFIED Requirements

### Requirement: output report is a scrubbed YAML file

The system SHALL write a YAML report to `hardware-data/<mode>_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml` by default (overridable with `--output`), where `<mode>` is `verify` for plain runs and `verify-ground-truth` for runs with `--ground-truth`, `<MODEL>` is the device type, and the timestamp is the session start time in UTC at minute precision with a literal `Z`. Filename components SHALL be separated by underscores. Report writes SHALL never overwrite an existing file: when the target path already exists (whether defaulted or given via `--output`), the writer SHALL append a `_v<N>` component before the `.yaml` suffix, choosing the smallest integer N ≥ 2 that yields a non-existent path.

The report SHALL replace the device serial number with `VKTEST000000` and the BLE MAC address with `AA:BB:CC:DD:EE:FF` unless `--no-scrub` is passed. The report SHALL contain a top-level section per tier. Tier 3 numeric fields SHALL use the summary output format defined in the tier 3 requirement (no `probes` list; summary fields instead). Tier 3 bool and enum fields retain their existing `probes` list format.

Raw block payloads recorded by tier 1 SHALL also be scrubbed unless `--no-scrub` is passed: bytes of any BCD serial-number field falling within a block's read window SHALL be zeroed, with SN fields collected from all of the device's struct definitions so V1 and V2 devices are covered alike; the IOT block's module SN, MAC, and IP bytes SHALL be zeroed at their fixed offsets. Bundle-shaped raw payloads (unsplittable TLV bundles) cannot be offset-scrubbed and SHALL be omitted from scrubbed reports; `--no-scrub` retains them under `raw_bundle`.

#### Scenario: Report written to hardware-data by default

- **WHEN** the user runs `voltkeeper verify AA:BB:CC:DD:EE:FF` without `--output` at 2026-07-04 17:59 UTC on an EL100V2
- **THEN** the YAML report is created at `hardware-data/verify_EL100V2_2026-07-04T1759Z.yaml` relative to the current working directory

#### Scenario: Ground-truth runs use the ground-truth mode component

- **WHEN** the user runs `voltkeeper verify <address> --ground-truth` without `--output`
- **THEN** the report filename begins with `verify-ground-truth_` followed by the model and timestamp

#### Scenario: Existing file is never overwritten

- **WHEN** the computed report path already exists (same mode, model, and minute — or a colliding `--output` path)
- **THEN** the report is written to the same name with `_v2` appended before `.yaml` (then `_v3`, and so on, until a non-existent path is found)
- **THEN** the pre-existing file's content is unchanged

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
- **THEN** the recorded IOT block hex (if present) has module SN, MAC, and IP bytes zeroed
- **THEN** parsing the scrubbed HOME hex succeeds and yields SN `0`

#### Scenario: V1 device serial numbers are scrubbed

- **WHEN** a verify run completes without `--no-scrub` on a V1 device whose real-data block (base register 10) contains the BCD SN at register 21
- **THEN** the recorded block hex has those SN bytes zeroed

#### Scenario: --no-scrub preserves raw payloads

- **WHEN** a verify run completes with `--no-scrub`
- **THEN** recorded block hex is byte-identical to what the device returned

#### Scenario: Bundle-shaped raw dropped from scrubbed reports

- **WHEN** a verify run records an unsplittable TLV bundle and scrubbing is enabled
- **THEN** the report contains neither `raw` nor `raw_bundle` for the affected blocks
- **WHEN** the same run uses `--no-scrub`
- **THEN** the bundle hex appears under `raw_bundle`

#### Scenario: Skipped tiers are documented

- **WHEN** the user declines tier 4
- **THEN** the report contains `tier_4: {status: skipped, reason: "user declined", fields: {}}` rather than omitting tier 4 entirely

#### Scenario: Report includes firmware version

- **WHEN** the tier-1 parse result contains firmware version fields
- **THEN** the report's `device` section includes the firmware fields parsed from the device
