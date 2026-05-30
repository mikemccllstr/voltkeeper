## Context

Three CLI commands (`probe`, `validate-profile`, `annotate`) were built during early reverse-engineering of the Bluetti protocol. They served as bootstrap tools for discovering register layouts, validating field values, and interactively mapping byte-level changes to field names. The Bluetti APK v3.0.9 is now fully decompiled (`bluetti-files/BLUETTI-v3.0.9.apk/jadx_out/`), providing the authoritative source for all register addresses, field types, and enum values. The `verify` command (`src/voltkeeper/core/verify.py`) provides comprehensive live hardware validation with a six-tier test that covers read, parse, identity-write, and probe-write validation. These bootstrap tools no longer serve a purpose and create maintenance overhead, test execution time, and user confusion about which command to use.

Additionally, the EL100V2 device class has a documentation-only defect in its ABOUTME comment that references a non-existent device in the APK template chain.

## Goals / Non-Goals

**Goals:**
- Remove the `probe`, `validate-profile`, and `annotate` CLI commands
- Remove their supporting modules (`probe.py`, `validate.py`, `annotate.py`)
- Remove their dedicated test files
- Remove the `probe-capabilities` spec (scoped entirely to probe YAML output)
- Fix the EL100V2 ABOUTME template chain comment
- Add TODO(hardware) banner to EL100V2 matching sibling Elite devices
- Preserve valuable test fixture (`tests/fixtures/ac2a_probe_real.yml`) and the BcdSerialField/SN parsing tests that use it

**Non-Goals:**
- Do not remove or modify the `verify` command or its supporting code
- Do not change any device class behavior (EL100V2 or otherwise)
- Do not remove the `probe`-related scrub helpers (`scrub_profile`, `split_model_sn` in `scrub.py`) that are used elsewhere
- Do not modify any existing spec other than `probe-capabilities`

## Decisions

### Keep the AC2A probe fixture

`tests/fixtures/ac2a_probe_real.yml` is a capture from real hardware with synthetic SN. Tests in `tests/test_ac2a_probe.py` use this fixture to validate BcdSerialField encoding, SN parsing, device model naming, and pack voltage scale. These are valuable regression tests independent of the probe tool itself. The fixture file stays, the `test_ac2a_probe.py` file stays, and only the `test_ac2a_probe_real_full_validate_no_errors` test (which imports `validate_profile`) gets removed.

### Remove `_emit_capabilities` test from test_voltkeeper.py

Three tests in `test_voltkeeper.py` (lines 3079–3113) exercise `probe._emit_capabilities`. This is a probe-internal helper with no value outside the probe module. These tests are removed along with the probe module.

### No backwards compatibility

These commands have no other consumers. The MQTT daemon, REST API, and verify command do not depend on probe/validate/annotate. The removal is clean.

## Risks / Trade-offs

- **Risk**: A community member submits raw register hex from an unknown device not in the APK.
  - **Mitigation**: The APK v3.0.9 covers all current Bluetti devices. Any new device would need a newer APK version anyway. Raw hex can still be shared informally — the probe tool was never a requirement for that.

- **Risk**: Someone relied on `probe` for protocol detection of an unknown device prefix.
  - **Mitigation**: The registry now covers all known BLE name prefixes from the APK. `build_device` already handles registry lookup. If a truly unknown prefix appears, the `_detect_protocol` logic was always a stopgap anyway — the real answer is to add the device to the registry.

- **Risk**: Renaming `test_ac2a_probe.py` might break CI file discovery.
  - **Decision**: Do not rename. The file tests parsing of a fixture originally captured by probe, but the tests themselves hit `AC2A.parse()` directly — they don't import probe or validate (except the one test being removed). The filename is historical, not a dependency.
