## 1. Fix EL100V2 documentation

- [x] 1.1 Fix ABOUTME line 2 in `src/voltkeeper/core/devices/el100v2.py`: change `AC240` to `AC200PL`
- [x] 1.2 Add `TODO(hardware): verify against physical device` to EL100V2 ABOUTME (matching sibling Elite devices EL10V2, EL30V2, EL400)

## 2. Remove CLI commands

- [x] 2.1 Remove `from .annotate import annotate_loop` import from `src/voltkeeper/cli.py`
- [x] 2.2 Remove `from .probe import emit_yaml, probe_device` import from `src/voltkeeper/cli.py`
- [x] 2.3 Remove `from .validate import validate_profile` import from `src/voltkeeper/cli.py`
- [x] 2.4 Remove the `probe` CLI command function and its `@cli.command("probe")` decorator from `src/voltkeeper/cli.py`
- [x] 2.5 Remove the `annotate` CLI command function and its `@cli.command("annotate")` decorator from `src/voltkeeper/cli.py`
- [x] 2.6 Remove the `validate-profile` CLI command function and its `@cli.command("validate-profile")` decorator from `src/voltkeeper/cli.py`

## 3. Remove source modules

- [x] 3.1 Delete `src/voltkeeper/probe.py`
- [x] 3.2 Delete `src/voltkeeper/validate.py`
- [x] 3.3 Delete `src/voltkeeper/annotate.py`

## 4. Remove tests

- [x] 4.1 Delete `tests/test_probe.py`
- [x] 4.2 Delete `tests/test_validate.py`
- [x] 4.3 Delete `tests/test_annotate.py`
- [x] 4.4 Remove `test_probe_emit_capabilities_v2`, `test_probe_emit_capabilities_no_home_data`, and `test_probe_emit_capabilities_short_data` from `tests/test_voltkeeper.py` (lines 3079–3113)
- [x] 4.5 Remove `test_ac2a_probe_real_full_validate_no_errors` and its `from voltkeeper.validate import validate_profile` import from `tests/test_ac2a_probe.py` (lines 72–82)

## 5. Remove spec

- [x] 5.1 Delete `openspec/specs/probe-capabilities/spec.md`

## 6. Verification

- [x] 6.1 Run `mise run lint` and fix any issues
- [x] 6.2 Run `mise run typecheck` and fix any issues
- [x] 6.3 Run `mise run test` and confirm all remaining tests pass
