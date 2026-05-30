## MODIFIED Requirements

### Requirement: tier 3 performs probe writes with range boundary testing

For each tier 2/3 field **not in `SKIP_AUTO`**, the system SHALL write test values that differ from the current value, verify the readback, and restore the original value. For BoolField: toggle and restore. For EnumField: cycle through all members in declaration order, restoring after each. For UintField, DecimalField, and Uint8Field (collectively "numeric fields"): sweep every integer value from 0 to 255 inclusive in ascending order, using the pre/in/post-range state machine described below.

**Sweep state machine:**
- **pre_range**: initial state; no early termination; transitions to `in_range` on the first accepted probe.
- **in_range**: no early termination; transitions to `post_range` on the first rejected probe after at least one accept.
- **post_range**: counts consecutive rejections; terminates the sweep for that field after 2 consecutive rejections.

A probe value is **accepted** when the readback equals the written value. A probe value is **rejected** when either the write raises an exception or the readback does not equal the written value.

**Restore optimisation**: after each probe, if the readback already equals the field's original value, the restore write SHALL be skipped (device state is already correct). Otherwise, the system SHALL write the original value and verify the readback matches. If the restore fails, the system SHALL set `restore_failed: true`, record `last_known_value`, stop probing that field, and continue with the next field.

**Output for numeric fields**: the system SHALL NOT emit a `probes` list for numeric fields. Instead it SHALL emit:
- `current_value` (int): the register value read before probing began.
- `probes_count` (int): total number of probe writes executed.
- `probed_range` ([int, int]): `[0, last_probed_value]` — the actual sweep extent.
- `probe_cap_hit` (bool): `true` when the sweep ended at 255 with the device still in `in_range` state (upper bound is "≥ 255, possibly higher").
- `declared_range` ([int, int] or null): the range declared in the device model, or null if none.
- `in_range_rejected` (list[int]): values within `declared_range` that were rejected (anomaly list; empty list when no declared range).
- `discovered_range` ([int, int] or null): min and max of all accepted values, or null if no values were accepted.
- `range_discrepancy` (bool or null): `true` when `discovered_range` differs from `declared_range`; null when either is absent.

**Status semantics for numeric fields**: the field status SHALL be `fail` only when `restore_failed` is `true`. Range discrepancies, in-range rejections, and out-of-range acceptances SHALL produce `status: pass` — they are findings, not failures.

**Probe cap**: 255 is the universal cap for all numeric fields. For `Uint8Field`, this matches the inherent byte width; for `UintField` and `DecimalField`, all declared ranges in the current codebase have `high ≤ 255`, making 255 a safe practical upper bound.

#### Scenario: Exhaustive sweep discovers range not starting at 0

- **WHEN** tier 3 probes `dc_eco_power` (no declared range) whose device-accepted range is [5, 10]
- **THEN** values 0–4 are probed and rejected (pre_range state, no early termination)
- **THEN** value 5 transitions the state to in_range
- **THEN** values 5–10 are probed and accepted
- **THEN** value 11 transitions the state to post_range (consecutive_rejections = 1)
- **THEN** value 12 is rejected (consecutive_rejections = 2) and the sweep terminates
- **THEN** the result contains `discovered_range: [5, 10]`, `probed_range: [0, 12]`, `probe_cap_hit: false`, `probes_count: 13`

#### Scenario: In-range rejection recorded as finding, not failure

- **WHEN** tier 3 probes a field with `declared_range: [0, 100]` and the device rejects value 50
- **THEN** the result contains `in_range_rejected: [50]`
- **THEN** the result contains `status: pass` (not fail)

#### Scenario: Out-of-range acceptance recorded in discovered_range

- **WHEN** tier 3 probes `sys_low_power` (declared [0, 100]) and the device accepts all values 0–255
- **THEN** `discovered_range: [0, 255]`, `range_discrepancy: true`, `probe_cap_hit: true`
- **THEN** `status: pass`

#### Scenario: Restore skip when device silently rejected

- **WHEN** a probe value is rejected and the readback equals the original value
- **THEN** no restore write is issued for that probe

#### Scenario: Restore failure halts tier-3 for that field

- **WHEN** a probe write succeeds but the subsequent restore write does not roundtrip
- **THEN** `restore_failed: true` and `last_known_value` are recorded for that field
- **THEN** testing continues with the next field

#### Scenario: Uint8Field probe sequence capped at 255

- **WHEN** tier 3 probes a `Uint8Field` with no declared range
- **THEN** the sweep covers 0–255 and does not write any value above 255

#### Scenario: Bool field unchanged — still uses probes list

- **WHEN** tier 3 tests `alarm_sound` (BoolField)
- **THEN** the result contains a `probes` list with toggle and restore entries
- **THEN** no `probes_count`, `probed_range`, or `probe_cap_hit` fields are present

### Requirement: output report is a scrubbed YAML file

The system SHALL write a YAML report to `hardware-data/verify-<MODEL>-<YYYY-MM-DD>.yaml` by default (overridable with `--output`). The report SHALL replace the device serial number with `VKTEST000000` and the BLE MAC address with `AA:BB:CC:DD:EE:FF` unless `--no-scrub` is passed. The report SHALL contain a top-level section per tier. Tier 3 numeric fields SHALL use the summary output format defined in the tier 3 requirement (no `probes` list; summary fields instead). Tier 3 bool and enum fields retain their existing `probes` list format.

#### Scenario: Report written to hardware-data by default

- **WHEN** the user runs `voltkeeper verify AA:BB:CC:DD:EE:FF` without `--output`
- **THEN** the YAML report is created at `hardware-data/verify-<MODEL>-<DATE>.yaml` relative to the current working directory

#### Scenario: Tier 3 numeric field output uses summary format

- **WHEN** the verify run completes and the report is written
- **THEN** numeric tier 3 fields contain `probes_count`, `probed_range`, `probe_cap_hit`, `declared_range`, `discovered_range`, `range_discrepancy`, `in_range_rejected`, and `current_value`
- **THEN** numeric tier 3 fields do NOT contain a `probes` list


## ADDED Requirements

### Requirement: hardware-data folder stores verify output files

The repository SHALL contain a `hardware-data/` directory at the project root, tracked by git. This directory SHALL contain all verify output YAML files produced on real hardware. A `hardware-data/README.md` SHALL describe the folder's purpose and the naming convention.

#### Scenario: hardware-data directory exists in the repository

- **WHEN** the repository is cloned
- **THEN** `hardware-data/` exists and contains a `README.md`

#### Scenario: Existing verify files are present in hardware-data

- **WHEN** the repository is at the current commit
- **THEN** `hardware-data/verify-AC2A-2026-05-26.yaml` and `hardware-data/verify-AC2A-2026-05-27.yaml` exist
