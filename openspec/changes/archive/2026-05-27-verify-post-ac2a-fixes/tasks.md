## 1. Code fixes

- [x] 1.1 Add `ctrl_led` to `SKIP_AUTO` frozenset in `verify.py` and update docstring
- [x] 1.2 Add `range=(0, 255)` to `lcd_timeout` field registration in `ac2a.py`
- [x] 1.3 Add `@unique` decorator to `EmsCtrlMode` in `commands.py`
- [x] 1.4 In `run_tier3_numeric`, filter probe values > 255 when the field is a `Uint8Field`

## 2. Tests

- [x] 2.1 Add test: `ctrl_led` excluded from `build_tier_plan` automatic tiers
- [x] 2.2 Add test: `run_tier3_numeric` with a `Uint8Field` does not probe 65535
- [x] 2.3 Add test: `lcd_timeout` write command rejects values > 255

## 3. Documentation

- [x] 3.1 Add "Result codes" subsection to `verify.md` Output section explaining `accepted`, `no-readback`, and `rejected`
- [x] 3.2 Add `range_discrepancy` explanation to the same subsection
- [x] 3.3 Add a note in `verify.md` that the output file is written to the current directory

## 4. Quality gate

- [x] 4.1 Run `mise run check` and confirm all pass
