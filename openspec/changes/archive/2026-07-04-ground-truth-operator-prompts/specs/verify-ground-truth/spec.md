## MODIFIED Requirements

### Requirement: Passive observations recorded with tolerance-aware comparison

Ground-truth mode SHALL prompt for a curated core list of device-screen values — SoC, total output watts, total input watts, AC/DC output state, AC output frequency, charging mode, and firmware versions where the device shows them on-screen — and record each as observation, comparison value, reference to the captured raw block, observation source, and match result. Where the device screen shows a total (output watts, input watts), the comparison value SHALL be the sum of the corresponding parsed fields, not any single field. Numeric comparisons SHALL apply per-quantity tolerances rather than exact equality (bench-validated 2026-07-03: SoC ±1, watts ±10 % or ±10 W). Firmware-version comparisons SHALL apply the device display format (raw register ÷ 100, e.g. 218614 → "2186.14") before comparing.

Observation prompts SHALL be written for an operator with no prior familiarity with the device or the process: each prompt SHALL say where to find the value (which screen or app page, using the prompt-metadata terminology) and what format to expect. The firmware prompt SHALL state that the app's device-info page lists several component versions (ARM, DSP, BMS, IoT), name which one to report, and give a format example.

#### Scenario: Observation matches within tolerance
- **WHEN** the operator enters a total output of 60 W and the parsed AC and DC outputs sum to 62 W
- **THEN** the check is recorded as a match within the watts tolerance, with both values stored

#### Scenario: Observation recorded on mismatch
- **WHEN** an observation falls outside tolerance of the comparison value
- **THEN** the check is recorded as a mismatch with both values and the raw block reference stored — the tool records, a human adjudicates

#### Scenario: Alternating observation recorded without widening tolerance
- **WHEN** the operator reports the observed value alternates between two levels (e.g. grid draw switching between 46 W and 60 W as the device cycles between battery-supplied and grid-topped-up DC load)
- **THEN** both levels are recorded, the check matches if the comparison value is within tolerance of either level, and the per-quantity tolerance is not widened

#### Scenario: Firmware version prompt names the component
- **WHEN** the firmware observation prompt is shown
- **THEN** it states that the app lists several versions (ARM, DSP, BMS, IoT), asks for the ARM value, and shows a format example like "2186.14"
- **WHEN** the operator reads version "2186.14" from the device-info page and the raw register value is 218614
- **THEN** the check is recorded as a match under the ÷100 display format

### Requirement: Active control checks confirm effects on the device UI

Ground-truth mode SHALL support actuate-and-confirm checks: write a value to a writable enum or bool field, prompt the operator to confirm the device UI reflects the intended effect, and record wrote/readback/confirmed. The write deliberately precedes the confirmation prompt — the check exists to test whether the actuation command produces the effect our label claims. Field eligibility SHALL follow the same risk classification the tiers use (FIELD_TIERS): fields classified tier 6 (irreversible) SHALL never be actuated in ground-truth mode; fields classified tier 4 or 5 SHALL be actuated only when the operator consented to that tier during the same run, and otherwise recorded as `skipped` with the declined tier noted. Fields excluded from automatic tier testing (SKIP_AUTO) SHALL be excluded here too.

Each actuation SHALL follow a five-beat script built from the field's prompt metadata:
1. **Announce** the specific change in plain language, naming the exact output or setting (e.g. "the AC outlets", never a bare "output"), including any caution text.
2. **Describe what to watch for** on the Bluetti unit's display and, for load-affecting fields, on any connected appliance; when the main display does not distinguish the written value, the prompt SHALL say where to look (e.g. the EL100V2 shows the charging mode only on settings page P03; only Turbo has a main-display icon).
3. **Ready gate**: wait for the operator to confirm they are watching before any write; the operator may skip here, recording `skipped`. Fields whose metadata carries a caution (e.g. AC output frequency, which the user manual requires be changed only with AC output turned off) SHALL default to skip: proceeding requires explicit affirmative input, not a bare Enter.
4. **Actuate**: write and read back as before.
5. **Confirm** with three accepted outcomes: yes, no, or unsure. `unsure` SHALL be recorded distinctly and SHALL NOT count as a denial; the "denial with readback match — possible label mapping error" note SHALL fire only on an explicit no.

When the device UI cannot reflect the difference at all, the check SHALL be recorded as `not_confirmable_on_device` rather than as a denial.

#### Scenario: Actuation prompt names the specific output
- **WHEN** the `ac_output` actuation is announced
- **THEN** the prompt says the AC outlets on the Bluetti unit are about to switch off, that any appliance plugged into them will lose power, and what the display will show
- **THEN** the DC ports are not mentioned as affected

#### Scenario: Ready gate precedes the write
- **WHEN** an actuation check is reached
- **THEN** no write occurs until the operator confirms they are ready and watching
- **WHEN** the operator skips at the ready gate
- **THEN** the check records `skipped` and no write occurs

#### Scenario: Unsure outcome recorded distinctly
- **WHEN** the operator answers `unsure` at the confirm beat and the readback matches the written value
- **THEN** the check records the unsure response and does NOT carry the label-mapping-error note

#### Scenario: Enum label swap detected
- **WHEN** the tool writes the value it maps to TURBO, readback matches, and the operator explicitly reports the device UI shows a different mode
- **THEN** the check is recorded as `device_confirmed: false` with wrote and readback values — the signature of a label mapping error

#### Scenario: Frequency change requires explicit opt-in with caution
- **WHEN** the `inv_freq` actuation is reached
- **THEN** the announce beat includes the manual's caution (turn off AC output before setting the frequency)
- **THEN** a bare Enter at the ready gate skips the check; only explicit affirmative input proceeds

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

Induced-check instructions SHALL be computed from the device's declared rated specs, not hardcoded per-model prose: the AC overload prompt SHALL state the connected device's actual rated AC output and suggest a load derived from it, with a concrete household example. When the device declares no rated AC output, the overload check SHALL NOT be offered.

#### Scenario: Overload alarm captured
- **WHEN** the operator confirms and applies a load above the device's rated output
- **THEN** the tool captures the alarm/fault registers and raw HOME hex during the event, records which alarm bits were set, and prompts the operator for which alarm indicators the device screen showed (both LCDs have overload/fault icons; the EL100V2 also keeps a fault-history page)

#### Scenario: Overload suggestion derived from the device rating
- **WHEN** the overload check is offered on an EL100V2 (rated 1800 W)
- **THEN** the prompt states the 1800 W rating and suggests a load computed above it, with an example appliance
- **THEN** no prompt text claims a different rating for this or any other model

#### Scenario: No rating, no overload offer
- **WHEN** the connected device declares no rated AC output
- **THEN** the induced-overload check is not offered and the report notes why

#### Scenario: Typed confirmation required
- **WHEN** an induced-condition check is reached and the operator does not type the confirmation phrase
- **THEN** the check is recorded as `skipped` and no instruction to create the condition is given
