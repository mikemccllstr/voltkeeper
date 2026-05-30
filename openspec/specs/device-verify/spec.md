## ADDED Requirements

### Requirement: verify command runs six-tier integration test

The system SHALL provide a `voltkeeper verify <address>` command that connects to a Bluetti device over BLE and runs a six-tier integration test. Tiers 1–3 SHALL run automatically without user interaction. Tiers 4–6 SHALL each prompt once before that tier's fields are tested; if the user declines, the tier SHALL be recorded as `skipped (user declined)` and the command SHALL continue to the next tier. After any tier that produces one or more failures, the command SHALL print a recommendation to share the current output before proceeding deeper.

#### Scenario: Automatic tiers run without prompts

- **WHEN** the user runs `voltkeeper verify <address>` on a supported device
- **THEN** tiers 1, 2, and 3 complete without any user interaction
- **THEN** the command prints a one-line progress summary after each tier

#### Scenario: Supervised tier prompts once per tier

- **WHEN** tier 3 completes and tier 4 fields are present on the device
- **THEN** the command prints a single warning describing the risk (load interruption) and asks `Continue? [y/N]`
- **THEN** if the user types `y`, all tier-4 fields are tested
- **THEN** if the user presses Enter or types `n`, tier 4 is recorded as `skipped (user declined)` and tier 5 is evaluated next

#### Scenario: Halt recommendation after failures

- **WHEN** any tier completes with one or more field failures or mismatches
- **THEN** the command prints "⚠ N issue(s) found — consider sharing the report before continuing"
- **THEN** the command continues to the next tier boundary (does not halt automatically)

### Requirement: tier 1 validates read and parse

Tier 1 SHALL poll all blocks returned by the device's `control_commands` and `polling_commands`, parse each response, and verify that every field listed in the device's `WRITABLE_FIELD_NAMES` and expected status fields is present in the parsed result without raising an exception.

#### Scenario: All blocks parse cleanly

- **WHEN** tier 1 runs on a device whose BLE responses match the declared register map
- **THEN** each block is recorded as `{status: pass, fields_parsed: N}`
- **THEN** no failures are recorded for tier 1

#### Scenario: A block fails to parse

- **WHEN** tier 1 receives a response that triggers a parse exception for a block
- **THEN** that block is recorded as `{status: fail, error: "<exception message>"}`
- **THEN** tier 1 overall status is `fail`

### Requirement: tier 2 performs identity writes

For each field in the device's `WRITABLE_FIELD_NAMES` whose tier (from `FIELD_TIERS`) is 2 or is not listed (defaults to tier 2/3), **and that is not in `SKIP_AUTO`**: the system SHALL read the field's current value from the tier-1 parse result, write that value back via `build_setter_command`, issue a `ReadHoldingRegisters` for that field's address, re-parse, and verify the readback matches the written value.

If the field's value was not present in the tier-1 parse result, the system SHALL write a safe default (False for BoolField, first member for EnumField, `range_min` or 0 for numeric) and document the default used.

#### Scenario: Identity write roundtrips correctly

- **WHEN** tier 2 writes the current value of `alarm_sound` (False) and re-reads
- **THEN** the result contains `{read: false, wrote: 0, readback: false, match: true, status: pass}`

#### Scenario: Field not in status uses safe default

- **WHEN** a writable field's address is absent from the tier-1 parse result
- **THEN** the system writes the safe default for that field type
- **THEN** the result contains `{read: null, wrote: <default>, note: "no status value — used safe default"}`

#### Scenario: Identity write mismatch recorded as failure

- **WHEN** the re-read value after an identity write does not match the written value
- **THEN** the result contains `{match: false, status: fail}`
- **THEN** tier 2 overall status is `fail`

#### Scenario: SKIP_AUTO field absent from tier 2 results

- **WHEN** `ctrl_led` is in `SKIP_AUTO` and tier 2 runs
- **THEN** `ctrl_led` does not appear in the tier 2 field results

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
- `in_range_rejected` (list[int]): values within `declared_range` that were rejected (anomaly list; omitted when no declared range or list is empty).
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

### Requirement: SKIP_AUTO excludes fields from automatic tier testing

The system SHALL define `SKIP_AUTO: frozenset[str]` in `src/voltkeeper/core/verify.py` listing field names to exclude from tiers 2 and 3. A field SHALL be included in `SKIP_AUTO` when its register does not support read-after-write (write-only or toggle-only semantics) or when automating writes to that field is unsafe. Fields in `SKIP_AUTO` SHALL be absent from tier 2 and tier 3 results.

