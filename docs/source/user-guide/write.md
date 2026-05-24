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

- `battery_range_start`
- `battery_range_end`
- `lcd_timeout`
- `led_color`
- `soc_low`
- `soc_high`
- `inv_voltage`
- `inv_freq`
- `working_mode`

Use `voltkeeper status --verbose` to see current values of all writable fields.
