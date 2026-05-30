## Context

`run_tier3_numeric` currently builds a hand-crafted probe sequence
(`[current, low, high, low-1, high+1, high+2, 0, 65535]`) and infers a
`discovered_range` from the min/max of accepted values. This is sufficient to
detect obvious boundary mismatches but cannot confirm interior values, cannot
discover ranges that don't start at 0, and produces a `probes` list that scales
badly with any future exhaustive approach.

Empirical data from two AC2A verify runs shows:
- `sys_low_power` (declared 0–100) accepts 101, 102, and 65535 — the sparse
  probe caught this because 65535 was in the sequence, but only by accident.
- `dc_eco_power` (no declared range) rejects 0 and accepts only values near the
  current setting — the sparse probe never found the true lower bound.
- `dc_eco_auto_off_time` (no declared range) rejects 0 and 5, accepts 3 and 4 —
  a range of [3, 4] that the sparse probe partially discovered but could not
  fully confirm.

All declared ranges in the codebase have `high ≤ 255`, making an exhaustive
0–255 sweep practical (≤256 probes per field, each with write + readback +
optional restore = ≤768 BLE operations).

## Goals / Non-Goals

**Goals:**
- Confirm every value in 0–255 is either accepted or rejected, for every
  numeric field in automatic tiers.
- Correctly discover ranges that do not start at 0.
- Stop probing once confident the upper boundary has been found (post-range
  early termination).
- Emit a compact, self-contained output that a Claude/agent instance can use to
  update device models without reading the source code.
- Keep bool and enum probing unchanged.

**Non-Goals:**
- Probing values above 255 (no current field has a declared `high > 255`; this
  can be revisited when such a field is added).
- Detecting non-contiguous accepted ranges (we assume firmware enforces a single
  contiguous accepted interval).
- Changing tiers 1, 2, or 4–6.

## Decisions

### D1: Always sweep 0–255, regardless of declared range

**Decision:** Use a single uniform strategy — sweep every integer from 0 to 255
in ascending order — for both known-range and no-range fields.

**Rationale:** A separate "known-range" sequence was tempting (probe only
declared range + a boundary band), but it would miss discoveries outside the
boundary band and requires more branching logic. A uniform sweep is simpler,
easier to test, and the runtime cost (~768 BLE ops × ~150 ms ≈ 2 min per field)
is acceptable for an infrequently-run verification command.

**Alternative considered:** Binary search to find boundaries first, then
exhaustive verification of the found range. Rejected because it assumes
monotonic device behavior that is likely but not guaranteed, adds complexity, and
does not save enough time to justify the added code.

### D2: Pre/in/post-range state machine with 2-rejection early termination

**Decision:** Track a three-state machine across the sweep:

```
pre_range  →  in_range  →  post_range
            (first accept)  (first reject after accept)
```

Early termination fires only in `post_range` after 2 consecutive rejections.
`pre_range` never terminates early, so ranges starting above 0 are discovered
correctly.

**Rationale:** The user confirmed we can assume contiguity — once we've seen
two consecutive rejections after the last accept, all remaining values will also
be rejected. Applying the termination rule only in `post_range` is the minimal
correct rule given that assumption.

### D3: Skip restore when readback already equals original value

**Decision:** After a probe where `readback == current_int`, skip the restore
write. The device's state is already correct.

**Rationale:** Devices that silently reject a write return the old register
value on readback. Restoring to a value that's already there wastes a BLE
round-trip. This optimization halves the BLE traffic for rejected probes, which
is the common case for out-of-range values.

### D4: Replace `probes` list with summary fields for numeric fields

**Decision:** For numeric fields, do not populate `probes: list[ProbeResult]`.
Instead emit six summary fields:

| Field | Type | Meaning |
|---|---|---|
| `current_value` | `int` | Register value before probing |
| `probes_count` | `int` | Total probes executed |
| `probed_range` | `[int, int]` | Actual sweep extent `[0, N]` |
| `probe_cap_hit` | `bool` | True when sweep ended at 255 with device still accepting — upper bound is "≥255, possibly higher" |
| `declared_range` | `[int, int] \| null` | What the device model currently declares |
| `in_range_rejected` | `list[int]` | Declared-in-range values the device rejected (anomaly list) |
| `discovered_range` | `[int, int] \| null` | Min/max of accepted values (unchanged field, kept) |
| `range_discrepancy` | `bool \| null` | Whether discovered ≠ declared (unchanged field, kept) |

Bool and enum fields keep the existing `probes` list.

**Rationale:** 256 individual `ProbeResult` entries would be unreadable in YAML
and carry no additional information beyond what the summary fields convey.
`in_range_rejected` is the key anomaly list — it directly identifies holes in
the declared range. `probe_cap_hit` is essential for a downstream Claude/agent
to know whether the upper bound is confirmed or merely "at least 255."

### D5: `status: fail` means only restore failure

**Decision:** A numeric field's `status` is `fail` only when `restore_failed`
is true. Range discrepancies, in-range rejections, and out-of-range acceptances
set `status: pass` and are recorded as findings in the summary fields.

**Rationale:** The verify command's purpose is to discover what the hardware
actually supports, not to assert conformance to a pre-specified range. Marking
a discovery as a failure conflates measurement with judgement. A restore failure
is a genuine failure because it leaves the device in an unknown state.

### D6: `hardware-data/` folder for permanent verify output storage

**Decision:** Add `hardware-data/` at the project root, tracked by git. Move
existing verify YAMLs there. Update the CLI default output path to
`hardware-data/verify-<MODEL>-<DATE>.yaml`. Add `hardware-data/README.md`
explaining the folder's purpose.

**Rationale:** Verify files are primary empirical evidence about real hardware
behaviour. They should be version-controlled alongside the code they inform.
The folder name is descriptive without being CLI-command-specific (future
non-verify hardware data could also live here).

**Alternative considered:** Leave output in the current directory and add
`.gitignore` entry. Rejected — this loses the historical record and makes it
impossible to track which hardware was tested with which code version.

## Risks / Trade-offs

**Runtime per field is ~2 minutes at 150 ms/BLE-op** → Acceptable because
verify is a rare, deliberate operation. Document the expected duration in the
user guide.

**Contiguity assumption could be wrong** → If a device has a non-contiguous
accepted range (accepts 10–20 and 40–50), early termination would stop after
seeing 21–22 rejected and never discover 40–50. Mitigation: clearly document
the assumption in the interpretation guide; if a future device violates it,
revisit the algorithm.

**`probe_cap_hit: true` leaves upper bound uncertain** → The guide must
explicitly instruct Claude/agent instances not to write `range=(0, 255)` in the
model when `probe_cap_hit` is true — only write what is confirmed. For now,
annotate such fields with a `# TODO(verify): upper bound uncertain` comment.

**CLI default output path change** → Existing scripts that expect
`verify-*.yaml` in the current directory will break. This is acceptable; the
`--output` flag remains available for explicit paths.

## Open Questions

None — all design decisions were resolved during the explore session.
