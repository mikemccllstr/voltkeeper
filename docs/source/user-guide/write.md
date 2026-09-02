# write

Write settings to a Bluetti device.

```bash
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on
voltkeeper write AA:BB:CC:DD:EE:FF dc_output off
voltkeeper write AA:BB:CC:DD:EE:FF charging_mode turbo
```

## Switch fields

Values are `on` or `off`:

- `ac_output`
- `dc_output`
- `power_off`
- `dc_eco_mode`
- `ac_eco_mode`
- `power_lifting`
- `alarm_sound`
- `ups_mode` *(supported devices only — see below)*

## Enum fields

- `charging_mode` — `standard` (0), `silent` (1), `turbo` (2); also `custom` (4) on EL100V2. Mapping confirmed against APK v3.0.10 and hardware bench testing — `silent` enables the quiet, lower-speed mode on the device. **(breaking: releases through v2026.05 had `turbo` and `silent` swapped, so each wrote the opposite physical mode)**
- `system_power` *(EL400)* — `normal`, `shutdown`, `power_down_v1`, `power_down_v2`, or `sleep`. Replaces the older `power_off` / `sleep_mode` toggles, which collided on register 2013. Use `system_power sleep` to enter sleep mode and `system_power shutdown` to power down.

## Numeric fields

| Field              | Description                                     | Range            |
| ------------------ | ----------------------------------------------- | ---------------- |
| `sys_low_power`    | System low power threshold (%)                  | 0–100            |
| `sys_high_power`   | System high power threshold (%)                 | 0–100            |
| `soc_holding_low`  | SOC holding low threshold (%)                   | 0–100            |
| `soc_holding_high` | SOC holding high threshold (%)                  | 0–100            |
| `lcd_timeout`      | Screen backlight off delay (minutes)            | device-dependent |
| `led_color`        | Indicator LED color index                       | device-dependent |
| `inv_voltage`      | Output voltage setting (volts, e.g. 120 or 230) | device-dependent |
| `inv_freq`         | Output frequency setting (Hz, e.g. 50 or 60)    | device-dependent |
| `working_mode`     | Operating mode index                            | device-dependent |

`sys_low_power`, `sys_high_power`, and `led_color` are not available on the
EL100V2 — the device does not honor those registers.

## Online vs Standby UPS (`ups_mode`)

Supported devices: AC300, AC500, AC200L, AC200PL, EP500, EP600, EL10V2, EL30V2, EL100V2, EL400.

```bash
voltkeeper write AA:BB:CC:DD:EE:FF ups_mode on   # Online UPS (~0–20 ms switchover)
voltkeeper write AA:BB:CC:DD:EE:FF ups_mode off  # Standby UPS (transfer-on-loss)
```

`ups_mode` is a sub-toggle within Standard UPS mode (`working_mode = STANDARD_UPS`). It has no effect under other working modes.

- **Online (`on`)** — the inverter runs continuously, so loads never see a transfer gap. Switchover is 0 ms on dedicated outlets or ~10–20 ms on AC output. The trade-off is higher idle battery drain and more inverter heat.
- **Standby (`off`)** — the inverter idles and starts on grid loss. Switchover takes ~20 ms or more. Battery drain is lower.

Use `voltkeeper status --verbose` to see current values of all writable fields before changing them.

## Inspecting writable fields

Before writing a field, inspect what values it accepts without touching the
device:

```bash
voltkeeper write AA:BB:CC:DD:EE:FF --help-field charging_mode
# charging_mode: [standard|silent|turbo]

voltkeeper write AA:BB:CC:DD:EE:FF --help-field sys_low_power
# sys_low_power: [0-100]

voltkeeper write AA:BB:CC:DD:EE:FF --help-field ac_output
# ac_output: [on|off]
```

`--help-field` prints the field's type and its valid values: the enum options
for `on`/`off` and mode fields, or the numeric range (with the unit, where the
field defines one) for adjustable fields. `FIELD` and `VALUE` are not needed in
this mode, but the address is: voltkeeper does a BLE scan lookup to identify the
model before reading its field definitions, so the device must be powered on and
in range. No write is performed and no data connection is opened. Running it
against an unknown field prints the list of writable fields for that model.
