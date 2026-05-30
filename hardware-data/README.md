# hardware-data

This directory stores verify output YAML files produced against real hardware.
These files are committed to the repository as primary empirical evidence of
what each device model actually supports.

## Naming convention

```
verify-<MODEL>-<YYYY-MM-DD>.yaml
```

Examples:
- `verify-AC2A-2026-05-26.yaml`
- `verify-AC2A-2026-05-27.yaml`

`<MODEL>` matches the device's `type` attribute (e.g., `AC2A`). Multiple runs
on the same day can be distinguished by appending `-2`, `-3`, etc., or by
passing an explicit `--output` path.

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
