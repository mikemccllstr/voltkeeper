## Context

The status command has two display paths: `_print_status` (compact, default) and
`_print_verbose` (full, `--verbose`). Both currently show power data as a flat
list of unsigned numbers — `DC Load`, `AC Load`, `Total Load` in compact and
`PV Input / AC / DC Load / Grid` in verbose. Neither shows where power originates,
neither shows a battery contribution row, and the sign annotations are opaque.

The V2 register map exposes four power registers: `totalPVPower` (uint, reg 144),
`totalACPower` (signed, reg 142, pos=load, neg=export), `totalDCPower` (uint,
reg 140), and `totalGridPower` (signed, reg 146, pos=import, neg=export). There
is no battery power register — the battery contribution must be derived.

## Goals / Non-Goals

**Goals:**
- Replace the flat power list with an IN / OUT grouped layout in both display paths.
- Derive and display a battery row from conservation of energy.
- Show totals for IN and OUT so the user doesn't do arithmetic.
- Keep compact output tight (hide zero rows); show all rows in verbose.
- Document the power topology and the battery derivation in `status.md`.

**Non-Goals:**
- Adding new BLE register reads — no new polling, no latency impact.
- Surfacing `totalInvPower` (reg 148) — not needed for the user-facing picture.
- Changing any register parsing logic or device model files.
- Modifying MQTT, API, or daemon paths.

## Decisions

### D1: Derive battery power from energy conservation

**Decision:** `battery_w = ac_w + dc_w − pv_w − grid_w`

Positive result = discharging (battery is a source).
Negative result = charging (battery is a sink).

**Rationale:** The four existing registers fully constrain the balance. No new
register is needed. The formula holds for all realistic sign combinations
(verified for: grid import, PV surplus + export, battery-only, export via grid
port). The one pathological case — simultaneous export through both the grid port
and AC output port — cannot occur on the AC2A hardware.

**Alternative considered:** Show `totalInvPower` (reg 148) instead of deriving
battery. Rejected because the inverter power doesn't directly answer "how much
battery am I using?" and because it adds a register that is not yet understood
well enough to label confidently.

### D2: Shared `_print_power_section(home, indent, show_zeros)` helper

**Decision:** Extract the IN/OUT layout into a single function called from both
`_print_status` and `_print_verbose` with different `indent` and `show_zeros`
arguments.

- `_print_status` calls with `indent="  ", show_zeros=False`
- `_print_verbose` calls with `indent="    ", show_zeros=True`

**Rationale:** The layout logic and the battery derivation formula are identical
in both paths. A shared helper eliminates duplication and ensures the two displays
always agree on the formula and sign conventions. The `indent` parameter is the
only structural difference between the two call sites.

### D3: Section always renders when power registers are present

**Decision:** Show the POWER section header and at least the totals line
whenever any of the four power registers is present in `home`, even if all
values are zero (idle state).

**Rationale:** Omitting the section when idle would make it unclear whether the
device has no load or whether the register wasn't received. Showing zeros
confirms the measurement is live.

The existing gate `if any(k in home for k in ("totalPVPower", "totalACPower",
"totalDCPower")):` is preserved and sufficient.

### D4: Row classification

Each row is classified as IN or OUT based on the sign of its value:

| Source | Condition | Side |
|---|---|---|
| PV | pv_w present | IN (always ≥ 0) |
| Grid import | grid_w > 0 | IN |
| Battery discharging | battery_w > 0 | IN |
| AC loads | ac_w > 0 | OUT |
| DC loads | dc_w present | OUT (always ≥ 0) |
| Grid export | grid_w < 0 | OUT (show as positive) |
| AC export | ac_w < 0 | OUT (show as positive) |
| Battery charging | battery_w < 0 | OUT (show as positive) |

When `show_zeros=False`, rows with a value of 0 are omitted. When
`show_zeros=True`, all rows whose register is present (or whose derivation is
computable) are shown.

### D5: Battery row label

**Decision:** Label the battery row `Battery` with a parenthetical state hint:
`Battery:  18 W  (discharging)` or `Battery:  50 W  (charging)`.

**Rationale:** "Discharging at 100% SOC" is the specific confusion this change
aims to address. The explicit state label makes it immediately clear that the
battery is providing power, which is expected when DC loads are present even at
full charge.

## Risks / Trade-offs

**Derived battery can show small non-zero values due to register rounding** →
The four registers are integers; conversion losses and quantisation can produce
a battery_w of ±1–3 W even when the battery is truly idle. Mitigation: treat
`abs(battery_w) < 2` as zero for row-visibility purposes (omit in compact mode;
show as "≈ 0 W" or just "0 W" in verbose). Exact threshold to be decided during
implementation.

**Sign convention uncertainty for edge-case configs** → The formula was verified
for common scenarios. Unusual configurations (e.g., grid export AND AC export
simultaneously, parallel inverters) are not tested on real hardware. Mitigation:
the formula is based on energy conservation — it cannot be structurally wrong
— but individual register semantics could differ on non-AC2A V2 devices.

## Open Questions

None — design decisions were resolved during the explore session.
