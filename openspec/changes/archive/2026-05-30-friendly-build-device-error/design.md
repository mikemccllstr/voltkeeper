## Context

`build_device()` in `src/voltkeeper/bluetooth/__init__.py` maps a BLE advertised name to a device class by matching against known prefixes (e.g. `EL100V2`, `AC2A`). When a device is already connected to the Bluetti Android app, it advertises with its raw MAC address as the name (e.g. `DC:B4:D9:46:73:96`) instead of the expected `EL100V2<sn>` format. No prefix matches, and `build_device()` raises `ValueError`.

The daemon (`device_manager.py`) already handles this with `_try_build_device()` (catch `ValueError`, return `None`). CLI commands don't — they crash.

## Goals / Non-Goals

**Goals:**
- Replace the traceback with a clear, actionable error message
- Apply to all CLI commands that call `build_device()`
- Keep the change small and low-risk

**Non-Goals:**
- Auto-discover the device model from register 110 (future Option B)
- Change `build_device()` behavior in `bluetooth/__init__.py`
- Add retry logic or scan for alternative names

## Decisions

### Decision 1: Helper function in `cli.py`

**Choice**: Add a `_device_from_scan(sr: ScanResult)` helper in `cli.py` that wraps `build_device()` with a try/except.

**Why**: A single function captures the logic once. If we later implement Option B (auto-discover), it's one change point. Avoids touching `bluetooth/__init__.py` since `build_device()` is used by the daemon which handles `ValueError` differently (log-and-skip, not exit).

**Alternative**: Catch at each call site. Rejected — 8 identical try/except blocks.

### Decision 2: Error message content

**Choice**: Include the device address and received name for debugging, plus the likely cause and fix.

```
Device at AA:BB:CC:DD:EE:FF is advertising without a recognized model name
(received: 'DC:B4:D9:46:73:96').
This happens when the device is already connected to the Bluetti app.
Disconnect it from the app and try again.
```

## Risks / Trade-offs

- **Risk**: Future commands forget to use the helper and reintroduce the crash. **Mitigation**: The helper is the obvious choice — it handles both success and error paths. Adding a comment near `build_device()` import could help but is fragile.
- **Risk**: The device advertises with a genuinely unknown prefix (not MAC address). The message about "connected to the app" would be misleading. **Mitigation**: Low probability — all known Bluetti models are registered. If a new model appears, it needs a registry entry regardless.
