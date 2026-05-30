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
- Power readings (IN/OUT grouped layout — see below)

## Power readings

When V2 power registers are available, the output groups instantaneous power
into **IN** (sources) and **OUT** (sinks), each with a total:

```
IN   PV:              500 W
     Total:           500 W
OUT  AC loads:        100 W
     DC loads:         50 W
     Grid export:     300 W
     Battery:          50 W  (charging)
     Total:           500 W
```

### Battery row

The battery row is **derived** — it is not a directly measured register value.
It is computed from the other four power registers using conservation of energy:

```
battery = ac + dc − pv − grid
```

A positive result means the battery is discharging (acting as a source); a
negative result means it is charging (acting as a sink).

### Discharging at 100% SOC

When DC loads are active, the battery powers them directly — there is no
separate DC bus. This means `Discharging` in the battery row is **expected and
normal** even when SOC is at 100%, because the DC load demand must come from
somewhere. It does not indicate a fault or a misconfigured state.

### Compact vs verbose

In `voltkeeper status` (compact), rows with a value of 0 W are hidden to keep
the output tight. In `voltkeeper status --verbose`, all rows are shown even at
0 W, which confirms the measurement is live.

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
