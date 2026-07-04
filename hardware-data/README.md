# hardware-data

This directory stores verify output YAML files produced against real hardware.
These files are committed to the repository as primary empirical evidence of
what each device model actually supports.

## Naming convention

```
{verify|verify-ground-truth}_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml
```

The mode component is `verify` for plain runs and `verify-ground-truth` for
`--ground-truth` runs. `<MODEL>` is the device's `type` attribute (e.g.,
`AC2A`). The timestamp is the session start time in UTC at minute precision.

Examples:
- `verify_AC2A_2026-05-26T1000Z.yaml`
- `verify_AC2A_2026-05-27T1530Z.yaml`

When the computed path already exists, the writer appends `_v2`, `_v3`, etc.
before `.yaml` — existing files are never overwritten. Use `--output` to
specify a custom path.

## Why these files are committed

Verify runs represent real hardware behaviour that informs the device model
declarations in `src/voltkeeper/core/devices/`. Keeping them here alongside
the code makes it possible to:

- Trace which hardware was tested with which code version.
- Review findings when updating a field's declared range.
- Spot regressions when a device firmware update changes accepted values.

Serial numbers and BLE MAC addresses are scrubbed by default
(`VKTEST000000` / `AA:BB:CC:DD:EE:FF`). Pass `--no-scrub` to preserve them
if you need them for correlation, but do not commit unscrubbed files.
