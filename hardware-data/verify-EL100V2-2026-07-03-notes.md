# Bench session notes — EL100V2, 2026-07-03

Operator: Mike. Three verify runs captured the same day:

| Report | Power source | Tiers | Notes |
| ------ | ------------ | ----- | ----- |
| `verify-EL100V2-ac-2026-07-03.yaml`  | Grid (~119 V) | 1–3 | Primary session; state below |
| `verify-EL100V2-dc1-2026-07-03.yaml` | DC/PV supply  | 1–3 | SoC 100%; PV block records 103 W @ 12.5 V / 8.2 A |
| `verify-EL100V2-dc2-2026-07-03.yaml` | DC/PV supply  | 1 only | SoC 99%; PV block records 102 W @ 12.5 V / 8.1 A (matches app: ~102 W DC in) |

App observations from screenshots taken before/after the AC run.

## Device state at capture time (AC run)

- SoC: 100%
- AC load: ~45 W (steady, supplied by device)
- DC load: 16 W (supplied by device)
- Grid input: connected, ~119 V
- DC/PV supply: physically connected, device not drawing from it
- Grid draw observed at both ~46 W (matching AC load) and ~60 W (matching
  AC + DC load) at different times: DC load appears battery-supplied, with the
  grid draw jumping when the battery tops back up.

## App cross-checks (Bluetti app, before/after run)

### Firmware versions (task 3.3 — all match parsed keys)

Display format is `raw / 100`, two decimals.

| MCU | Parsed raw | App displays |
| --- | ---------- | ------------ |
| ARM | 218614     | v2186.14     |
| DSP | 220013     | v2200.13     |
| BMS | 108307     | v1083.07     |
| IOT | 802411     | v8024.11     |

Communications Board SN displays as `IoT2542016273527` — matches parsed
`iot_sn` (`2542016273527`).

### Grid max current (register 2214)

App screen "Max. Grid Input Current" is gated behind a "Pro Mode" slider
(liability disclaimer + password prompt; password unknown, not entered).
With Pro Mode disabled the app shows the input current as **0 A**.

Combined with the tier-3 sweep (raw 0–15 accepted, 16+ rejected), register
2214 holds **whole amps**, with 0 meaning Pro Mode disabled. The DecimalField
(÷10) declaration in voltkeeper is wrong.

### ECO settings

- AC Shutdown: options 1h/2h/3h/4h (4h selected post-run) — matches tier-3
  discovered range 1–4 on `ac_eco_auto_off_time` (register holds hours).
- AC Power: numeric entry, range 10 W–40 W (10 W post-run) — register 2019
  holds watts; tier-3 accepted 10–14 before the sweep ended.
- DC Shutdown: options 1h/2h/3h/4h (4h selected post-run) — register holds
  hours, discovered 1–4.
- DC Power: range 5 W–20 W (6 W post-run) — register 2016 holds watts;
  tier-3 accepted 5–6 before the sweep ended.

Post-run app values (4h/10 W/6 W) show the tier-3 `restore_failed` leftovers
largely self-corrected; `lcd_timeout` (left at 0) and charging mode (see
below) were the remaining manual cleanups.

## Charging-mode TURBO/SILENT swap — CONFIRMED

Writing `charging_mode turbo` (register 2020 = 1) moved the device from
Standard to **Silent** on the device's own display. The APK mapping
(silent=1, turbo=2) is correct; voltkeeper's AC2A and EL100V2 enums are
swapped. Fix tracked as a separate change.

## BLE exclusivity (verify-ground-truth question 0.1)

While voltkeeper held the BLE connection, an Android app device scan did not
show the EL100V2; after the run it reappeared. The device accepts one BLE
session at a time. The cloud path was also inactive during the run
(`mqtt_status: false` in the IoT block), so no concurrent app view of live
data was available by any path in this setup.

## Custom charging mode (task 3.2)

`charging_mode = 4` written and read back as 4 during the tier-3 enum cycle —
CUSTOM is accepted by the device firmware.

## DC-run addenda

- The dc1/dc2 runs used the post-fix field declarations: block 2200 now
  parses 11 fields vs 10 in the AC run — the old DecimalField dropped
  `grid_max_current` (raw 4 → 0.4 A, outside its declared (1, 15)); the uint
  field parses it as 4 A. The fix is visible in the reports.
- `lcd_timeout` floor confirmed again in dc1: safe-default write of 0
  rejected, register holds 5 minimum. Real range unknown (no app evidence
  captured); candidate for a future range declaration.
- `ac_eco_power` acceptance is state-dependent: the dc1 sweep accepted 10–18
  and rejected 19 (the AC run accepted only 10–14), while the app's entry
  field allows 10–40. Declared range stays (10, 40) per the app; device-side
  rejection within that range is possible.
- dc1 tier-3 restores left `ac_eco_power` at 19 W and `lcd_timeout` at 0;
  charging mode ended at Standard (0).
