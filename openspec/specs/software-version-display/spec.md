## Purpose

Parse MCU software version entries from the INV_BASE_INFO register block for all V2 devices using the APK v3.0.10 byte layout, mapping type codes to human-readable component names.
## Requirements
### Requirement: MCU type codes mapped to human-readable names

`V2Base` SHALL map MCU type codes to component name keys using the APK's `DeviceFirmware` enum mapping, for all V2 devices. Known types (1=ARM, 2=DSP, 3=BMS, 0=IOT, 11=HMI1, 12=HMI2) SHALL produce keys like `arm_version`, `dsp_version`. Unknown type codes SHALL produce fallback keys `mcu{N}_version` so no data is silently dropped. The mapping table SHALL live in the V2 base module, not in a device subclass.

#### Scenario: Known MCU type produces named key

- **WHEN** mcu_type = 1 (ARM)
- **THEN** the parse result key is `arm_version`

#### Scenario: Known BMS type produces named key

- **WHEN** mcu_type = 3 (BMS)
- **THEN** the parse result key is `bms_version`

#### Scenario: Unknown MCU type produces fallback key

- **WHEN** mcu_type = 99 (unknown)
- **THEN** the parse result key is `mcu99_version`

### Requirement: Named versions displayed in --verbose status

`voltkeeper status --verbose` SHALL display software versions with human-readable component labels derived from the parse-result key names. The section SHALL be titled "SOFTWARE VERSIONS" and SHALL list each version with its formatted value. The CLI SHALL filter for keys ending in `_version` rather than the old `software[` prefix.

#### Scenario: Versions displayed with component labels

- **WHEN** `--verbose status` runs on an AC2A and the parse result contains `arm_version: 208409` and `dsp_version: 210004`
- **THEN** the output includes a "SOFTWARE VERSIONS" section
- **THEN** the output includes `ARM:  v2084.09`
- **THEN** the output includes `DSP:  v2100.04`

#### Scenario: No versions displayed when none present

- **WHEN** `--verbose status` runs and no `_version` keys exist in the parse result
- **THEN** no "SOFTWARE VERSIONS" section is printed

### Requirement: Named versions captured in verify reports

`voltkeeper verify` SHALL capture the named version keys (e.g., `arm_version`, `dsp_version`) in its report's `device.firmware` section via the existing substring match on `_FIRMWARE_FIELD_SUBSTRINGS`. No changes to the verify report logic are needed, but the test suite SHALL validate that named keys are captured.

#### Scenario: Named versions appear in verify report firmware section

- **WHEN** a verify run completes on an AC2A with version keys `arm_version` and `dsp_version` in the tier-1 parse result
- **THEN** the report's `device.firmware` section includes `arm_version` and `dsp_version`

### Requirement: V2 software version bytes parsed correctly

`V2Base` SHALL parse software version entries from the INV_BASE_INFO register block for all V2 devices, using the correct byte layout: MCU type as a 2-byte big-endian unsigned integer at bytes `[off, off+1]`, and version as a word-swapped 4-byte value formed from register halves at `off+4` (high) and `off+2` (low). No entries with `mcu_type > 0` and `version > 0` SHALL be skipped due to byte-layout errors. This matches APK v3.0.10 `ProtocolParserV2.parseInvBaseInfo`, which parses the 6-entry array at bytes 26–61 for every V2 device.

#### Scenario: ARM version extracted from fixture data

- **WHEN** the INV_BASE_INFO payload contains `00 01 2e 19 00 03` at byte offset 26 (entry 0)
- **THEN** mcu_type is parsed as `(0x00 << 8) | 0x01 = 1` (ARM)
- **THEN** version is parsed as `(_u16(off+4) << 16) | _u16(off+2) = 0x00032e19 = 208409`
- **THEN** the result contains `arm_version: 208409`

#### Scenario: DSP version extracted from fixture data

- **WHEN** the INV_BASE_INFO payload contains `00 02 34 54 00 03` at byte offset 32 (entry 1)
- **THEN** mcu_type is parsed as `(0x00 << 8) | 0x02 = 2` (DSP)
- **THEN** version is parsed as `0x00033454 = 210004`
- **THEN** the result contains `dsp_version: 210004`

#### Scenario: Empty entry skipped

- **WHEN** the INV_BASE_INFO payload has `00 00 00 00 00 00` at a 6-byte entry position
- **THEN** that entry is skipped (mcu_type = 0)

#### Scenario: EL100V2 reports firmware versions

- **WHEN** an `El100V2` instance parses an INV_BASE_INFO payload with populated version entries
- **THEN** the result contains the corresponding `*_version` keys (the APK firmware list for the EL100V2 chain is IOT, ARM, DSP, BMS)

