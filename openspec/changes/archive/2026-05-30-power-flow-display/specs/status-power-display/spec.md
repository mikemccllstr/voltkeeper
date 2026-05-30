## ADDED Requirements

### Requirement: status command displays power as IN/OUT grouped layout

The `voltkeeper status` and `voltkeeper status --verbose` commands SHALL display
instantaneous power in an IN/OUT grouped layout whenever any V2 power register
(`totalPVPower`, `totalACPower`, `totalDCPower`, `totalGridPower`) is present in
the parsed device data.

The layout SHALL have two sections — **IN** (power sources) and **OUT** (power
sinks) — each followed by a **Total** line. The battery row SHALL be derived from
energy conservation: `battery_w = ac_w + dc_w − pv_w − grid_w`. Positive
`battery_w` means discharging (IN); negative means charging (OUT).

Row classification:

| Row | Side | Condition |
|---|---|---|
| PV | IN | register present |
| Grid import | IN | `totalGridPower > 0` |
| Battery (discharging) | IN | `battery_w > 0` |
| AC loads | OUT | `totalACPower > 0` |
| DC loads | OUT | register present |
| Grid export | OUT | `totalGridPower < 0` |
| AC export | OUT | `totalACPower < 0` |
| Battery (charging) | OUT | `battery_w < 0` |

#### Scenario: Typical grid + battery discharge

- **WHEN** `totalGridPower=36`, `totalACPower=36`, `totalDCPower=18`, `totalPVPower=0`
- **THEN** the power section shows:
  ```
  IN   Grid:         36 W
       Battery:      18 W  (discharging)
       Total:        54 W
  OUT  AC loads:     36 W
       DC loads:     18 W
       Total:        54 W
  ```

#### Scenario: PV surplus with grid export and battery charging

- **WHEN** `totalPVPower=500`, `totalGridPower=-300`, `totalACPower=100`, `totalDCPower=50`
- **THEN** the power section shows:
  ```
  IN   PV:          500 W
       Total:       500 W
  OUT  AC loads:    100 W
       DC loads:     50 W
       Grid export: 300 W
       Battery:      50 W  (charging)
       Total:       500 W
  ```

#### Scenario: Battery-only (no grid, no PV)

- **WHEN** `totalPVPower=0`, `totalGridPower=0`, `totalACPower=180`, `totalDCPower=20`
- **THEN** the power section shows:
  ```
  IN   Battery:     200 W  (discharging)
       Total:       200 W
  OUT  AC loads:    180 W
       DC loads:     20 W
       Total:       200 W
  ```

### Requirement: compact status hides zero-value power rows

In `voltkeeper status` (non-verbose), the power section SHALL omit rows whose
value is zero. The IN Total and OUT Total lines SHALL always appear.

#### Scenario: Zero PV hidden in compact mode

- **WHEN** `voltkeeper status` runs and `totalPVPower=0`
- **THEN** no `PV` row appears in the power section
- **THEN** the IN/OUT totals are still displayed

#### Scenario: Idle device compact output

- **WHEN** all power values are zero and registers are present
- **THEN** the power section header and totals appear with value 0 W
- **THEN** no individual source or sink rows appear

### Requirement: verbose status shows all power rows including zeros

In `voltkeeper status --verbose`, the power section SHALL display every row
whose underlying register is present, even when the value is zero.

#### Scenario: Zero PV shown in verbose mode

- **WHEN** `voltkeeper status --verbose` runs and `totalPVPower=0`
- **THEN** a `PV: 0 W` row appears in the IN section

### Requirement: status.md documents power layout and battery derivation

The `docs/source/user-guide/status.md` file SHALL include a **Power readings**
section explaining the IN/OUT layout, the battery row derivation formula, and
why the battery can show `Discharging` at 100% SOC.

#### Scenario: User understands Discharging at 100%

- **WHEN** a user reads status.md
- **THEN** the document explains that DC loads are always sourced from the
  battery and that `Discharging` at 100% SOC is expected when DC loads are active

#### Scenario: User understands battery row is derived

- **WHEN** a user reads status.md
- **THEN** the document states the battery row is computed from the other four
  power registers and is not a directly measured value
