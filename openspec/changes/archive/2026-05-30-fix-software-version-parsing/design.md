## Context

The AC2A (and all V2-protocol devices) report software versions in the INV_BASE_INFO register block (address 1100). Starting at byte offset 26, there are up to 6 entries, each 6 bytes:

```
[byte0] [byte1] [byte2] [byte3] [byte4] [byte5]
 mcu_hi  mcu_lo   ver2    ver3    ver0    ver1
```

- **mcu_type**: 2 bytes concatenated as hex `(byte0 << 8) | byte1`, yielding a type code per the APK's `DeviceFirmware` enum
- **version**: 4 bytes, word-swapped: `(register_at_off+4 << 16) | register_at_off+2`

The APK maps MCU type codes to human-readable names via `DeviceFirmware` (1=ARM, 2=DSP, 3=BMS, etc.).

The current `_fill_software_versions` in `ac2a.py` has two bugs:
1. `mcu_type = data[off]` reads only 1 byte — on the real AC2A fixture, the first byte is always `0x00`, causing all entries to be skipped (`mcu_type > 0` is False)
2. `version = (_u16(off+2) << 16) | _u16(off+4)` does not word-swap — even if entry weren't skipped, the version number would be wrong

V1 devices (`v1_base.py`) have their own `_fill_software_versions` with correct word-swap logic and fixed-position labels. V2 differs in that positions are variable (the MCU type tells you which component occupies each slot), so a name mapping is required.

## Goals / Non-Goals

**Goals:**
- Fix the two byte-layout bugs in `ac2a.py:_fill_software_versions` so that real AC2A devices report all non-zero software versions
- Map MCU type codes to human-readable component names (ARM, DSP, BMS, IOT, HMI1, HMI2, etc.)
- Display named versions in `--verbose status` and `verify` reports

**Non-Goals:**
- V1 device version display — V1 versions are already parsed correctly (though without friendly names); improving V1 display is out of scope
- Extending version parsing to ALL V2 devices — only `AC2A` has `_fill_software_versions` today; this fix stays scoped to AC2A

## Decisions

### D1: Key naming — named keys vs. indexed keys

**Chosen:** Named keys like `arm_version`, `dsp_version`, `bms_version`, using the MCU type name as the key prefix. Fallback for unknown type codes: `mcu{N}_version`.

**Rationale:** V2 entries have variable positions (ARM might be at index 0 or 2 depending on device). Named keys are self-documenting. They match the existing verify.py `_FIRMWARE_FIELD_SUBSTRINGS` pattern (which includes `"version"`). The CLI display can derive the display label from the key name.

**Alternative considered:** Keep indexed `software[N]` keys and add a separate name field. Rejected because it requires the display layer to correlate two fields, adds complexity, and doesn't help verify.py which looks for substrings.

### D2: MCU type → name mapping location

**Chosen:** Module-level constant `_MCU_TYPE_NAMES: dict[int, str]` in `ac2a.py`.

**Rationale:** Only AC2A uses this today. If other V2 devices adopt `_fill_software_versions`, the mapping can be moved to `v2_base.py` or `core/utils.py` later. YAGNI.

**Alternative considered:** Shared module in `core/`. Rejected because premature — no other V2 device uses this method yet.

### D3: Byte layout fix details

**mcu_type fix:**
```python
# Before (bug — reads 1 byte, first byte is 0x00):
mcu_type = data[off]

# After (reads 2 bytes as big-endian uint16):
mcu_type = (data[off] << 8) | data[off + 1]
```

**version fix:**
```python
# Before (bug — no word-swap):
version = (_u16(data, off + 2) << 16) | _u16(data, off + 4)

# After (word-swap the two 16-bit register halves):
version = (_u16(data, off + 4) << 16) | _u16(data, off + 2)
```

This matches the APK's `bit32HexSwap` which reorders 4 bytes as `[2][3][0][1]`.

### D4: Display format

**Chosen in CLI:** Key name derived as section label (uppercased MCU name), value shown as formatted version string. Example:
```
SOFTWARE VERSIONS
  ARM:  v2084.09
  DSP:  v2100.04
  BMS:  vXXXX.XX
```

The CLI filters for keys ending in `_version` instead of the old `software[` prefix.

**Chosen in verify reports:** No change needed — the existing `_FIRMWARE_FIELD_SUBSTRINGS = ("ver", "version", "firmware", "software")` already matches `_version` keys.

## Risks / Trade-offs

- **[Risk] Test fixture doesn't exercise the fix**: The current `ac2a_inv_base_bytes` fixture has zero-valued first bytes, which the old code also rejects. → **Mitigation**: Update the fixture to include non-zero mcu_type bytes (preserving the other fields) so the test validates the fix produces the expected version output.
- **[Risk] Unknown MCU type codes**: Future devices may report type codes not in our mapping. → **Mitigation**: Fallback key `mcu{N}_version` ensures unknown codes are still captured, not silently dropped.
- **[Risk] AC2A-only scope**: Other V2 devices may have the same bug but won't be fixed. → **Mitigation**: Accepted. Those devices don't have `_fill_software_versions` today, so they're unaffected.
