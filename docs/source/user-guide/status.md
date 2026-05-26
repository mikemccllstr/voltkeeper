# status

Read battery status from a Bluetti power station.

```bash
voltkeeper status                  # auto-scan for devices, then pick one
voltkeeper status AA:BB:CC:DD:EE:FF  # connect directly
```

## Output

- Battery SOC (%)
- Pack voltage
- Charging status
- Time to full / time to empty (context-dependent)
- DC load, AC load, and total load (watts)

## Alarms and faults

When the device reports an active alarm or fault condition, the output includes
one or more keys of the form:

```
alarm.<name> = True
fault.<name> = True
```

For example:

```
alarm.Grid Voltage High = True
fault.Inverter Over Temperature = True
```

Alarm names are sourced verbatim from the Bluetti APK string resources (see
`src/voltkeeper/core/devices/_v2_alarm_tables.py` for V2 devices and
`_v1_alarm_tables.py` for V1 devices). For pack-connected devices, pack alarms
include a sub-device prefix:

```
sub[41].alarm.Overall Overvoltage Alarm = True
```

## Options

| Option                | Description                                                                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-t, --timeout FLOAT` | Scan timeout in seconds (default: 10.0, used only when no address given)                                                                                                     |
| `-v, --verbose`       | Display all available device information (power meters, energy totals, PV strings, grid, loads, temperatures, software versions, writable controls, and device capabilities) |
