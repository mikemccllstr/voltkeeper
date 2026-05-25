## Why

The CONTROLS section of verbose status output gives users no indication of what values are valid for each writable field, and the unit decoration (h, W) on eco fields is driven by hardcoded field-name checks that miss several device variants. Surfacing valid-value hints inline — drawn from field metadata that already exists — removes the need to run a separate `--help-field` query for every field.

## What Changes

- `UintField` gains an optional `unit` attribute (`"h"`, `"W"`, or `None`)
- `DeviceStruct.add_uint_field` accepts and threads `unit` through to the field
- All device files annotate eco time fields with `unit="h"` and eco power fields with `unit="W"` — this also fixes a latent bug where `eco_off_time` / `eco_auto_off` on AC200L, AC300, and AC500 were never getting unit suffixes in display
- `build_setter_command` strips the unit suffix before int conversion, so `"2h"` and `"2"` are both accepted
- `_print_verbose` drops the name-based unit checks and reads `field.unit` instead
- A `_field_hint()` helper in `cli.py` produces a dimmed hint string for each field type: `[on|off]`, `[opt1|opt2|...]`, `[0-100]`, `[integer]`, `[integer]h`, etc.
- The CONTROLS table gains a third column rendering that hint in dim style
- `_show_field_help` is updated to use `_field_hint` for consistency

## Capabilities

### New Capabilities

- `controls-field-hints`: Inline valid-value hints in the CONTROLS section of verbose status output, driven by field metadata rather than name-based heuristics

### Modified Capabilities

- `interface-value-display`: The unit-suffix display requirement is broadened — units are now derived from `field.unit` metadata rather than a hardcoded field-name list, and the set of fields covered expands to include the AC200L/AC300/AC500 naming variants

## Impact

- `src/voltkeeper/core/struct.py` — `UintField`, `DeviceStruct.add_uint_field`
- `src/voltkeeper/core/devices/v2_base.py` — `build_setter_command`
- `src/voltkeeper/core/devices/` — 10 device files annotated (el30v2, el10v2, el100v2, el400, ac180, ac60, ac2a, ac200l, ac300, ac500)
- `src/voltkeeper/cli.py` — `_print_verbose`, new `_field_hint` helper, `_show_field_help`
- No API, protocol, or external dependency changes
