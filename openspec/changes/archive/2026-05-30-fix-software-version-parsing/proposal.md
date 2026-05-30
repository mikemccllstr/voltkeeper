## Why

The AC2A software version parsing in `_fill_software_versions` has two byte-layout bugs — mcu_type reads 1 byte instead of 2, and version bytes are not word-swapped — causing all 6 version entries to be silently suppressed. Both `voltkeeper status --verbose` and `voltkeeper verify` produce no version output for AC2A devices, despite the data being present in the INV_BASE_INFO register block. The real Bluetooth app shows ARM v2084.09, DSP v2100.04, etc.; voltkeeper shows nothing.

## What Changes

- Fix `ac2a.py:_fill_software_versions` to read mcu_type as a 2-byte concatenated-hex value and word-swap the 4 version bytes (swap the two 16-bit register halves)
- Map mcu_type codes to human-readable component names using the APK's `DeviceFirmware` enum (1=ARM, 2=DSP, 3=BMS, 0=IOT, 11=HMI1, 12=HMI2, etc.)
- Display versions as named components in `--verbose` status output instead of anonymous `software[N]: MCU=N`
- Update the test fixture in `conftest.py` to include non-zero mcu_type bytes so the fix is testable

## Capabilities

### New Capabilities

- `software-version-display`: Parse 2-byte MCU type codes from INV_BASE_INFO register data, word-swap version bytes correctly, map type codes to human-readable component names (ARM, DSP, BMS, HMI, IOT), and display named versions in --verbose status and verify reports.

### Modified Capabilities

None — existing behavior is broken (zero versions displayed), so this is a bugfix, not a requirement change.

## Impact

- `src/voltkeeper/core/devices/ac2a.py`: `_fill_software_versions` method — fix byte parsing, add name mapping
- `src/voltkeeper/cli.py`: `_print_verbose` SOFTWARE VERSIONS section — display format changes from `software[N]: MCU=N` to `NAME: vXXXX.XX`
- `src/voltkeeper/core/verify.py`: `build_report` firmware extraction — picks up new key names via existing `"software"` substring match
- `tests/conftest.py`: AC2A INV_BASE_INFO fixture — add non-zero mcu_type bytes
- `tests/test_voltkeeper.py`: version assertion test — update to match new key names/format
