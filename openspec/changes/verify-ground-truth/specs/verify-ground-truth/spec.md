<!-- Status: sketch. Requirements are provisional pending the open questions in design.md
     (app/BLE concurrency test, device-UI coverage inventory, flag-vs-subcommand decision). -->

## ADDED Requirements

### Requirement: Ground-truth mode is opt-in and attended

The system SHALL provide an opt-in ground-truth mode for `voltkeeper verify` that prompts the operator for observations of the device's own UI and physical setup. The mode SHALL NOT activate during `--yes` unattended runs. Every prompt SHALL be individually skippable, recording `skipped` without affecting other checks.

#### Scenario: Unattended runs unaffected
- **WHEN** `voltkeeper verify --yes` runs without the ground-truth flag
- **THEN** no ground-truth prompts appear and the report contains no `ground_truth` section

#### Scenario: Skipped prompt recorded
- **WHEN** the operator skips a ground-truth prompt
- **THEN** that check is recorded as `skipped` and the session continues

### Requirement: Passive observations recorded with tolerance-aware comparison

Ground-truth mode SHALL prompt for a curated core list of device-displayed values (including SoC, charging mode, AC/DC output state, AC output voltage, load watts, firmware versions) and record each as observation, parsed value, and reference to the captured raw block, with a match result. Numeric comparisons SHALL apply per-quantity tolerances rather than exact equality.

#### Scenario: Observation matches within tolerance
- **WHEN** the operator enters an AC output voltage of 122 and the parsed value is 121.0
- **THEN** the check is recorded as a match within the voltage tolerance, with both values stored

#### Scenario: Observation recorded on mismatch
- **WHEN** an observation falls outside tolerance of the parsed value
- **THEN** the check is recorded as a mismatch with both values and the raw block reference stored — the tool records, a human adjudicates

### Requirement: Scale inference on numeric mismatch

When a numeric observation mismatches the parsed value, the comparator SHALL test the observation against the raw register value under candidate decimal scales (×1, ÷10, ÷100) and record any scale at which it matches.

#### Scenario: Decivolt scale inferred
- **WHEN** the operator observes 121 V and the raw register value is 1210 while the parsed value used the wrong scale
- **THEN** the report records that the observation matches the raw value at ÷10

### Requirement: Active control checks confirm effects on the device UI

Ground-truth mode SHALL support actuate-and-confirm checks: write a value to a writable enum or bool field, prompt the operator to confirm the device UI reflects the intended effect, and record wrote/readback/confirmed. Fields excluded from automatic tier testing (SKIP_AUTO) SHALL be excluded here too.

#### Scenario: Enum label swap detected
- **WHEN** the tool writes the value it maps to TURBO, readback matches, and the operator reports the device UI shows a different mode
- **THEN** the check is recorded as `device_confirmed: false` with wrote and readback values — the signature of a label mapping error

### Requirement: Induced-condition checks capture alarm state safely

Ground-truth mode SHALL support induced-condition checks in which the operator creates a physical condition within the device's designed protections (e.g., AC overload) and the tool captures alarm/fault registers and raw HOME block hex during the condition. Each induced check SHALL require typed confirmation before proceeding, following the tier-6 pattern, and SHALL document why the condition is within designed protections. Conditions requiring defeat of a protection or risking damage SHALL NOT be offered.

#### Scenario: Overload alarm captured
- **WHEN** the operator confirms and applies a load above the device's rated output
- **THEN** the tool captures the alarm/fault registers and raw HOME hex during the event and records which alarm bits were set

#### Scenario: Typed confirmation required
- **WHEN** an induced-condition check is reached and the operator does not type the confirmation phrase
- **THEN** the check is recorded as `skipped` and no instruction to create the condition is given

### Requirement: Ground-truth results are durable in the verify report

All ground-truth prompts, observations, confirmations, and induced-condition captures SHALL be recorded in a `ground_truth` section of the verify YAML report, in the same file as the tier results and raw block captures, subject to the same scrubbing rules.

#### Scenario: One session, one artifact
- **WHEN** a ground-truth session completes
- **THEN** the report contains tier results, raw block hex, and the `ground_truth` section cross-referencing them
