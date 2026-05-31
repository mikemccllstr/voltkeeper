## 1. Implementation

- [x] 1.1 Add `_device_from_scan(sr: ScanResult)` helper function in `cli.py` that wraps `build_device()` with a try/except and a friendly error message
- [x] 1.2 Replace `build_device(address, sr.name)` call in `status` command with `_device_from_scan(sr)`
- [x] 1.3 Replace `build_device(address, sr.name)` call in `write` command with `_device_from_scan(sr)`
- [x] 1.4 Replace `build_device(address, sr.name)` call in `get` command with `_device_from_scan(sr)`
- [x] 1.5 Replace `build_device(address, sr.name)` call in `daemon run` command with `_device_from_scan(sr)`
- [x] 1.6 Replace `build_device(address, sr.name)` call in `daemon ping` command with `_device_from_scan(sr)`
- [x] 1.7 Replace `build_device(address, sr.name)` call in `ac2a_load_test` command with `_device_from_scan(sr)`
- [x] 1.8 Replace `build_device(address, _device_name)` call in verbose name resolution path with `_device_from_scan(sr)`
- [x] 1.9 Replace `build_device(address, sr.name)` call in `verify` command with `_device_from_scan(sr)`

## 2. Quality Checks

- [x] 2.1 Run `mise run lint` and fix any issues
- [x] 2.2 Run `mise run typecheck` and fix any issues
- [x] 2.3 Run `mise run test` and confirm all tests pass
