## 1. No-overwrite report writer

- [x] 1.1 TDD: add tests in `tests/test_verify.py` for a unique-path helper — existing file gets `_v2` before `.yaml`, `_v2` occupied gets `_v3`, non-existent path unchanged
- [x] 1.2 Implement the unique-path logic in `core/verify.py` and apply it inside `write_report` so all callers (default and `--output`) are covered

## 2. Default filename format

- [x] 2.1 TDD: add tests for the default filename builder — plain run yields `verify_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml`, `--ground-truth` run yields the `verify-ground-truth_` prefix, timestamp is UTC minute-precision with literal `Z`
- [x] 2.2 Update `cli/verify.py` to build the default path per the new grammar, capturing the timestamp at session start

## 3. Docs

- [x] 3.1 Update `docs/verify.md` output-path section: new filename grammar, no-overwrite `_v<N>` rule, `hardware-data/` default directory (fixes the current-directory drift)
- [x] 3.2 Check docs nav/index references to verify output paths and update any stale examples

## 4. Verification

- [x] 4.1 Run the full test suite; confirm pristine output
- [x] 4.2 End-to-end check with the fake/test device path if available, or a dry `write_report` invocation, confirming two consecutive writes produce `..._v2.yaml` rather than overwriting
