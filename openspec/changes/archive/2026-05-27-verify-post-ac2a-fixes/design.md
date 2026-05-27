## Context

Five gaps were found during the first real hardware verify run against an AC2A. The changes are independent of each other and each touches a single well-defined location. No new abstractions are needed; these are targeted corrections.

## Goals / Non-Goals

**Goals:**
- Eliminate `ctrl_led` noise from verify tier 2/3 output
- Prevent `Uint8Field` probes from writing 0xFFFF to a shared register
- Make `lcd_timeout` write-command validation consistent with observed hardware limits
- Make `EmsCtrlMode` consistent with every other enum in `commands.py`
- Fill three documentation gaps in `verify.md`

**Non-Goals:**
- Characterizing power-limit field ranges (`chg_max_voltage` etc.) — deferred to a dedicated APK research change
- Addressing `sys_low_power`/`soc_holding_*` accepting 101/102 — deferred
- Any changes to tier 4/5/6 behavior

## Decisions

**`ctrl_led` → `SKIP_AUTO`**
`ctrl_led` (register 2007) is a write-only toggle: writing 1 triggers a state change but the register always reads back its prior value. This is the same exclusion reason as `system_time`. Adding it to `SKIP_AUTO` removes the always-`no-readback` entry from tier 2/3 results without losing any safety signal.

**Uint8Field probe cap**
`run_tier3_numeric` currently probes `[ci, 0, 255, 65535, ci+1, max(0, ci-1)]` for range-less fields and appends 65535 unconditionally for range-declared fields. For a `Uint8Field` (one byte of a 16-bit register), writing 65535 (0xFFFF) sets both bytes of the register — the adjacent byte may belong to a different field.

The fix: after building the probe sequence, filter out any value > 255 when the field is a `Uint8Field`. The `Uint8Field` class is importable from `voltkeeper.core.struct`.

Alternative considered: cap based on declared range hi — rejected because some `Uint8Field`s have no declared range, and the cap should be structural (field type), not declarative.

**`lcd_timeout` range=(0, 255)**
Hardware rejects 65535 and accepts 0–255. Declaring the range in `ac2a.py` serves two purposes: (1) the write command will now raise `ValueError` for out-of-range values; (2) the tier-3 probe will use the range-aware sequence instead of the 65535-inclusive fallback.

**`@unique` on `EmsCtrlMode`**
Every other Enum subclass in `commands.py` uses `@unique`. The missing decorator is an oversight. No behavior change — the current values (0, 3, 4, 5, 8) are already unique.

**`verify.md` additions**
Three gaps found in the docs during hardware testing:
1. `no-readback` is never defined — add a "Result codes" subsection to the Output section
2. `range_discrepancy` appears in the YAML but is undocumented — add to the same subsection
3. No mention of where the output file lands or that users might want to gitignore it — add a note after the output format description

## Risks / Trade-offs

**Uint8Field probe cap changes existing tier-3 output** — any device that previously accepted 65535 on a `Uint8Field` will no longer be probed at that value. This is intentional: the result was ambiguous anyway (the device may have been accepting 0xFF from the high byte). The output will be strictly more correct.

**`lcd_timeout` range tightens tier-3 probing** — with `range=(0, 255)`, the probe sequence switches to the range-aware path `[ci, 0, 255, 254, 256, 257, 0, 65535]`. 65535 is still included in the range-aware sequence as an out-of-bounds check. Hardware will reject it as before.

## Open Questions

None. All decisions are resolved.
