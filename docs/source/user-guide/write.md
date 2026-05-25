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

## Enum fields

- `charging_mode` — `standard`, `turbo`, or `silent`

## Numeric fields

| Field | Description | Range |
|---|---|---|
| `battery_range_start` | Lower SOC limit for charge cycling (%) | 0–100 |
| `battery_range_end` | Upper SOC limit for charge cycling (%) | 0–100 |
| `soc_low` | Low-battery alert threshold (%) | 0–100 |
| `soc_high` | High-battery alert threshold (%) | 0–100 |
| `lcd_timeout` | Screen backlight off delay (minutes) | device-dependent |
| `led_color` | Indicator LED color index | device-dependent |
| `inv_voltage` | Output voltage setting (volts, e.g. 120 or 230) | device-dependent |
| `inv_freq` | Output frequency setting (Hz, e.g. 50 or 60) | device-dependent |
| `working_mode` | Operating mode index | device-dependent |

Use `voltkeeper status --verbose` to see current values of all writable fields before changing them.
