## MODIFIED Requirements

### Requirement: Ground-truth mode is opt-in and attended

The system SHALL provide an opt-in ground-truth mode via a `--ground-truth` flag on `voltkeeper verify` that prompts the operator for observations of the device's own UI and physical setup. The mode is attended by definition and `--ground-truth` and `--yes` are mutually exclusive: combining them SHALL be rejected with an error before connecting to the device, and a `--yes` report SHALL never contain a `ground_truth` section.

Ground-truth mode SHALL run in two phases. **Passive observations** SHALL run immediately after tier 1, before any tier performs writes, so the operator's readings and secondary sources describe unmutated device state. **Actuate-and-confirm checks and induced-condition checks** SHALL run after whatever tiers execute, including under a `--tier` limit: actuate-and-confirm checks follow tier consent — a tier that never ran was never consented, so its fields record `skipped`. Every prompt SHALL be individually skippable, recording `skipped` without affecting other checks.

The observation phase SHALL be conducted as an app handoff: voltkeeper SHALL disconnect its BLE connection, invite the operator to connect the vendor app to the unit (offering to proceed LCD-only if the operator has no app), and for each observation show the value voltkeeper parsed while asking the operator to type exactly what the app or LCD shows at that moment — even if it differs. When all observations are done, voltkeeper SHALL instruct the operator to disconnect the app (return to its device-list screen) and SHALL reconnect before tier 2, retrying with operator guidance on reconnection failure. If reconnection ultimately fails, the report SHALL still be written with tier-1 and observation results, and later tiers recorded as skipped with the connection loss noted.

At the start of a ground-truth session, the operator SHALL be offered a category selection covering observations, output/load actuations, mode actuations, and induced conditions — all enabled by default. Deselected categories SHALL be recorded as `skipped (operator category selection)` without prompting per item. The CLI SHALL accept a repeatable `--skip-category` option that pre-answers the selection for non-interactive repeat runs.

#### Scenario: Unattended runs unaffected
- **WHEN** `voltkeeper verify --yes` runs without the ground-truth flag
- **THEN** no ground-truth prompts appear and the report contains no `ground_truth` section

#### Scenario: Flags mutually exclusive
- **WHEN** `voltkeeper verify --yes --ground-truth` is invoked
- **THEN** the command exits with an error naming the flags as mutually exclusive, without connecting to the device

#### Scenario: Observations precede all writes
- **WHEN** `voltkeeper verify --ground-truth` runs with tiers 2+ enabled
- **THEN** all passive-observation prompts complete after tier 1 and before any tier-2 write is issued
- **THEN** actuate-and-confirm and induced checks run only after the tiers complete

#### Scenario: App handoff brackets the observation phase
- **WHEN** the observation phase begins
- **THEN** voltkeeper disconnects BLE and prompts the operator to connect the vendor app before the first observation
- **WHEN** the last observation completes
- **THEN** voltkeeper instructs the operator to return the app to its device-list screen, then reconnects and proceeds to tier 2

#### Scenario: Observation prompt shows the parsed value without confirming for the operator
- **WHEN** an observation prompt is shown for SoC and voltkeeper parsed 94
- **THEN** the prompt displays the parsed value 94 as what to look for and asks the operator to type exactly what the app shows, even if it differs
- **THEN** the recorded observation is the operator's entry, compared against the parsed value as usual

#### Scenario: Reconnection failure preserves the session
- **WHEN** voltkeeper cannot reconnect after the app handoff and the operator gives up after the retry prompts
- **THEN** the report is written with tier-1 and observation results intact and tiers 2+ recorded as skipped with the connection loss noted

#### Scenario: Ground truth under a tier limit
- **WHEN** `voltkeeper verify --tier 1 --ground-truth` runs
- **THEN** passive observations run after tier 1 and induced-condition checks are offered, and every tier-4/5 actuation check records `skipped` with its tier noted as not consented

#### Scenario: Category deselected up front
- **WHEN** the operator deselects "induced conditions" at the category menu (or passes `--skip-category induced`)
- **THEN** no induced-condition prompt appears and the report records the category as `skipped (operator category selection)`

#### Scenario: Skipped prompt recorded
- **WHEN** the operator skips a ground-truth prompt
- **THEN** that check is recorded as `skipped` and the session continues

### Requirement: Off-screen quantities use recorded secondary sources

Quantities the device's own screen does not display (AC output voltage, grid voltage, pack voltage — see the device-screen inventory) SHALL be prompted during the app-handoff observation phase with explicit secondary sources: the live vendor-app reading (source `app_live`, preferred — available because voltkeeper has released the BLE connection) or a multimeter reading. Each observation SHALL record its source, and prompts SHALL allow "not available", recording the field as unanchored.

#### Scenario: Pack voltage anchored by the live app
- **WHEN** the operator enters 53.5 V read live from the vendor app during the handoff and the parsed value is 530.5
- **THEN** the check is recorded as a mismatch with source `app_live`, and scale inference runs against the raw register value

#### Scenario: No secondary source available
- **WHEN** the operator has no app connection or multimeter for a voltage prompt
- **THEN** the field is recorded as unanchored and the session continues
