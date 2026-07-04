# verify

Run a six-tier integration test against a connected Bluetti device and write a
scrubbed YAML report suitable for filing a GitHub issue.

```bash
voltkeeper verify AA:BB:CC:DD:EE:FF
```

The command connects to the device, runs tiers 1–3 automatically, then prompts
once per supervised tier (4–6) before continuing. When it finishes a YAML
report is written to the `hardware-data/` folder.

## Command syntax

```bash
voltkeeper verify <address> [options]
```

| Option                     | Description                                                                                                       |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `<address>`                | BLE MAC address (or UUID on macOS) of the target device                                                           |
| `-o`, `--output FILE`      | Override the default report filename                                                                              |
| `--tier N`                 | Stop after tier N (remaining tiers recorded as skipped)                                                           |
| `--yes`                    | Pre-consent to all supervised tiers — no prompts                                                                  |
| `--no-scrub`               | Write real serial number and BLE address to the report                                                            |
| `--ground-truth`           | Attended mode: compare device-display values against parsed registers                                             |
| `--skip-category CATEGORY` | Skip a ground-truth category (repeatable). Valid: `observations`, `load_actuations`, `mode_actuations`, `induced` |

## The six tiers

Each tier builds on the previous one. Tiers 1–3 run automatically; tiers 4–6
each require a one-time confirmation before testing begins.

### Tier 1 — Read and parse

Polls every register block (`polling_commands` and `control_commands`) and
verifies that each response can be parsed without error. This confirms the
device speaks the expected protocol and that the register map matches reality.

### Tier 2 — Identity writes

For each writable field, reads the current value and writes it back unchanged.
A single-register read verifies the write was accepted. The write is safe: the
device state does not change.

If a field's current value is not available from the tier-1 parse (for example,
a register that does not appear in polling blocks), a safe default is used:
`False` for boolean fields, the lowest declared enum member for enum fields, and
the declared minimum or `0` for numeric fields.

### Tier 3 — Probe writes

For each automatic field, exercises the full range of values:

- **Boolean** — toggles the field and restores the original value.

- **Enum** — cycles through every declared member, restoring after each.

- **Numeric** (`UintField`, `DecimalField`, `Uint8Field`) — performs an
  exhaustive ascending sweep from 0 to 255.

  The sweep uses a three-state machine to stop early once the accepted range
  has been found:

  | State        | Condition                                    | Early termination                                     |
  | ------------ | -------------------------------------------- | ----------------------------------------------------- |
  | `pre_range`  | No value accepted yet                        | Never — ranges that start above 0 are found correctly |
  | `in_range`   | At least one value accepted                  | Never                                                 |
  | `post_range` | At least one rejection after the last accept | After 2 consecutive rejections                        |

  After each probe the original value is restored if needed. When the
  device silently rejects a probe (readback equals the original value), the
  restore write is skipped.

  **Expected runtime**: approximately 2 minutes per numeric field at typical
  BLE throughput (~150 ms per BLE operation).

If restoring a field fails, `restore_failed: true` and the last known value are
recorded for that field, and testing moves on to the next field.

### Tier 4 — Load-affecting fields (supervised)

Fields whose toggle directly affects connected loads: `ac_output`, `dc_output`,
`ctrl_grid`, `ctrl_feed`, `power_lifting`, `ac_eco_mode`, `dc_eco_mode`.

The command prints a risk description and asks `Continue? [y/N]` before
running. Pressing Enter or typing `n` records tier 4 as
`skipped (user declined)` and moves on to tier 5.

### Tier 5 — Mode-changing fields (supervised)

Fields that change the device operating mode: `working_mode`, `ups_mode`.

Same prompt-and-continue mechanic as tier 4.

### Tier 6 — Irreversible fields (supervised)

Fields that could have irreversible effects: `factory_reset`, `system_power`,
`power_off`.

Instead of a yes/no prompt, the command requires you to type the exact phrase:

```
I understand this is irreversible
```

Anything else (including pressing Enter) records tier 6 as
`skipped (user declined)`.

## Ground-truth mode

The `--ground-truth` flag enables an attended verification mode that compares
the device's own display against parsed register values. This catches
interpretation errors — wrong decimal scales, swapped enum labels, or
misassigned registers — that write/readback verification alone cannot detect.

All ground-truth prompts use consistent terminology:

- **"the Bluetti unit"** — the power station itself
- **"your appliance" / "the load"** — equipment plugged into the unit
- **"the AC outlets"**, **"the DC ports"** — explicit output names, never a
  bare "output" or "device" where the referent is ambiguous

Ground-truth mode runs in two phases. **Passive observations** run immediately
after tier 1, before any tier performs writes, so the operator's readings and
secondary sources describe unmutated device state. **Actuate-and-confirm and
induced-condition checks** run after whatever tiers execute — including under a
`--tier` limit: actuate-and-confirm checks follow tier consent, and a tier
that never ran was never consented, so its fields record `skipped`.

The observation phase is structured as an **app handoff**:

1. Voltkeeper disconnects BLE and invites you to open the BLUETTI app and
   connect to the device. If you don't have the app installed, you can proceed
   LCD-only: each prompt will ask you to type what the device screen shows
   instead.