#### Scenario: ctrl_led absent from automatic tiers

- **WHEN** `ctrl_led` is in `SKIP_AUTO` and tier 2 or tier 3 runs
- **THEN** `ctrl_led` does not appear in tier 2 or tier 3 field results

#### Scenario: system_time absent from automatic tiers

- **WHEN** `system_time` is in `SKIP_AUTO` and tier 2 or tier 3 runs
- **THEN** `system_time` does not appear in tier 2 or tier 3 field results

### Requirement: global FIELD_TIERS classification

The system SHALL define `FIELD_TIERS: dict[str, int]` in `src/voltkeeper/core/verify.py` mapping field names to their risk tier (4, 5, or 6). Fields not listed SHALL default to tier 2/3. The classification SHALL apply at runtime by intersecting `FIELD_TIERS` with each device's `WRITABLE_FIELD_NAMES`.

Tier 4 (load-affecting): `ac_output`, `dc_output`, `ctrl_grid`, `ctrl_feed`, `power_lifting`, `ac_eco_mode`, `dc_eco_mode`.
Tier 5 (mode-changing): `working_mode`, `ups_mode`.
Tier 6 (irreversible): `factory_reset`, `system_power`, `power_off`.

#### Scenario: ac_output is classified as tier 4

- **WHEN** the verify command builds the tier plan for any device with `ac_output` in `WRITABLE_FIELD_NAMES`
- **THEN** `ac_output` is placed in the tier-4 group and does not run in tiers 1–3

#### Scenario: charging_mode defaults to tier 3

- **WHEN** `charging_mode` is in a device's `WRITABLE_FIELD_NAMES`
- **THEN** `charging_mode` is placed in the tier-3 group (not listed in `FIELD_TIERS`, defaults to 2/3)

#### Scenario: Unknown future field defaults to tier 2/3

- **WHEN** a device has a writable field name not present in `FIELD_TIERS`
- **THEN** that field is treated as tier 2/3 (automatic, non-destructive)

### Requirement: tier 6 requires typed confirmation

Tier 6 fields (factory_reset, system_power, power_off) SHALL require the user to type `"I understand this is irreversible"` before any tier-6 field is tested. If the user does not type the exact string, tier 6 SHALL be recorded as `skipped (user declined)`.

#### Scenario: Correct confirmation proceeds to tier 6

- **WHEN** the user types `I understand this is irreversible` at the tier-6 prompt
- **THEN** tier-6 fields present on the device are tested in sequence

#### Scenario: Incorrect or empty confirmation skips tier 6

- **WHEN** the user presses Enter without typing the confirmation string
- **THEN** tier 6 is recorded as `skipped (user declined)` and the run concludes

### Requirement: output report is a scrubbed YAML file

The system SHALL write a YAML report to `hardware-data/verify-<MODEL>-<YYYY-MM-DD>.yaml` by default (overridable with `--output`). The report SHALL replace the device serial number with `VKTEST000000` and the BLE MAC address with `AA:BB:CC:DD:EE:FF` unless `--no-scrub` is passed. The report SHALL contain a top-level section per tier. Tier 3 numeric fields SHALL use the summary output format defined in the tier 3 requirement (no `probes` list; summary fields instead). Tier 3 bool and enum fields retain their existing `probes` list format.

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

#### Scenario: Skipped tiers are documented

- **WHEN** the user declines tier 4
- **THEN** the report contains `tier_4: {status: skipped, reason: "user declined", fields: {}}` rather than omitting tier 4 entirely

#### Scenario: Report includes firmware version

- **WHEN** the tier-1 parse result contains firmware version fields
- **THEN** the report's `device` section includes the firmware fields parsed from the device

### Requirement: --yes flag pre-consents to all supervised tiers

When `--yes` is passed, the command SHALL skip all interactive prompts and run all six tiers automatically. The report SHALL note `consent: pre-granted (--yes)` for each supervised tier.

#### Scenario: --yes runs all tiers without prompts

- **WHEN** the user runs `voltkeeper verify <address> --yes`
- **THEN** tiers 4, 5, and 6 run without any interactive prompt
- **THEN** tier 6 still runs only if the device has tier-6 fields in its WRITABLE_FIELD_NAMES
