## Context

Voltkeeper's status output and write path treat many register fields as opaque integers, even though the APK v3.0.9 source confirms they have enumerated human-readable meanings. The `build_setter_command` method in `v2_base.py`/`v1_base.py` already handles `EnumField` (accepts string names OR integer values) and `BoolField` (accepts `"on"`/`True`), but many fields remain as `UintField`. Additionally, `UintField.in_range()` is called on reads but never on writes, allowing out-of-range values through.

## Goals / Non-Goals

**Goals:**
- Convert `inv_freq`, `pv_type_set`, `pv2_type_set`, `led_color`, `ems_ctrl_mode_set` from `UintField` to `EnumField` on all V2 device classes
- Enforce `in_range()` validation during writes for `UintField` and `DecimalField`
- Add `invWorkingStatus` human-readable mapping to CLI verbose display
- Add unit suffixes to ECO/power fields in CLI verbose display
- Fix CLI `_parse_field_value` to not hardcode enum values
- Add `--help` to write command showing valid values per field
- Fix Web UI charging_mode string-vs-int bug
- Render Web UI controls dynamically from writable field definitions
- Add new enum fields to MQTT NORMAL_DEVICE_FIELDS

**Non-Goals:**
- Converting `inv_voltage` to an enum (depends on `voltType` which is not exposed)
- Adding writable-field discovery to the HTTP API (new endpoint)
- Changing the MQTT topic format or HA discovery schema

## Decisions

### Decision 1: Enums live in `commands.py` alongside `WorkingMode`

All new enums (`InvFrequency`, `PvType`, `Pv2Type`, `LedColor`, `EmsCtrlMode`) go in `commands.py`. This is where `WorkingMode` already lives, providing a single shared location for enums used by both V1 and V2 device classes.

**Rationale**: Avoids circular imports between device classes. `commands.py` already imports only from `utils.py` (CRC calculation), so adding enums is dependency-free.

**Alternatives considered**: Placing enums in `v2_base.py`. Rejected because V1 devices also use `InverterFrequency` (already in `ac200l.py`/`ac500.py`/`ac300.py`) and consistency matters.

### Decision 2: V1 InverterFrequency enum removes raw values for Hz labels

Existing V1 `InverterFrequency` uses `HZ50 = 50, HZ60 = 60` (the actual Hz values). The new unified `InvFrequency` uses `HZ_50 = 0, HZ_60 = 1` (the register values). V1 devices using `inv_frequency` at address 3003 will switch to the shared `InvFrequency` enum.

**Rationale**: The register holds 0 or 1, not 50 or 60. Enum values matching the register makes write logic straightforward: `InvFrequency["HZ_50"] → 0` and `WriteSingleRegister(2210, 0)`. The Hz display comes from the enum member name.

**Alternatives considered**: Keeping V1's 50/60-based enum. Rejected because `build_setter_command` sends enum values to the Modbus register, so the values should match what the device expects.

### Decision 3: `build_setter_command` validates range before constructing command

Range validation is added to `build_setter_command` in both `v2_base.py` and `v1_base.py`. For `UintField` and `DecimalField` with range constraints, writing an out-of-range value raises `ValueError` with a descriptive message including the valid range.

**Rationale**: Catches errors at the earliest possible point (before the Modbus command is constructed) and provides immediate feedback across all interfaces (CLI, API, MQTT).

### Decision 4: Web UI dynamically discovers writable fields

The Web UI replaces its hardcoded `writableFields` array with dynamic discovery. An HTTP API endpoint (`GET /api/device/{address}/fields`) returns the list of writable fields with types, enum values, and ranges. The UI renders each field with the appropriate control: dropdown for enums, checkbox for bools, number input for ranged numeric fields.

**Rationale**: Keeps the Web UI in sync with the device class definitions. Adding a new writable field to a Python class automatically surfaces it in the UI.

### Decision 5: `_parse_field_value` delegates to `build_setter_command`

The daemon-mode `_parse_field_value` in `cli.py` is replaced with a function that sends the raw string value to the API and lets the server-side `build_setter_command` handle validation. This eliminates the hardcoded `charging_mode` mapping.

**Rationale**: Single source of truth for value validation. The old `_parse_field_value` would need to grow with every new enum added. Deferring to the server avoids maintaining a mirrored validation in the CLI.

### Decision 6: inv_voltage documented but not converted

`inv_voltage` (register 2209) is confirmed to be an enumeration whose mapping depends on `voltType` (0=low-voltage regions with 100V/120V/208V, 1=high-voltage regions with 220V/230V/240V). Since voltkeeper has no mechanism to discover `voltType`, the field remains as `UintField` with a comment documenting the known mappings and the voltType dependency.

## Risks / Trade-offs

- **[Risk] Enums may include values that specific device models don't support** → Mitigation: All devices share the same enum definition; writing an unsupported value will be NACK'd by the device firmware (same as the official app's behavior)
- **[Risk] Web UI field discovery adds an HTTP round-trip** → Mitigation: Single GET request per device, payload is small (<1KB), cached for session
- **[Risk] led_color mapping differs between devices with/without color support** → Mitigation: Use a single enum covering both semantics (Off/Cool-or-Half/Warm-or-Full/SOS); the display label is inherently model-dependent
- **[Risk] `_parse_field_value` removal changes daemon-mode behavior** → Mitigation: The server already calls `build_setter_command` with the value; sending the raw string lets the server handle all parsing consistently
