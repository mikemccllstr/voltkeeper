## 1. Fix AC2A version byte parsing

- [x] 1.1 Fix mcu_type to read 2 bytes as big-endian uint16: `mcu_type = (data[off] << 8) | data[off + 1]`
- [x] 1.2 Fix version word-swap: `version = (_u16(data, off + 4) << 16) | _u16(data, off + 2)`
- [x] 1.3 Add `_MCU_TYPE_NAMES` dict mapping type codes to component name prefixes (1=arm, 2=dsp, 3=bms, 0=iot, 11=hmi1, 12=hmi2)
- [x] 1.4 Replace `software[N]` keys with named keys: `{name}_version`, fallback `mcu{N}_version` for unknown codes
- [x] 1.5 Store raw integer version value in result dict (not formatted string) for consistency with V1 parse output

## 2. Update test fixture

- [x] 2.1 Update `ac2a_inv_base_bytes` in conftest.py to include non-zero mcu_type bytes at offset 26+ (e.g., `00012e190003` for ARM v208409, `000234540003` for DSP v210004) while preserving non-version bytes

## 3. Update test assertions

- [x] 3.1 Update `test_software_versions_present` in test_voltkeeper.py to assert `arm_version` and `dsp_version` keys with expected integer values
- [x] 3.2 Update `test_build_report_firmware_includes_v2_software_number` in test_verify.py to validate new named keys (e.g., `arm_version`) are captured by firmware substring match

## 4. Update CLI --verbose display

- [x] 4.1 Change `_print_verbose` SOFTWARE VERSIONS filter from `k.startswith("software[")` to `k.endswith("_version")`
- [x] 4.2 Format display: derive label from key name (strip `_version` suffix, uppercase), format version value with `_format_version()`, align values under labels

## 5. Quality gate

- [x] 5.1 Run `mise run check` (lint + typecheck + tests) and fix any failures
