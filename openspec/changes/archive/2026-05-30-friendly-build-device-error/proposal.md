## Why

When a Bluetti device is already connected to the Android app, it advertises without its model-name prefix (the BLE name becomes the raw MAC address instead of e.g. `EL100V22305000`). All CLI commands crash with a bare `ValueError: Unsupported device model ... Known prefixes: [...]` traceback instead of telling the user what happened and how to fix it.

## What Changes

- Add a `_device_from_scan()` helper in `cli.py` that wraps `build_device()` with a friendly error message when the advertised name doesn't match any known device prefix
- Replace all 8 `build_device()` call sites in CLI commands with the helper
- Error message explains the likely cause (device connected to the Bluetti app) and the fix (disconnect and retry)

## Capabilities

### New Capabilities

- `cli-error-handling`: CLI commands gracefully handle unrecognized BLE device names with a clear error message instead of a traceback

### Modified Capabilities

None.

## Impact

- `src/voltkeeper/cli.py` — new helper function, 8 call sites updated
