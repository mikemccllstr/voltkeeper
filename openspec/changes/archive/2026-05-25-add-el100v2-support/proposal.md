## Why

The BLUETTI Elite 100 V2 (EL100V2) is a V2-protocol portable power station not currently supported by voltkeeper. The APK v3.0.9 handles it via a template chain (ELITE200_V2 → AC200PL → AC240) with V2 protocol, full writable controls, and ctrl_event capability decoding. Adding support lets voltkeeper users monitor and control this device over BLE.

## What Changes

- New `El100V2` device class inheriting from `V2Base` with full writable control struct based on APK analysis
- Registry entry in `bluetooth/__init__.py` for BLE name prefix `EL100V2`
- CTRL_EVENT_BITS definition matching V2 portable power station capabilities
- Tests for registry lookup, polling commands, parse dispatch, writable fields, and ctrl_event decoding

## Capabilities

### New Capabilities
- `el100v2-device`: Full V2 device support for EL100V2 including telemetry, writable controls, and ctrl_event decoding

### Modified Capabilities
- *(none — no existing requirements change)*

## Impact

- `src/voltkeeper/core/devices/el100v2.py` — new device class
- `src/voltkeeper/bluetooth/__init__.py` — registry entry
- `tests/test_voltkeeper.py` — new test class
