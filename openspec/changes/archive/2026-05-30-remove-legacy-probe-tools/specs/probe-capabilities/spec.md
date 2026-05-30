## REMOVED Requirements

### Requirement: Probe decodes ctrl_event capabilities

**Reason**: The `probe` CLI command and its supporting module are being removed. ctrl_event decoding is handled by the `verify` command and the device class `decode_ctrl_event` method, which are unaffected.

**Migration**: Use `voltkeeper verify` for hardware validation, which parses and validates all fields including ctrl_event through the device class parse path (not raw hex). For programmatic ctrl_event access, use the device class `decode_ctrl_event` method directly.

### Requirement: Probe ctrl_event bit definitions

**Reason**: Same as above — this requirement was scoped entirely to the probe YAML output format. The bit definitions (`CTRL_EVENT_BITS`, `decode_ctrl_event`) remain unchanged in `v2_base.py` and continue to be tested.

**Migration**: No migration needed. The bit definitions and decode function are untouched.
