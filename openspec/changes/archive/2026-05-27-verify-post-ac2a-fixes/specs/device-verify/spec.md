## ADDED Requirements

### Requirement: SKIP_AUTO excludes fields from automatic tier testing

The system SHALL define `SKIP_AUTO: frozenset[str]` in `src/voltkeeper/core/verify.py` listing field names to exclude from tiers 2 and 3. A field SHALL be included in `SKIP_AUTO` when its register does not support read-after-write (write-only or toggle-only semantics) or when automating writes to that field is unsafe. Fields in `SKIP_AUTO` SHALL be absent from tier 2 and tier 3 results.

#### Scenario: ctrl_led absent from automatic tiers

- **WHEN** `ctrl_led` is in `SKIP_AUTO` and tier 2 or tier 3 runs
- **THEN** `ctrl_led` does not appear in tier 2 or tier 3 field results

#### Scenario: system_time absent from automatic tiers

- **WHEN** `system_time` is in `SKIP_AUTO` and tier 2 or tier 3 runs
- **THEN** `system_time` does not appear in tier 2 or tier 3 field results

## MODIFIED Requirements

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

For each tier 2/3 field **not in `SKIP_AUTO`**, the system SHALL write test values that differ from the current value, verify the readback, and restore the original value. For BoolField: toggle and restore. For EnumField: cycle through all members in declaration order, restoring after each. For UintField and DecimalField with a declared range `(low, high)`: probe the sequence `[current, low, high, low-1, high+1, high+2, 0, 65535]`. For numeric fields without a declared range: probe `[current, 0, 255, 65535, current+1, current-1]`. For `Uint8Field`: any probe value exceeding 255 SHALL be excluded from the sequence (probing a value above 255 into a byte-wide field sets both bytes of the shared 16-bit register, potentially corrupting an adjacent field). Each probe SHALL be followed by a restore-and-verify. If the restore write fails (readback does not match original), the system SHALL stop tier-3 testing for that field, record `restore_failed: true` with the last known value, and continue with the next field.

The system SHALL infer a `discovered_range` for numeric fields (the outermost accepted values, excluding 65535) and SHALL set `range_discrepancy: true` when `discovered_range` differs from `declared_range`.

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

#### Scenario: Uint8Field probe sequence capped at 255

- **WHEN** tier 3 probes a `Uint8Field` with no declared range
- **THEN** the probe sequence does not include any value above 255
- **THEN** 65535 is not written to that field's register
