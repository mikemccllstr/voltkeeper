## Context

Voltkeeper's device classes model writable fields via `WRITABLE_FIELD_NAMES` and a typed `control_struct` (BoolField, EnumField, UintField, DecimalField, etc.). The `build_setter_command` method converts a field name + value into a `WriteSingleRegister` BLE command. The `parse()` method converts raw register bytes into a dict of field values.

Range annotations on numeric fields (e.g., `range=(0, 100)`) are derived from the Android APK's UI constraints, which may be narrower than what the hardware actually accepts. Most non-AC2A device classes carry `TODO(hardware): verify` comments.

There is no existing mechanism for a user to systematically test voltkeeper's device model against a real device and produce a shareable result.

## Goals / Non-Goals

**Goals:**
- Six-tier progressive integration test against a live device over BLE
- Tiers 1–3 fully automatic; tiers 4–6 prompted at tier boundary (one prompt per tier, not per field)
- Range boundary probing to discover true hardware limits vs. declared ranges
- Structured YAML output with SN and BLE address scrubbed, suitable for GitHub issue submission
- After any tier with failures: recommendation to share results before proceeding
- Single global `FIELD_TIERS` dict as the classification authority — no per-device tier lists

**Non-Goals:**
- Register fuzzing / sweep of undocumented addresses (that's `probe`/`annotate`)
- Firmware upgrade or factory reset verification (tier 6 is present but optional)
- Automated CI integration (this is a human-in-the-loop command)
- Modifying device class code based on verify results (that's a manual follow-up)

## Decisions

### Tier structure

Six tiers, run in sequence, stopping on user decline at supervised tiers:

| Tier | Mode      | What runs                                                          |
|------|-----------|--------------------------------------------------------------------|
| 1    | Automatic | Poll all status/control blocks; parse; check all expected fields present |
| 2    | Automatic | For each writable field: write current value (or safe default); re-read; verify match |
| 3    | Automatic | For each tier-2 field: probe-write (toggle bools, cycle enums, probe numeric boundaries); restore |
| 4    | Prompted  | Load-affecting fields: ac_output, dc_output, ctrl_grid, ctrl_feed, power_lifting, ac/dc_eco_mode |
| 5    | Prompted  | Operating-mode fields: working_mode, ups_mode |
| 6    | Prompted  | Irreversible: factory_reset, system_power, power_off |

One prompt before each supervised tier group (not per-field). If the user declines, the tier is recorded as `skipped (user declined)` and the command continues to the next tier boundary.

### Global field risk classification

A single `FIELD_TIERS: dict[str, int]` in `src/voltkeeper/core/verify.py` maps field names to their tier (4, 5, or 6 only — anything not listed defaults to tier 2/3). Applied at runtime by intersecting with each device's `WRITABLE_FIELD_NAMES`.

```python
FIELD_TIERS = {
    # Tier 4 — load-affecting
    "ac_output": 4, "dc_output": 4, "ctrl_grid": 4, "ctrl_feed": 4,
    "power_lifting": 4, "ac_eco_mode": 4, "dc_eco_mode": 4,
    # Tier 5 — mode-changing
    "working_mode": 5, "ups_mode": 5,
    # Tier 6 — irreversible
    "factory_reset": 6, "system_power": 6, "power_off": 6,
}
```

`charging_mode` is *not* listed — it defaults to tier 3 (brief switch, auto-restores).

**Alternative considered:** per-device tier lists in each device class. Rejected — duplicates classification logic across 15+ classes for no gain, since field names are semantically stable across devices.

### Tier 2 — safe default for unreadable fields

If a writable field's address is not present in the parsed status result (field not in any polled block), we cannot read its current value. Rather than skipping, we write a safe default and document it:
- `BoolField`: write `False` (0)
- `EnumField`: write first member (lowest value)
- `UintField` / `DecimalField`: write `range_min` if range declared, else `0`

This gives us write-path validation even for fields that don't appear in status. The output records `read: null, wrote: <default>, note: "no status value — used safe default"`.

**Alternative considered:** skip unreadable fields entirely. Rejected — skipping silently hides useful information about whether the write path works.

### Tier 3 — range boundary probing

For numeric fields with a declared range `(low, high)`, probe in this order (each followed by restore-and-verify):

```
current, low, high, low-1, high+1, high+2, 0, 65535
```

The output records each probe's `wrote` / `readback` / `result` (accepted | rejected | no-readback). A `discovered_range` is inferred as the outermost values that were accepted. A `range_discrepancy` flag is set when `discovered_range` differs from `declared_range`.

For bools: toggle (write `not current`) and restore.  
For enums: cycle through all members in order, restoring after each.  
For numeric fields *without* a declared range: probe `0`, `255`, `65535`, and `current ± 1`.

**Restore failure handling:** If the restore write after a probe fails (readback doesn't match original), stop tier 3 for that field immediately, record `restore_failed: true`, and report the field's last known state. Do not abort the entire run — continue with the next field.

### Output format

YAML file, default name `verify-<MODEL>-<DATE>.yaml`. SN replaced with `VKTEST000000`; BLE address replaced with `AA:BB:CC:DD:EE:FF`. Structured so each tier is a top-level key containing per-field results.

**TOML considered:** rejected — TOML handles nested structures with less readability at this depth. YAML is already used elsewhere in the project (profiles, probe output).

### BLE connection management

Reuse the same BLE connection throughout the entire verify run (same pattern as `status --continuous`). If the connection drops mid-run, record the disconnect point in the output and exit with a non-zero status. Do not auto-reconnect — a reconnect mid-test would invalidate the sequence.

### CLI options

```
voltkeeper verify <address>
  --output FILE    Write report to FILE (default: verify-MODEL-YYYY-MM-DD.yaml)
  --tier N         Run through tier N only (1–6). If N >= 4, prompts still appear.
  --yes            Pre-consent to all supervised tiers (for developer use)
  --no-scrub       Omit SN/address scrubbing (personal use only)
```

## Risks / Trade-offs

**Restore failure leaves device in unexpected state** → Mitigated by documenting the last known state in the report and stopping tier 3 for that field. The user is informed immediately.

**Tier 3 range probing may be slow on BLE** → Each probe is a write + read round-trip (~200–500 ms). A device with 20 numeric fields × 8 probes each = 160 BLE operations, potentially 60–80 seconds. Acceptable for a deliberate verification run; document expected duration.

**Safe defaults may not be "safe" for all fields** → e.g., writing `system_time = 0` would set the clock to epoch. Fields where the safe default is known to be problematic should be listed in a `SKIP_TIER2` set and documented as "skipped — no safe default."

**Tier 6 consent UX** → Factory reset requires a strong confirmation. Use typed string (`"I understand this is irreversible"`) rather than a simple y/N to prevent accidental execution.

## Open Questions

- Should tier 3 probe writes run for tier 4/5/6 fields too (after their supervised consent is given), or only for tier 2 fields? Current design: probe writes only on tier 2 fields (automatic); tier 4/5/6 get identity-write verification only.
- Should the report include raw register hex alongside parsed values? Useful for debugging parse bugs, but adds verbosity. Could be `--verbose` flag.
