<!-- Requirements refined against the 2026-07-03 EL100V2 bench session and the device-screen
     inventory in design.md. Interface: `verify --ground-truth` flag (design decision 6). -->

## ADDED Requirements

### Requirement: Ground-truth mode is opt-in and attended

The system SHALL provide an opt-in ground-truth mode via a `--ground-truth` flag on `voltkeeper verify` that prompts the operator for observations of the device's own UI and physical setup. The mode is attended by definition and `--ground-truth` and `--yes` are mutually exclusive: combining them SHALL be rejected with an error before connecting to the device, and a `--yes` report SHALL never contain a `ground_truth` section. Ground-truth mode SHALL run after whatever tiers execute, including under a `--tier` limit: passive observations and induced-condition checks depend only on the tier-1 capture, and actuate-and-confirm checks follow tier consent — a tier that never ran was never consented, so its fields record `skipped`. Every prompt SHALL be individually skippable, recording `skipped` without affecting other checks.

#### Scenario: Unattended runs unaffected
- **WHEN** `voltkeeper verify --yes` runs without the ground-truth flag
- **THEN** no ground-truth prompts appear and the report contains no `ground_truth` section

#### Scenario: Flags mutually exclusive
- **WHEN** `voltkeeper verify --yes --ground-truth` is invoked
- **THEN** the command exits with an error naming the flags as mutually exclusive, without connecting to the device

#### Scenario: Ground truth under a tier limit
- **WHEN** `voltkeeper verify --tier 1 --ground-truth` runs
- **THEN** ground-truth prompts run after tier 1, passive observations and induced-condition checks are offered, and every tier-4/5 actuation check records `skipped` with its tier noted as not consented

#### Scenario: Skipped prompt recorded
- **WHEN** the operator skips a ground-truth prompt
- **THEN** that check is recorded as `skipped` and the session continues

### Requirement: Passive observations recorded with tolerance-aware comparison

Ground-truth mode SHALL prompt for a curated core list of device-screen values — SoC, total output watts, total input watts, AC/DC output state, AC output frequency, charging mode, and firmware versions where the device shows them on-screen — and record each as observation, comparison value, reference to the captured raw block, observation source, and match result. Where the device screen shows a total (output watts, input watts), the comparison value SHALL be the sum of the corresponding parsed fields, not any single field. Numeric comparisons SHALL apply per-quantity tolerances rather than exact equality (bench-validated 2026-07-03: SoC ±1, watts ±10 % or ±10 W). Firmware-version comparisons SHALL apply the device display format (raw register ÷ 100, e.g. 218614 → "2186.14") before comparing.

#### Scenario: Observation matches within tolerance
- **WHEN** the operator enters a total output of 60 W and the parsed AC and DC outputs sum to 62 W
- **THEN** the check is recorded as a match within the watts tolerance, with both values stored

#### Scenario: Observation recorded on mismatch
- **WHEN** an observation falls outside tolerance of the comparison value
- **THEN** the check is recorded as a mismatch with both values and the raw block reference stored — the tool records, a human adjudicates

#### Scenario: Alternating observation recorded without widening tolerance
- **WHEN** the operator reports the observed value alternates between two levels (e.g. grid draw switching between 46 W and 60 W as the device cycles between battery-supplied and grid-topped-up DC load)
- **THEN** both levels are recorded, the check matches if the comparison value is within tolerance of either level, and the per-quantity tolerance is not widened

#### Scenario: Firmware version compared under display format
- **WHEN** the operator reads version "2186.14" from the device-info page and the raw register value is 218614
- **THEN** the check is recorded as a match under the ÷100 display format

### Requirement: Off-screen quantities use recorded secondary sources

Quantities the device screen does not display (AC output voltage, grid voltage, pack voltage — see the device-screen inventory in design.md) SHALL be prompted with explicit secondary sources: a multimeter reading or a vendor-app screenshot taken before or after the session (BLE exclusivity prevents concurrent app observation). Each observation SHALL record its source, and prompts SHALL allow "not available", recording the field as unanchored.

#### Scenario: Pack voltage anchored by pre-session app screenshot
- **WHEN** the operator enters 53.5 V from a pre-session app screenshot and the parsed value is 530.5
- **THEN** the check is recorded as a mismatch with source `app_screenshot`, and scale inference runs against the raw register value

