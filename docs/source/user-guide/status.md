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

## Software versions

`voltkeeper status --verbose` reports the firmware versions of the device's
MCU components in a `SOFTWARE VERSIONS` section. Each row labels the component
and shows the formatted version string, for example:

```
ARM:  v2084.09
DSP:  v2100.04
```

Versions are parsed from the MCU firmware entries in the inverter base-info
register block (INV_BASE_INFO, registers 1100+). Each entry is a 6-byte record
holding an MCU type code and a version value; the type code selects the
component name, and unknown type codes fall back to `mcuN` labels rather than
being dropped. Entries with a type code of 0 or a version of 0 are treated as
empty slots and skipped, so a component never appears with a placeholder value.

Known type codes are named after the APK's `DeviceFirmware` enum. The most
commonly seen components on V2 devices are:

| Type code | Component label |
| --------- | --------------- |
| 1         | ARM             |
| 2         | DSP             |
| 3         | BMS             |
| 11        | HMI1            |
| 12        | HMI2            |

The raw version value is a packed integer. The CLI formats it as `v<n>` up to
four digits, `v<major>.<minor>` at five or six digits (`208409` becomes
`v2084.09`), and `v<major>.<minor>.<patch>` beyond that. The section is only
printed when at least one `*_version` key is present.

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
| `--daemon URL`        | Query the voltkeeperd daemon at this URL instead of connecting via BLE (e.g. `localhost` or `http://localhost:8080`)                                                         |
