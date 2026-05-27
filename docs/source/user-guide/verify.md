# verify

Run a six-tier integration test against a connected Bluetti device and write a
scrubbed YAML report suitable for filing a GitHub issue.

```bash
voltkeeper verify AA:BB:CC:DD:EE:FF
```

The command connects to the device, runs tiers 1–3 automatically, then prompts
once per supervised tier (4–6) before continuing. When it finishes a YAML
report is written to the current directory.

## Command syntax

```bash
voltkeeper verify <address> [options]
```

| Option                | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `<address>`           | BLE MAC address (or UUID on macOS) of the target device |
| `-o`, `--output FILE` | Override the default report filename                    |
| `--tier N`            | Stop after tier N (remaining tiers recorded as skipped) |
| `--yes`               | Pre-consent to all supervised tiers — no prompts        |
| `--no-scrub`          | Write real serial number and BLE address to the report  |

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
- **Numeric with declared range** — probes the sequence
  `[current, low, high, low−1, high+1, high+2, 0, 65535]`, then infers the
  actual hardware range from accepted values. Sets `range_discrepancy: true`
  when the discovered range differs from the declared range.
- **Numeric without declared range** — probes
  `[current, 0, 255, 65535, current+1, current−1]`.

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

The report is written to `verify-<MODEL>-<YYYY-MM-DD>.yaml` in the current
directory unless overridden with `--output`.

### Scrubbing

By default the real serial number is replaced with `VKTEST000000` and the BLE
MAC address with `AA:BB:CC:DD:EE:FF` before the report is written. Use
`--no-scrub` to disable scrubbing if you are comfortable sharing your device
identifiers.

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
    sys_low_power:
      status: pass
      probes:
        - wrote: 20
          readback: 20
          result: accepted
        - wrote: 0
          readback: 0
          result: accepted
      discovered_range: [0, 100]
      range_discrepancy: false

tier_4:
  status: skipped
  reason: "user declined"
  fields: {}
```

Skipped tiers are always present in the report — they are never omitted.

### Result codes

Each tier-3 probe entry includes a `result` field:

- `accepted` — the value was written and the subsequent read returned the same value.
- `no-readback` — the write command was accepted by the device but the read-back did not match what was written (the register silently ignored the value, or uses write-only/toggle semantics).
- `rejected` — the write itself raised an error at the BLE/Modbus layer.

The `range_discrepancy` flag is set to `true` on a field when the `discovered_range` (the outermost values the hardware actually accepted) differs from the range declared in the device model. A discrepancy is not necessarily a bug — it may indicate the device accepts a wider range than documented, or that observed-valid values depend on device state.

### Output file

The report is written to the current working directory. If your project is a git repository you may want to add `verify-*.yaml` to your `.gitignore` to avoid accidentally committing test artifacts.

## Submitting a report

After running verify, file a GitHub issue at
`https://github.com/mikemccllstr/voltkeeper/issues` and attach or paste the
YAML report. Include the device model and firmware version, which appear in
the `device` section of the report.