#### Scenario: No secondary source available
- **WHEN** the operator has no multimeter or app screenshot for a voltage prompt
- **THEN** the field is recorded as unanchored and the session continues

### Requirement: Scale inference on numeric mismatch

When a numeric observation mismatches the parsed value, the comparator SHALL test the observation against the raw register value under candidate decimal scales (×1, ÷10, ÷100) and record any scale at which it matches.

#### Scenario: Decivolt scale inferred
- **WHEN** the operator observes 121 V and the raw register value is 1210 while the parsed value used the wrong scale
- **THEN** the report records that the observation matches the raw value at ÷10

### Requirement: Active control checks confirm effects on the device UI

Ground-truth mode SHALL support actuate-and-confirm checks: write a value to a writable enum or bool field, prompt the operator to confirm the device UI reflects the intended effect, and record wrote/readback/confirmed. The write deliberately precedes the confirmation prompt — the check exists to test whether the actuation command produces the effect our label claims. Field eligibility SHALL follow the same risk classification the tiers use (FIELD_TIERS): fields classified tier 6 (irreversible) SHALL never be actuated in ground-truth mode; fields classified tier 4 or 5 SHALL be actuated only when the operator consented to that tier during the same run, and otherwise recorded as `skipped` with the declined tier noted. Fields excluded from automatic tier testing (SKIP_AUTO) SHALL be excluded here too. The prompt SHALL tell the operator where on the device to look when the main display does not distinguish the written value (e.g. the EL100V2 shows the charging mode only on settings page P03; only Turbo has a main-display icon); when the device UI cannot reflect the difference at all, the check SHALL be recorded as `not_confirmable_on_device` rather than as a denial.

#### Scenario: Enum label swap detected
- **WHEN** the tool writes the value it maps to TURBO, readback matches, and the operator reports the device UI shows a different mode
- **THEN** the check is recorded as `device_confirmed: false` with wrote and readback values — the signature of a label mapping error

#### Scenario: Effect not visible on the device UI
- **WHEN** a written value produces no distinguishable indication anywhere on the device (e.g. Standard vs. Silent on a device with only a Turbo icon and no settings pages)
- **THEN** the check is recorded as `not_confirmable_on_device` with wrote and readback values, not as a confirmation or denial

#### Scenario: Irreversible fields are never actuated
- **WHEN** a device's control struct includes a tier-6 field (e.g. `factory_reset`, `power_off`)
- **THEN** ground-truth mode does not write to it under any circumstances — actuate-and-confirm restores the original value afterwards, which is impossible for an irreversible action

#### Scenario: Unconsented tier not actuated
- **WHEN** the operator declined tier 4 during the run and ground-truth mode reaches a tier-4 field (e.g. `ac_output`)
- **THEN** the check is recorded as `skipped` with a note that tier 4 was not consented, and no write occurs

### Requirement: Induced-condition checks capture alarm state safely

Ground-truth mode SHALL support induced-condition checks in which the operator creates a physical condition within the device's designed protections (e.g., AC overload) and the tool captures alarm/fault registers and raw HOME block hex during the condition. Each induced check SHALL require typed confirmation before proceeding, following the tier-6 pattern, and SHALL document why the condition is within designed protections. Conditions requiring defeat of a protection or risking damage SHALL NOT be offered.

#### Scenario: Overload alarm captured
- **WHEN** the operator confirms and applies a load above the device's rated output
- **THEN** the tool captures the alarm/fault registers and raw HOME hex during the event, records which alarm bits were set, and prompts the operator for which alarm indicators the device screen showed (both LCDs have overload/fault icons; the EL100V2 also keeps a fault-history page)

#### Scenario: Typed confirmation required
- **WHEN** an induced-condition check is reached and the operator does not type the confirmation phrase
- **THEN** the check is recorded as `skipped` and no instruction to create the condition is given

### Requirement: Ground-truth results are durable in the verify report

All ground-truth prompts, observations, confirmations, and induced-condition captures SHALL be recorded in a `ground_truth` section of the verify YAML report, in the same file as the tier results and raw block captures, subject to the same scrubbing rules.

#### Scenario: One session, one artifact
- **WHEN** a ground-truth session completes
- **THEN** the report contains tier results, raw block hex, and the `ground_truth` section cross-referencing them
