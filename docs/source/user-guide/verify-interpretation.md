# Interpreting verify output

This guide explains how to read a tier-3 verify report and how to use its
findings to update device model files. It is written for two audiences:
**human developers** and **Claude/agent instances** acting on verify results.

## Overview

A verify run probes every numeric field with an exhaustive 0–255 sweep and
records what the hardware actually accepts. The result is a set of **findings**,
not a pass/fail verdict. A `status: pass` with a `range_discrepancy: true` is
normal — it means the hardware was measured and the measurement differs from
what the model currently declares.

The job after reading a verify report is to decide whether to:

1. Add a declared range where there is none.
1. Widen or narrow an existing declared range.
1. Flag an uncertain result for follow-up (e.g., `probe_cap_hit: true`).
1. Leave the model unchanged (e.g., the discrepancy is known and intentional).

## Field reference

### Numeric field summary fields

| Field               | Type         | When present                                                      |
| ------------------- | ------------ | ----------------------------------------------------------------- |
| `current_value`     | `int`        | Always                                                            |
| `probes_count`      | `int`        | Always                                                            |
| `probed_range`      | `[int, int]` | Always — actual sweep extent `[0, last_probed]`                   |
| `probe_cap_hit`     | `bool`       | Always — see below                                                |
| `declared_range`    | `[int, int]` | When device model has a declared range                            |
| `in_range_rejected` | `list[int]`  | When declared range exists AND some in-range values were rejected |
| `discovered_range`  | `[int, int]` | When at least one probe was accepted                              |
| `range_discrepancy` | `bool`       | When both `declared_range` and `discovered_range` are present     |

**`probe_cap_hit: true`** means the sweep ended at 255 with the device still
accepting values. The upper bound is "at least 255, possibly higher". Do NOT
write `range=(0, 255)` (or any range ending at 255) in the device model based
solely on this result — the true upper bound is unknown. Add a
`# TODO(verify): upper bound uncertain` comment to the field definition instead
and investigate further if precision matters.

**`probe_cap_hit: false`** means the sweep found the actual upper boundary
(post-range early termination fired at `probed_range[1]`). The
`discovered_range[1]` value is confirmed.

**`in_range_rejected`** lists values that the model declares as valid but the
hardware rejected. These are holes in the declared range. If they appear
consistently across multiple verify runs, narrow the declared range.

**`range_discrepancy: true`** means `discovered_range` differs from
`declared_range`. This is a finding, not a failure. Common causes:

- Device accepts a wider range than documented (potential model update).
- Device accepts a narrower range than documented (`in_range_rejected` will
  list the gaps).
- Current-value bias: the sweep always "accepts" the current value even if the
  device ignores the write, so a `discovered_range` that exactly contains only
  `current_value` often means nothing was actually accepted.

## Contiguous range assumption

The sweep algorithm assumes accepted values form a **single contiguous
interval**. Early termination fires in the `post_range` state after 2
consecutive rejections following the last accepted value. Given this assumption,
all values above `probed_range[1]` are inferred to be rejected.

If a device has a **non-contiguous** accepted range (e.g., accepts 10–20 and
40–50), early termination would stop after 21–22 and the 40–50 region would
never be discovered. The report would show `discovered_range: [10, 20]` with no
indication of the gap. This is a known limitation; document it with a comment
if a device is suspected of having non-contiguous ranges.

## How to update a device model

Follow these steps when a verify report shows a field that warrants a model
update.

1. **Locate the field** in `src/voltkeeper/core/devices/<model>.py`. Search for
   the field name (e.g., `dc_eco_auto_off_time`).

1. **Check `discovered_range`** in the verify report.

   - If absent: no probe was accepted — no range can be inferred.
   - If present: `[lo, hi]` is the confirmed hardware range (subject to
     `probe_cap_hit`).

1. **Check `probe_cap_hit`**.

   - `false`: `discovered_range[1]` is the confirmed upper bound. Safe to use.
   - `true`: upper bound is unknown. Do not update the declared range. Instead,
     add `# TODO(verify): upper bound uncertain, probe_cap_hit=true` to the
     field definition.

1. **Check `declared_range`**.

   - Absent: field has no declared range. If `discovered_range` is present and
     `probe_cap_hit` is false, add `range=(lo, hi)` to the field definition.
   - Present and equal to `discovered_range`: no change needed.
   - Present and different: proceed to step 5.

1. **Check `in_range_rejected`**.

   - Empty or absent: the device accepts the full declared range. If
     `discovered_range` is wider, the device accepts more than declared — you
     may widen the range if that is correct.
   - Non-empty: the listed values are holes. Narrow the declared range to
     exclude them, or document them with a comment if the behaviour is
     state-dependent.

1. **Update the field definition** with the new `range=(lo, hi)` argument.
   Only update when `probe_cap_hit` is false and the evidence is consistent
   across at least one verify run.

1. **Commit message convention**: reference the verify file that supports the
   change:

   ```
   fix(AC2A): update dc_eco_auto_off_time range to (3, 4)

   Evidence: hardware-data/verify-AC2A-2026-05-26.yaml
   ```

## Worked examples

### Example 1: No declared range, narrow discovered range

Verify report excerpt for `dc_eco_auto_off_time`:

```yaml
dc_eco_auto_off_time:
  status: pass
  current_value: 4
  probes_count: 6
  probed_range: [0, 5]
  probe_cap_hit: false
  discovered_range: [3, 4]
  range_discrepancy: null
```

Steps:

- `declared_range` is absent → no existing range.
- `discovered_range: [3, 4]`, `probe_cap_hit: false` → range is confirmed.
- Add `range=(3, 4)` to the field definition.

```python
# before
UintField("dc_eco_auto_off_time", 2015)
# after
UintField("dc_eco_auto_off_time", 2015, range=(3, 4))
```

Commit message: `fix(AC2A): add confirmed range (3, 4) for dc_eco_auto_off_time — hardware-data/verify-AC2A-2026-05-26.yaml`

______________________________________________________________________

### Example 2: Declared range, device accepts wider, probe_cap_hit true

Verify report excerpt for `sys_low_power` (declared `(0, 100)`):

```yaml
sys_low_power:
  status: pass
  current_value: 20
  probes_count: 256
  probed_range: [0, 255]
  probe_cap_hit: true
  declared_range: [0, 100]
  discovered_range: [0, 255]
  range_discrepancy: true
```

Steps:

- `probe_cap_hit: true` → upper bound unknown.
- Do NOT update range to `(0, 255)`.
- Add a comment to the field:

```python
# Device accepts at least 0–255; upper bound unconfirmed (probe_cap_hit).
# TODO(verify): run with extended probe range to confirm upper bound.
UintField("sys_low_power", 2022, range=(0, 100))
```

______________________________________________________________________

### Example 3: In-range rejections — narrow the declared range

Verify report excerpt for a field declared `(0, 10)`:

```yaml
some_setting:
  status: pass
  current_value: 3
  probes_count: 13
  probed_range: [0, 12]
  probe_cap_hit: false
  declared_range: [0, 10]
  in_range_rejected: [0, 1, 2]
  discovered_range: [3, 10]
  range_discrepancy: true
```

Steps:

- `in_range_rejected: [0, 1, 2]` — device rejects values 0, 1, 2 inside the
  declared range.
- `discovered_range: [3, 10]` — actual hardware range starts at 3.
- Narrow the declared range:

```python
# before
UintField("some_setting", 2030, range=(0, 10))
# after
UintField("some_setting", 2030, range=(3, 10))
```
