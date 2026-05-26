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

- `charging_mode` — `standard`, `turbo`, or `silent`
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
