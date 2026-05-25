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

Use `voltkeeper status --verbose` to see current values of all writable fields before changing them.

## Field name changes (breaking)

Four field names changed to match the Bluetti Android app's internal naming:

| Old Name              | New Name           | Reason                                                                         |
| --------------------- | ------------------ | ------------------------------------------------------------------------------ |
| `battery_range_start` | `sys_low_power`    | APK calls this `sysLowPower` — a system power threshold, not battery SOC range |
| `battery_range_end`   | `sys_high_power`   | APK calls this `sysHighPower`                                                  |
| `soc_low`             | `soc_holding_low`  | APK calls this `socHoldingLow`                                                 |
| `soc_high`            | `soc_holding_high` | APK calls this `socHoldingHigh`                                                |

Update any scripts, Home Assistant automations, or MQTT subscriptions to use the new field names.
