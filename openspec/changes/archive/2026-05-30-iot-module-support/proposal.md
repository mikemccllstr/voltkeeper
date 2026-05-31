## Why

Many Bluetti devices contain an ESP32-based IoT communications module with its own model, serial number, firmware, WiFi hardware, and connection status. The APK v3.0.9 reads these from Modbus registers 11000+ but our code has no awareness of them. Hardware probing on an EL100V2 (FW SW#3) confirmed the IoT module is present and responsive — even though the APK's `hasIot` flag is `false` for this model. Exposing IoT module data in `status` and `verify` helps diagnose connectivity issues (e.g., "is the device on WiFi or BLE-only right now?") and provides firmware version tracking comparable to what we already do for the inverter.

## What Changes

- Add `IOT_BASE_INFO` (11000) and `IOT_ENABLE_INFO` (12161) as V2 register constants
- Add an `iot_struct` to V2Base with key fields: model, serial, firmware, WiFi/connection status
- Include `ReadHoldingRegisters(IOT_BASE_INFO, 70)` in `control_commands` for devices with IoT hardware
- Display IoT info in `voltkeeper status`: model, firmware, active connection mode, BLE connection status
- Include IOT_BASE_INFO as a block in verify tier 1, capturing IoT firmware version in the report
- Add `_assert_iot_info(self, result, raw)` to verify tier 1 for IoT field parsing counts

## Capabilities

### New Capabilities

- `iot-module-polling`: The IoT communications module's registers (11000+) are polled, parsed, and displayed alongside inverter telemetry. Connection status, firmware version, and networking info are surfaced.

### Modified Capabilities

- `device-verify`: Tier 1 includes the IOT_BASE_INFO block when the device has an IoT module, recording firmware version and field parse counts.
- `el100v2-device`: `control_commands` includes IoT reads for EL100V2 (hardware-probed to support them).

## Impact

- `src/voltkeeper/core/devices/v2_base.py` — new `IOT_BASE_INFO` / `IOT_ENABLE_INFO` constants, `_build_iot_struct()`, `parse()` dispatch for 11000+
- `src/voltkeeper/core/devices/el100v2.py` — override `control_commands` to include IoT reads
- `src/voltkeeper/core/verify.py` — tier 1 includes block 11000 if device has `iot_struct` fields
- `src/voltkeeper/core/struct.py` — possibly new field types for MAC addresses, IPs
- `src/voltkeeper/cli.py` — status display shows IoT info when present
- `tests/test_voltkeeper.py` — tests for IoT struct parsing, control_commands inclusion