1. Each observation prompt shows the value voltkeeper parsed (e.g. "voltkeeper
   parsed: 94") and asks you to type **exactly what the app or screen shows** —
   even if it differs. This anchors the prompt while keeping your response
   independent.
1. After the last observation, voltkeeper asks you to return the app to its
   device-list screen, then reconnects for tier 2. If reconnection fails
   (the app is still holding the connection), it retries with operator guidance.
   If reconnection cannot be established, tier-1 and observations are preserved
   in the report and tiers 2+ are recorded as skipped.

Observations read from the live app are recorded with source `app_live`.
Voltage readings still use `multimeter` or `multimeter_or_app` sources when the
app is not used.

The ground-truth session has three phases:

1. **Passive observations**: the tool prompts for values shown on the device's
   own screen (SoC, output/input watts, AC/DC output state, AC output frequency,
   charging mode) and compares them against
   parsed values with per-quantity tolerances. Where the device screen shows a
   total (output/input watts), the tool compares against the sum of the
   corresponding parsed fields. Firmware versions are compared under the
   device's own display format (raw register ÷ 100). Quantities not shown on
   any device LCD (voltages) are prompted with an explicit request to use a
   multimeter or a pre/post-session app screenshot, and recorded as secondary
   source observations.

1. **Actuate-and-confirm**: the tool follows a five-beat script for each writable
   field:

   1. **Announce**: what is about to change, naming the specific output or
      setting in plain language (e.g. "the AC outlets", never a bare "output").
      If the field carries a caution (e.g. AC output frequency), it is shown
      here.
   1. **Watch-for**: what the operator should see on the Bluetti unit's display
      and on any connected appliance.
   1. **Ready gate**: the operator confirms they are watching before any write.
      For normal fields: press Enter to proceed or type `s` to skip. For
      **caution-gated fields** (e.g. AC output frequency): type `y` to proceed
      despite the caution, or press Enter to skip — the default is skip.
   1. **Actuate**: the tool writes the value and reads it back (unchanged logic).
   1. **Confirm**: the operator reports what the device UI shows with three
      accepted outcomes: `y` (yes, confirmed), `n` (no, denied),
      or `unsure` (cannot tell). A denial with a matching readback is the
      signature of an enum label swap (e.g. SILENT/TURBO). An `unsure`
      response is recorded distinctly and does NOT count as a denial —
      it never carries the label-mapping-error note.

   Fields the device UI cannot display are recorded as
   `not_confirmable_on_device`.

1. **Induced-condition checks** (AC overload only): the operator applies a
   resistive load above the device's rated output, the tool captures alarm/fault
   registers and raw HOME block hex during the event, and the operator records
   which alarm indicators appeared on the device display. This validates
   alarm-bit decoding that is otherwise untestable without a physical fault.
   Each induced check requires typed confirmation (tier-6 pattern) and documents
   why the condition is within the device's designed protections.

### When to run it

Ground-truth mode is for characterization sessions — new device bring-up,
firmware revision re-characterization, or suspected interpretation bugs. It is
not intended for routine verification. Every prompt is individually skippable.

### Safety notes for induced conditions

- **Only use AC overload**: the device's over-current protection is
  non-destructive and self-resetting. Do not short outputs, bypass protections,
  or create fault conditions the device was not designed to handle.
- **Load computed from the device's rated output**: the suggested overload
  wattage is ~15% above the device's declared rated AC output (sourced from
  the manufacturer's user manual), with a household example appliance
  (space heater, incandescent bulbs). The tool derives this from the model —
  no per-model wattages are hardcoded.
- **Typed confirmation required**: the tool will not instruct you to create
  the condition until you type the exact confirmation phrase.
- **Stay with the device**: induced checks are attended by design. Watch for
  unexpected behaviour and be ready to disconnect the load.

### Session checklist

1. Connect the device and position it so the screen is visible.
1. Set up a known steady load (e.g., a lamp drawing a known wattage).
1. Run `voltkeeper verify <address> --ground-truth`.
1. After tier 1, the observation phase begins: voltkeeper disconnects BLE. Open the
   BLUETTI app and connect to the device (or choose LCD-only). Answer each
   observation prompt with the app or screen reading.
1. Return the app to its device list and press Enter; voltkeeper reconnects.
1. Tiers 2–6 run as normal (consent for supervised tiers).
1. The actuations and induced-checks phases run after the tiers.
1. The restore audit checks whether any settings changed from the tier-1 baseline.
1. The report is written — share it in a GitHub issue.

### Report section

When `--ground-truth` is active, the report includes a `ground_truth` section
alongside the tier results:

```yaml
ground_truth:
  observations:
    - field: soc
      prompt: State of Charge (%)
      source: device_screen
      status: match
      observation: 85.0
      parsed: 85
      raw_ref: "100"
    - field: pack_voltage
      prompt: Pack voltage (V) — multimeter or pre/post-session app screenshot
      source: multimeter_or_app
      status: mismatch
      observation: 53.5
      parsed: 5.35
      inferred_scale: "÷10"
      note: matches raw value at ÷10
  actuations:
    - field: charging_mode
      prompt: Device set to turbo (was standard) — does the device display confirm this change? ...
      wrote: turbo
      readback: turbo
      device_confirmed: false
      note: denial with readback match — possible label mapping error
  induced_checks:
    - condition: ac_overload
      status: captured
      alarm_bits: [1, 3]
      raw_hex: "0aaa0013..."
      device_indicator: Overload icon lit
```

### `--yes` and `--ground-truth` are mutually exclusive

`--ground-truth` is an attended mode by design. Combining it with `--yes`
(unattended) is rejected before connecting. A `--yes` report never contains a
`ground_truth` section.

### Actuation tier gating

Actuate-and-confirm checks (phase 2) respect the same risk-tier classification
as the main verify tiers. Tier-6 fields (`factory_reset`, `system_power`,
`power_off`) are never actuated. Tier-4 and tier-5 fields are only actuated
when their tier was consented to during the run. If you declined tier 4 during
verify, the actuation phase skips all tier-4 fields. The same applies under a
`--tier` limit: a tier that never ran was never consented, so its fields are
recorded as skipped.

## Category skip controls

At the start of a ground-truth session, the operator is offered a category menu:

- **Passive observations** (screen readings)
- **Output & load actuations** (tier-4 fields)
- **Operating mode actuations** (tier-5 fields)
- **Induced conditions** (e.g. overload test)

All four are enabled by default. Deselected categories record
`skipped (operator category selection)` without prompting per item.

The `--skip-category` CLI option pre-answers the menu:

```bash
voltkeeper verify AA:BB:CC:DD:EE:FF --ground-truth --skip-category induced
```

This is repeatable — use it for non-interactive repeat runs.

## Restore audit

Any session that executed tier 2 or deeper ends with a restore audit: voltkeeper
re-reads the device's control registers, compares every writable field's value
against the tier-1 baseline, and records any deviations in the report under a
`restore_audit` section.

```yaml
restore_audit:
  status: deviations_found
  deviations:
    - field: ac_eco_power
      was: 10
      now: 34
```

A clean run records:

```yaml
restore_audit:
  status: clean
```

A tier-1-only run records `status: not_applicable` with no re-read performed.
The audit runs regardless of `--yes` (report-only when unattended). It does
**not** attempt corrective writes — the operator decides how to proceed.

## Progress display

After each tier, the command prints a one-line summary:

```
Tier 1  ████████  23/23  ✓
Tier 2  ████████  19/19  ✓
Tier 3  ████████  19/19  ✓
```

If a tier has failures:

```
Tier 2  ████░░░░  16/19  ✗
⚠ 3 issue(s) found — consider sharing the report before continuing
```

## Output report

The report is written to
`hardware-data/{verify|verify-ground-truth}_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml`
by default, with the mode component set to `verify-ground-truth` for
`--ground-truth` runs. The timestamp is the session start time in UTC at
minute precision. Existing files are never overwritten: when the target
path already exists the writer appends `_v<N>` before `.yaml`, choosing
the smallest N ≥ 2 that yields a non-existent path. Use `--output` to
specify a custom path.

### Scrubbing

By default the real serial number is replaced with `VKTEST000000` and the BLE
MAC address with `AA:BB:CC:DD:EE:FF` before the report is written. Use
`--no-scrub` to disable scrubbing if you are comfortable sharing your device
identifiers.

Raw block payloads in tier 1 are also scrubbed: bytes belonging to
serial-number fields (located via the device's struct field definitions, for
both V1 and V2 register layouts) and the IoT block's module serial, MAC, and
IP bytes are zeroed in the recorded hex. `--no-scrub` bypasses raw scrubbing
along with the text scrubbing.

### Raw payload capture

Every tier-1 block entry records the raw hex payload returned by the device in
a `raw` field. This is interpretation-free ground truth — the bytes the device
sent, before any parsing. Raw payloads are recorded for:

- Plain reads (`ReadHoldingRegisters`): one `raw` field per block.
- TLV-bundled reads (`TlvReadHoldingRegisters`): one `raw` field per register
  address in the bundle, recorded from each TLV item's payload. One item's
  parse failure does not discard the other items' results.
- Parse failures: the raw hex is recorded alongside the error so the bytes that
  caused the failure are preserved.

Raw scrubbing (see above) is applied to these payloads before the report is
written so that captured bytes are safe to commit.

One exception: if a TLV response is so malformed it cannot be split into
items, its bytes are not any single block's payload and cannot be scrubbed
byte-precisely. Scrubbed reports omit such bundles (the error is still
recorded); with `--no-scrub` the bundle hex appears under `raw_bundle`
instead of `raw`.

### Promoting a capture to a test fixture

Captured raw hex can be promoted into a conftest fixture for parse tests:

1. Run `voltkeeper verify <address>` on the target device.
1. Open the report in `hardware-data/` and find the block you need under
   `tier_1.blocks`.
1. Copy the `raw` hex string into a `_HEX` constant in `tests/conftest.py`,
   following the existing AC2A fixtures as a pattern.
1. Document the capture-time device state in a comment: battery level, AC load,
   PV input, charging status, and any relevant operating mode. See the
   `tests/conftest.py` AC2A fixture comments for the convention.
1. Write a `pytest.fixture` that returns `bytes.fromhex(_HEX)` and use it in
   your parse tests.

Because verify runs scrub by default, captured bytes have serial numbers and
MAC/IP already zeroed, so fixtures created this way carry no identifiable
information.

### Report structure

```yaml
voltkeeper_version: "1.2.3"
verified_at: "2026-05-26T10:00:00+00:00"
device:
  model: AC2A
  sn: VKTEST000000
  ble_address: AA:BB:CC:DD:EE:FF
  firmware:
    arm_version: "6.05"

tier_1:
  status: pass
  blocks:
    "100":
      status: pass
      fields_parsed: 23
      raw: "0aaa00130064000201000100000000000000000000434..."

tier_2:
  status: pass
  fields:
    alarm_sound:
      status: pass
      read: false
      wrote: 0
      readback: 0
      match: true

tier_3:
  status: pass
  fields:
    alarm_sound:
      status: pass
      probes:
        - wrote: 1
          readback: 1
          result: accepted
    sys_low_power:
      status: pass
      current_value: 20
      probes_count: 258
      probed_range: [0, 255]
      probe_cap_hit: true
      declared_range: [0, 100]
      discovered_range: [0, 255]
      range_discrepancy: true

tier_4:
  status: skipped
  reason: "user declined"
  fields: {}
```

Skipped tiers are always present in the report — they are never omitted.

### Result codes

#### Bool and enum fields

Each tier-3 probe entry for bool and enum fields includes a `result` field:

- `accepted` — the value was written and the subsequent read returned the same value.
- `no-readback` — the write was accepted but the read-back did not match (the register may use write-only or toggle semantics).
- `rejected` — the write itself raised an error at the BLE/Modbus layer.

#### Numeric field summary fields

Numeric fields do not include a `probes` list. Instead they use summary fields:

| Field               | Type                   | Meaning                                                                                                      |
| ------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| `current_value`     | `int`                  | Register value before probing                                                                                |
| `probes_count`      | `int`                  | Total probe writes executed                                                                                  |
| `probed_range`      | `[int, int]`           | Actual sweep extent `[0, N]`                                                                                 |
| `probe_cap_hit`     | `bool`                 | `true` when the sweep ended at 255 with the device still accepting — upper bound is "≥ 255, possibly higher" |
| `declared_range`    | `[int, int]` or absent | Range declared in the device model (omitted when none)                                                       |
| `in_range_rejected` | `list[int]`            | Declared-in-range values the device rejected (omitted when absent or empty)                                  |
| `discovered_range`  | `[int, int]` or absent | Min/max of all accepted values (omitted when no values were accepted)                                        |
| `range_discrepancy` | `bool` or absent       | `true` when `discovered_range` differs from `declared_range` (omitted when either is absent)                 |

A numeric field's `status` is `fail` only when `restore_failed: true`. Range
discrepancies, in-range rejections, and out-of-range acceptances produce
`status: pass` — they are findings, not test failures. See
[Interpreting verify output](verify-interpretation.md) for guidance on how to
act on these findings.

### Output file

The report is written to
`hardware-data/{verify|verify-ground-truth}_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml`
by default, where the mode component is `verify` for plain runs and
`verify-ground-truth` for runs with `--ground-truth`, `<MODEL>` is the
device type, and the timestamp is the session start time in UTC at minute
precision. When the computed path already exists the writer appends
`_v<N>` before `.yaml`, choosing the smallest N ≥ 2 that makes the path
unique — existing files are never overwritten.

Use `--output` to specify a custom path; the same no-overwrite rule applies.
The `hardware-data/` folder is tracked by git so that verify runs are kept
alongside the code they inform.

## Submitting a report

After running verify, file a GitHub issue at
`https://github.com/mikemccllstr/voltkeeper/issues` and attach or paste the
YAML report. Include the device model and firmware version, which appear in
the `device` section of the report.
