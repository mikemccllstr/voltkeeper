## Why

Cross-referencing Bluetti's official App Features Guide blog post against the v3.0.9 APK revealed several protocol features and device models that are already present in the APK but missing from voltkeeper. Adding them improves protocol completeness, enables control over UPS strategy selection (not just Online/Standby), adds hardware button lockout for safety, and extends device support to three additional models purchasable today.

## What Changes

- Add `WORKING_MODE` register (V1: 3001, V2: 2005) with a 6-value `WorkingMode` enum for UPS strategy selection (Customized, PV Priority, Standard, Time Control V1/V2, Self-Consumption Export)
- Add Child Lock registers (V2: 2072 on/off, 2076 level 1-2) as writable fields with feature-gated visibility
- Document `SYSTEM_POWER_OFF` multi-value encoding (1=shutdown, 2=power down V1, 3=power down V2, 4=sleep) and add sleep configuration registers (2073, 2074, 2079)
- Add AC180 device base class covering the AC180/PLP022 portable power station family (model #23/#7, 56V)
- Add EL10V2 device class (model #62, 25V) inheriting from AC180 base
- Add EL30V2 device class (model #32, 25V) as sibling to EL100V2 in the ELITE200_V2 family
- Add EL400 device class (model #29, 56V) in the ELITE200_V2 family with remote power control and sleep mode support
- Update protocol reference docs with new register value mappings
- Add fabricated test data based on APK parser structures for all new device classes

## Capabilities

### New Capabilities
- `working-mode`: UPS strategy selection register (3001/2005) with 6-mode enum, replacing the current boolean-only UPS_MODE at 3035
- `child-lock`: Physical button lockout via registers 2072 (on/off bitfield) and 2076 (level 1-2), feature-gated per device model
- `ac180-device`: Device support for AC180, PLP022, and EL10V2 portable power stations including register layout and writable fields

### Modified Capabilities
- `v2-control-registers`: Adding WORKING_MODE (2005), child lock (2072, 2076), and sleep config registers (2073, 2074, 2079); documenting SYSTEM_POWER_OFF value encoding
- `v1-control-registers`: Adding WORKING_MODE (3001) register documentation
- `device-model-expansion`: Adding EL400, EL10V2, EL30V2 to the supported device registry and catalog
- `tlv-protocol`: May require updates if new devices have TLV topology differences

## Impact

- `src/voltkeeper/core/devices/v1_base.py` — new WORKING_MODE constant
- `src/voltkeeper/core/devices/v2_base.py` — new WORKING_MODE, child lock, sleep register constants; WorkingMode enum
- `src/voltkeeper/core/devices/ac180.py` — new AC180 base class
- `src/voltkeeper/core/devices/el10v2.py` — new EL10V2 device class
- `src/voltkeeper/core/devices/el30v2.py` — new EL30V2 device class
- `src/voltkeeper/core/devices/el400.py` — new EL400 device class
- `src/voltkeeper/bluetooth/__init__.py` — device registry additions
- `docs/source/protocol/modbus-registers.md` — new register value mappings
- `docs/source/protocol/device-models.md` — new model entries
- `tests/` — new test files for AC180 family, child lock, working mode
