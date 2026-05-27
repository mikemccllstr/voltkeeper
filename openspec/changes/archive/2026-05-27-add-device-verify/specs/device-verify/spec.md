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

For each field in the device's `WRITABLE_FIELD_NAMES` whose tier (from `FIELD_TIERS`) is 2 or is not listed (defaults to tier 2/3): the system SHALL read the field's current value from the tier-1 parse result, write that value back via `build_setter_command`, issue a `ReadHoldingRegisters` for that field's address, re-parse, and verify the readback matches the written value.

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

### Requirement: tier 3 performs probe writes with range boundary testing

For each tier 2/3 field, the system SHALL write test values that differ from the current value, verify the readback, and restore the original value. For BoolField: toggle and restore. For EnumField: cycle through all members in declaration order, restoring after each. For UintField and DecimalField with a declared range `(low, high)`: probe the sequence `[current, low, high, low-1, high+1, high+2, 0, 65535]`. For numeric fields without a declared range: probe `[current, 0, 255, 65535, current+1, current-1]`. Each probe SHALL be followed by a restore-and-verify. If the restore write fails (readback does not match original), the system SHALL stop tier-3 testing for that field, record `restore_failed: true` with the last known value, and continue with the next field.

The system SHALL infer a `discovered_range` for numeric fields (the outermost accepted values) and SHALL set `range_discrepancy: true` when `discovered_range` differs from `declared_range`.

#### Scenario: Range boundary probing discovers wider hardware range

- **WHEN** `dc_eco_auto_off_time` has declared range (1, 5) and the device accepts values 0 through 7
- **THEN** the result contains `discovered_range: [0, 7]` and `range_discrepancy: true`

#### Scenario: Restore failure halts tier-3 for that field

- **WHEN** a probe write succeeds but the subsequent restore write does not roundtrip
- **THEN** `restore_failed: true` and `last_known_value` are recorded for that field
- **THEN** testing continues with the next field

#### Scenario: Boolean field toggled and restored

- **WHEN** tier 3 tests `alarm_sound` which is currently False
- **THEN** the system writes True, verifies readback, writes False, verifies restore
- **THEN** the result records both the probe and the restore outcomes

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

The system SHALL write a YAML report to `verify-<MODEL>-<YYYY-MM-DD>.yaml` (overridable with `--output`). The report SHALL replace the device serial number with `VKTEST000000` and the BLE MAC address with `AA:BB:CC:DD:EE:FF`. The report SHALL contain a top-level section per tier, each containing per-field results. Fields tested at a tier SHALL record at minimum: `wrote`, `readback`, `match` (for identity writes), `status` (pass/fail/skipped), and `note` (optional). Tier 6 fields that were not run SHALL be listed with `status: skipped`.

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
