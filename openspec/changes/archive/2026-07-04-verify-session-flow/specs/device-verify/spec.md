## ADDED Requirements

### Requirement: verify narrates progress continuously

The verify command SHALL keep the operator informed throughout the session: a banner at each tier start stating the tier's purpose, the number of fields to be tested, and a rough duration expectation; a line as each field's testing starts and a completion line including the probe count; and a line at each ground-truth category boundary. There SHALL be no stretch of automated work covering more than one field's testing that produces no output.

#### Scenario: Tier 3 sweep is narrated
- **WHEN** tier 3 begins on a device with 17 tier-2/3 fields
- **THEN** a banner states that range discovery on 17 fields is starting and that each field takes multiple writes (minutes overall)
- **THEN** each field emits a start line and a completion line with its probe count

#### Scenario: No silent stretches
- **WHEN** any tier is executing multi-field automated work
- **THEN** output appears at least at every field boundary

### Requirement: session ends with a restore audit

Any verify session that executed tier 2 or deeper SHALL end with a restore audit: re-read the device's control and status blocks, compare every writable field's parsed value against the tier-1 baseline, print each deviation to the operator in plain language with the original and current values and how to fix it, and record a `restore_audit` section in the report listing `{field, was, now}` per deviation (or `status: clean`). The audit SHALL run even under `--yes` (report section only is acceptable there). The audit SHALL NOT attempt corrective writes.

#### Scenario: Deviation reported to the operator
- **WHEN** a tier-3 restore failed and left `ac_eco_power` at 34 while the tier-1 baseline read 10
- **THEN** the session end prints that `ac_eco_power` was 10 and is now 34, with guidance to set it back
- **THEN** the report's `restore_audit` section lists the deviation

#### Scenario: Clean session recorded
- **WHEN** all restores succeeded and the re-read matches the baseline for every writable field
- **THEN** the report contains `restore_audit: {status: clean}` and the operator sees a confirmation line

#### Scenario: Tier-1-only run skips the audit
- **WHEN** a session runs with `--tier 1` (no writes performed)
- **THEN** no restore audit re-read occurs and the report notes the audit was not applicable
