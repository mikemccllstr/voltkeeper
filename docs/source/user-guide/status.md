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

## Options

| Option | Description |
|---|---|
| `-t, --timeout FLOAT` | Scan timeout in seconds (default: 10.0, used only when no address given) |
| `-v, --verbose` | Display all available device information (power meters, energy totals, PV strings, grid, loads, temperatures, software versions, writable controls, and device capabilities) |
