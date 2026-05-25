## Why

Our polling strategy fires 6-8 separate Modbus read commands every poll cycle, each a full BLE round-trip. The APK v3.0.9 uses TLV bundling to combine them into 1 request, discovers sub-device topology at runtime via NODE_INFO instead of hardcoding flags, and uses time-slicing to skip expensive reads when the user isn't on the relevant screen. Alignment with the APK's approach will reduce BLE latency, eliminate hardcoded topology assumptions, and improve the probe tool's utility for new devices.

## What Changes

- **TLV bundling for poll commands**: Build and send a single TLV-encoded Modbus read request per poll cycle instead of 6-8 individual commands. The device responds with all blocks in one BLE notification.
- **Runtime NODE_INFO discovery**: Poll NODE_INFO (register 21000) at connect time, parse the TLV response, and use discovered topology to dynamically include/exclude sub-device and battery pack registers from polling.
- **Time-sliced polling**: Fast-changing telemetry (HOME, CONTROLS) every cycle; slower registers (INV_BASE_INFO, PV_INFO, GRID_INFO, LOAD_INFO) every 2-3 cycles.
- **Probe ctrl_event capabilities**: When probing a V2 device, decode register 124 (ctrl_event) from APP_HOME_DATA and include the decoded capability list in the probe YAML output.

## Capabilities

### New Capabilities
- `probe-capabilities`: Decode and emit ctrl_event bitmask as named capabilities in the probe tool's YAML output for V2 devices.
- `time-sliced-polling`: Poll fast registers every cycle and slow registers on a counter-based schedule instead of all registers every cycle.

### Modified Capabilities
- `tlv-protocol`: Extend TLV support from parse-only to build-and-parse. TLV bundling to combine multiple register reads into one request. Relax the "only poll NODE_INFO for multi-device systems" requirement — poll at connect time to discover topology, then conditionally poll based on what was discovered.
- `battery-pack-data`: Replace hardcoded `has_battery_packs` flag with runtime discovery via NODE_INFO. Pack registers are polled when NODE_INFO reports packs, not based on a static class attribute.

## Impact

- `src/voltkeeper/core/commands.py` — new TLV build command or TLV encoding on ReadHoldingRegisters
- `src/voltkeeper/core/devices/v2_base.py` — time-sliced polling, dynamic polling_commands based on discovered topology, TLV bundling
- `src/voltkeeper/core/devices/bluetti_device.py` — base class support for discovered topology
- `src/voltkeeper/core/tlv.py` — new TLV encoding (build) in addition to existing parse
- `src/voltkeeper/core/devices/battery_packs.py` — remove hardcoded has_battery_packs
- `src/voltkeeper/probe.py` — ctrl_event decoding in probe output
- `docs/source/protocol/polling-strategy.md` — already written, needs updates as implementation progresses
