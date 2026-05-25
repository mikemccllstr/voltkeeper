## 1. struct.py — Add unit to UintField

- [x] 1.1 Add `unit: str | None = None` parameter to `UintField.__init__` and store as `self.unit`
- [x] 1.2 Add `unit: str | None = None` parameter to `DeviceStruct.add_uint_field` and pass through to `UintField`
- [x] 1.3 Write unit tests covering `UintField` with and without `unit`

## 2. Device files — Annotate eco fields with units

- [x] 2.1 Annotate `dc_eco_auto_off_time` and `ac_eco_auto_off_time` with `unit="h"` in el30v2, el10v2, el100v2, el400, ac180, ac60, ac2a
- [x] 2.2 Annotate `dc_eco_power` and `ac_eco_power` with `unit="W"` in el30v2, el10v2, el100v2, el400, ac180, ac60, ac2a
- [x] 2.3 Annotate `eco_off_time` and `eco_auto_off` with `unit="h"` in ac200l, ac300, ac500
- [x] 2.4 Annotate `dc_eco_power` and `ac_eco_power` with `unit="W"` in ac200l, ac300, ac500

## 3. v2_base.py — Strip unit suffix in build_setter_command

- [x] 3.1 In `build_setter_command`, for `UintField` with a non-None `unit`, call `value.removesuffix(field.unit).strip()` on string input before int conversion
- [x] 3.2 Write unit tests: suffixed input accepted, bare input accepted, wrong-case suffix not stripped (raises ValueError)

## 4. cli.py — Display and hints

- [x] 4.1 Add a `_field_hint(field_obj)` helper returning the hint string for each field type (bool, enum, ranged uint, unranged uint with/without unit, fallback empty)
- [x] 4.2 In `_print_verbose`, replace the name-based unit decoration block with a `field.unit` lookup via `device.control_struct`
- [x] 4.3 Add the dimmed hint column to the CONTROLS table render loop
- [x] 4.4 Update `_show_field_help` to use `_field_hint()` instead of its current inline type-name logic
- [x] 4.5 Write unit tests for `_field_hint` covering all field type branches

## 5. Verification

- [x] 5.1 Run the full test suite and confirm it passes
- [x] 5.2 Manually confirm `voltkeeper status --verbose` shows correct unit suffixes and hint column for a live or mocked device
