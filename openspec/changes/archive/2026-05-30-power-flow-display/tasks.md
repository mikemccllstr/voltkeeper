## 1. Helper function — `_print_power_section`

- [x] 1.1 Write failing test: compact mode hides zero PV row
- [x] 1.2 Write failing test: compact mode shows non-zero battery (discharging) in IN
- [x] 1.3 Write failing test: compact mode shows grid export in OUT
- [x] 1.4 Write failing test: compact mode shows battery (charging) in OUT
- [x] 1.5 Write failing test: verbose mode shows PV row even when 0 W
- [x] 1.6 Write failing test: IN Total and OUT Total match expected sums
- [x] 1.7 Confirm all new tests fail before implementation
- [x] 1.8 Implement `_print_power_section(home, indent, show_zeros)` with derived battery, row classification, and totals
- [x] 1.9 Confirm all new tests pass

## 2. `_print_status` — compact display

- [x] 2.1 Remove the existing `DC Load / AC Load / Total Load` block
- [x] 2.2 Call `_print_power_section(home, indent="  ", show_zeros=False)` in its place

## 3. `_print_verbose` — verbose display

- [x] 3.1 Remove the existing flat `# ── Power Meters ──` block
- [x] 3.2 Call `_print_power_section(home, indent="    ", show_zeros=True)` in its place, with matching section header style

## 4. End-to-end confirmation

- [x] 4.1 Run full test suite; confirm all tests pass

## 5. Documentation — status.md

- [x] 5.1 Add **Power readings** section to `docs/source/user-guide/status.md` explaining the IN/OUT layout
- [x] 5.2 Document the battery row derivation formula (`battery = ac + dc − pv − grid`)
- [x] 5.3 Explain why `Discharging` at 100% SOC is normal when DC loads are active
- [x] 5.4 Add note that the battery row is derived, not directly measured
