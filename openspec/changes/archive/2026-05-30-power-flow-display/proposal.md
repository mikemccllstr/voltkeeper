## Why

The status command's POWER section shows five flat unsigned numbers with sign
annotations like `(neg=export)`, forcing the user to mentally reconstruct where
power is flowing. There is no battery row, no totals, and no indication that
`Discharging` at 100% SOC is normal and expected when DC loads are present.

## What Changes

- Both `_print_status` (compact) and `_print_verbose` (full) replace the flat
  power list with an **IN / OUT grouped layout** with per-row labels and IN/OUT
  totals.
- A **derived battery row** is computed from conservation of energy
  (`battery = ac + dc − pv − grid`). Positive = discharging, negative = charging.
  No new register is needed.
- Grid export, AC export, and battery charging appear as **OUT rows** when active.
- **Compact (`status`)**: zero-value rows are hidden; section always rendered when
  any power register is present.
- **Verbose (`status --verbose`)**: all rows shown even at 0 W, so the user can
  confirm which meters are live.
- `docs/source/user-guide/status.md` gains a **Power readings** section explaining
  the layout, the battery derivation formula, and why `Discharging` at 100% SOC
  is normal.

## Capabilities

### New Capabilities

- `status-power-display`: IN/OUT grouped power layout for the status command —
  derived battery row, per-direction totals, compact vs verbose zero-hiding.

### Modified Capabilities

<!-- none — the existing status spec (if any) does not cover the power section layout -->

## Impact

- `src/voltkeeper/cli.py` — `_print_status`, `_print_verbose`, new
  `_print_power_section` helper
- `docs/source/user-guide/status.md` — new Power readings section
