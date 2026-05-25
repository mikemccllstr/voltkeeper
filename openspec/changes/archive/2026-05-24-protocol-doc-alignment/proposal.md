## Why

This branch reverse-engineered the Bluetti Android APK v3.0.9 and updated the protocol documentation in `docs/source/protocol/` with new findings — expanded register maps, TLV sub-protocol, 5 new device models, and protocol behavior details. The Python source code was originally written against APK 3.0.8 findings and has not been updated. Several bugs exist where the source makes incorrect assumptions that the 3.0.9 docs now clarify, and many registers and capabilities documented in 3.0.9 are missing from the Python implementation.

## What Changes

- **Bug fixes**: Fix V1 protocol version detection in `probe.py` (registry shortcut always uses `protocol_version=0`, causing data truncation on newer V1 devices). Fix regex inconsistency between `scrub.py` (`\d{6,}`) and `bluetooth.py` (`\d+`). Update stale "APK 3.0.8" reference to "APK 3.0.9".
- **V1 settable control registers**: Add 11 missing writable/readable register constants documented in the 3.0.9 V1 protocol register map (e.g., `MACHINE_MODE`, `MAX_PV_CHARGE_CURRENT`, `SYSTEM_TIME`, `ECO_AUTO_OFF`).
- **V2 control registers**: Add 20+ missing writable/readable register constants for AC2A and AC60 devices (e.g., `SYSTEM_TIME`, `CTRL_GRID`, `CTRL_FEED`, charge/grid current limits, PV type settings, EMS mode).
- **TLV protocol**: Implement parsing for the TLV-encoded NODE_INFO response (register 21000) introduced in APK v3.0.9, enabling multi-sub-device topology discovery.
- **Battery pack data**: Add register definitions and struct parsing for battery pack telemetry blocks (PACK_MAIN_INFO at 6000, PACK_ITEM_INFO at 6100, PACK_BMU_INFO at 7200).
- **Device model expansion**: Add device definitions for 5 new v3.0.9 models (AORA100_MINI, AORA30_MINI, AORA200_MINI, HB500S, BH500E) and update the device registry.

OOT scope: OTA/firmware upgrades, backend cloud API client, Wi-Fi-only device categories, grid certification registers.

## Capabilities

### New Capabilities

- `protocol-bug-fixes`: Fix V1 probe detection data truncation bug, harmonize device name regex between scrub and bluetooth modules, update stale APK version reference in comments.
- `v1-control-registers`: Add missing V1 settable/readable register constants from the APK 3.0.9 V1 protocol register map to `v1_base.py` and expose them as writable fields on V1 device classes.
- `v2-control-registers`: Add missing V2 control register constants from the APK 3.0.9 V2 protocol register map to `ac2a.py` (and `ac60.py` where applicable) and expose them as writable fields.
- `tlv-protocol`: Implement TLV response parsing for NODE_INFO (register 21000), supporting multi-sub-device topology discovery for V2 protocol devices.
- `battery-pack-data`: Add register definitions and struct parsing for battery pack blocks (PACK_MAIN_INFO, PACK_ITEM_INFO, PACK_BMU_INFO) to enable cell-level battery monitoring.
- `device-model-expansion`: Add device class definitions for 5 new v3.0.9 models and update the device name regex and registry to recognize them.

### Modified Capabilities

None — existing specs (gh-pages-deploy, readme-landing-page, sphinx-docs) are unchanged by this work.

## Impact

- `src/voltkeeper/probe.py` — fix `_detect_protocol` V1 path, may need `protocol_version` overrides on V1 device classes
- `src/voltkeeper/scrub.py` — update `_NAME_SN_RE` regex
- `src/voltkeeper/bluetooth/__init__.py` — update `_DEVICE_NAME_SN_RE` and `_device_registry`
- `src/voltkeeper/core/devices/v1_base.py` — add register constants, update APK version comment
- `src/voltkeeper/core/devices/v2_base.py` — may add battery/auxiliary block definitions
- `src/voltkeeper/core/devices/ac2a.py` — add control register fields
- `src/voltkeeper/core/devices/ac60.py` — add control register fields
- New files: `src/voltkeeper/core/devices/aora_mini.py`, `src/voltkeeper/core/devices/battery_packs.py`, TLV parsing module
- Tests: new and updated tests for all changed modules
