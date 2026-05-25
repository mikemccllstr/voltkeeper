## Context

The CONTROLS section of `voltkeeper status --verbose` iterates over writable fields and displays each field's current value. Unit decoration (appending `h` or `W`) is applied by name-matching against a hardcoded list in `_print_verbose`. `build_setter_command` in `v2_base.py` does not strip unit suffixes from user input. There is no inline hint to tell users what values are valid for each field.

Field metadata (range, enum, bool type) already exists in the `DeviceField` subclasses in `struct.py`. The gap is that units are not stored there — they live only in the display layer.

## Goals / Non-Goals

**Goals:**
- Store unit strings on `UintField` so they travel with the field, not with the display code
- Fix the latent bug where AC200L/AC300/AC500 eco fields never get unit suffixes
- Accept unit-decorated input on write (`"2h"` → `2`) without breaking bare input (`"2"`)
- Show a dimmed hint column in CONTROLS telling users what to pass on a write command

**Non-Goals:**
- Adding units to field types other than `UintField` (DecimalField etc. not used in controls)
- Changing the `system_timezone` display transform (UTC±N formatting — left as name-based)
- Modifying the HTTP API or daemon write path (unit stripping happens in `build_setter_command`, which both paths share)

## Decisions

### Unit as a field attribute, not a display-layer lookup

**Decision**: Add `unit: str | None = None` to `UintField.__init__` and `DeviceStruct.add_uint_field`.

**Rationale**: The unit is a property of the register's semantics, not of how the CLI chooses to display it. Keeping it in the struct means the display layer, the parser, and any future consumers (API field metadata, MQTT) all get it from one place without name-matching.

**Alternative considered**: Keep the name-based list in `cli.py` and duplicate a similar list in `build_setter_command`. Rejected — two lists with no connection will drift.

### Strip unit suffix in `build_setter_command`, not in the CLI

**Decision**: `build_setter_command` calls `value.removesuffix(field.unit).strip()` on string input before int conversion.

**Rationale**: `build_setter_command` is the single validation choke point for both direct BLE and daemon-forwarded writes. Stripping there means the behaviour is consistent regardless of call site. `removesuffix` is a no-op when the suffix is absent, so bare integers continue to work.

### Hint column rendered dim, not as a separate section

**Decision**: A third column in the CONTROLS table, styled with `click.style(..., dim=True)`.

**Rationale**: Users who know what they're doing can scan the value column and ignore the hint. Users who need help see it immediately without running `--help-field`. Dim styling keeps visual weight on the current value.

### `_field_hint()` shared between `_print_verbose` and `_show_field_help`

**Decision**: Extract hint generation into a module-level `_field_hint(field_obj)` helper and call it from both functions.

**Rationale**: Avoids duplication and keeps `--help-field` output consistent with the inline hint.

## Risks / Trade-offs

- **Line width**: Enum hint strings can be long (e.g. `[normal|power_saving|standby]`). This is acceptable — `--verbose` output is already wide and the user has opted in.
- **`system_timezone` is a special case**: It remains name-matched in the display path. The hint for it will fall through to `[integer]` since it's an unranged `UintField` with no unit, which is accurate enough.
- **Unit stripping is case-sensitive**: `removesuffix("h")` will not strip `"H"`. Device units (`h`, `W`) are lowercase and single-character; this is not a practical concern.
