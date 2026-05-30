## Why

Three CLI commands (`probe`, `validate-profile`, `annotate`) were bootstrap reverse-engineering tools from before the Bluetti APK v3.0.9 was decompiled. Now that the APK source is available, all register addresses, field types, and enum values are defined by `ProtocolParserV2.java` and `DeviceConnUtil.java`. The `verify` command provides comprehensive live hardware validation. These bootstrap tools are dead weight that add maintenance burden and user confusion. Additionally, the EL100V2 device class has a minor ABOUTME inaccuracy to fix before the physical device arrives.

## What Changes

- **Fix EL100V2 ABOUTME comment**: Replace incorrect `AC240` with `AC200PL` in the template chain, and add the `TODO(hardware)` banner that sibling Elite devices (EL10V2, EL30V2, EL400) already carry.
- **Remove `probe` command** (`voltkeeper probe`): Raw register capture and protocol detection. Superseded by `verify` Tier 1 (live poll + parse) and APK analysis for protocol knowledge.
- **Remove `validate-profile` command** (`voltkeeper validate-profile`): Offline stuck-at field check. Superseded by `verify` Tier 1 (same check done live with better output).
- **Remove `annotate` command** (`voltkeeper annotate`): Byte-level diff watcher for manual field discovery. Superseded by APK decompilation for register-to-field mapping.
- **Remove supporting modules**: `probe.py`, `validate.py`, `annotate.py`, and their test files.
- **Remove `probe-capabilities` spec**: This spec only covers probe YAML output behavior. With probe removed, the requirement no longer exists.

## Capabilities

### New Capabilities
<!-- None — this is a removal, not a new feature. -->

### Modified Capabilities

- `probe-capabilities`: **Removed** — this spec defined probe YAML ctrl_event decoding behavior. With `probe` removed, no replacement is needed (verify reports fields through the device class parse path, not raw hex).

## Impact

- **Removed files**: `src/voltkeeper/probe.py`, `src/voltkeeper/validate.py`, `src/voltkeeper/annotate.py`
- **Removed CLI commands**: `probe`, `validate-profile`, `annotate`
- **Removed imports**: `from .probe import ...`, `from .validate import ...`, `from .annotate import ...` in `cli.py`
- **Removed tests**: Any test files that exercise probe, validate-profile, or annotate
- **Removed spec**: `openspec/specs/probe-capabilities/spec.md`
- **Modified file**: `src/voltkeeper/core/devices/el100v2.py` (ABOUTME comment only)
- **No API changes, no dependency changes**
