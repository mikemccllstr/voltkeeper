## 1. Device Class

- [x] 1.1 Create `src/voltkeeper/core/devices/el100v2.py` with `El100V2(V2Base)` class
- [x] 1.2 Implement `_build_control_struct()` with writable fields matching APK chain (AC output/DC output/power off/ECO modes/charging mode/battery range/alarm sound/LCD timeout/SOC limits/LED/system time/grid control/feed-in control/output voltage/frequency/charge limits/grid limits/feed limits)
- [x] 1.3 Define `WRITABLE_FIELD_NAMES` list
- [x] 1.4 Define `CTRL_EVENT_BITS` and `ctrl_event_bits`/`decode_ctrl_event` using shared V2 definitions
- [x] 2.1 Add `EL100V2` prefix mapping to `El100V2` in `bluetooth/__init__.py` registry
- [x] 2.2 Import `El100V2` in `bluetooth/__init__.py` or use lazy import pattern matching existing devices

## 3. Tests

- [x] 3.1 Write test for registry lookup: BLE name `EL100V2<SN>` creates `El100V2` instance
- [x] 3.2 Write test for polling commands: inherits full V2 register blocks
- [x] 3.3 Write test for writable fields: `has_field_setter` returns True for known fields, False for unknown
- [x] 3.4 Write test for setter command building: `build_setter_command` returns correct addresses
- [x] 3.5 Write test for ctrl_event decoding: partial and full bitmask
