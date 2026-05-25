## ADDED Requirements

### Requirement: V1 protocol version propagates from device class to probe

The system SHALL use the `protocol_version` attribute of each V1 device subclass (as defined in the device class) to determine probe block sizes. V1 device classes SHALL override `protocol_version` with the correct `minProtocolVer` value from the APK's `DeviceConnUtil.getDeviceFunc()`.

#### Scenario: EB3A probe uses correct block sizes
- **WHEN** an EB3A device is discovered via the registry shortcut in `_detect_protocol`
- **THEN** `protocol_version` is 1019 (not 0)
- **THEN** `_v1_base_real_data_size(1019)` returns 58 registers (not 53)
- **THEN** `_v1_bms_pack_size(1019)` returns 115 registers (not 10)
- **THEN** `_v1_settable_data_size(1019)` returns 67 registers (not 36)

#### Scenario: AC200L probe uses correct block sizes
- **WHEN** an AC200L device is discovered via the registry shortcut in `_detect_protocol`
- **THEN** `protocol_version` is 1022 (not 0)
- **THEN** `_v1_base_real_data_size(1022)` returns 58 registers
- **THEN** `_v1_bms_pack_size(1022)` returns 115 registers
- **THEN** `_v1_settable_data_size(1022)` returns 82 registers

#### Scenario: Dynamic probe fallback still works
- **WHEN** a device is NOT found in the registry
- **THEN** `_detect_protocol` falls back to reading register 16 (MODBUS_PROTOCOL_VER)
- **THEN** the dynamic value determines V1/V2 classification and block sizes

### Requirement: Single device name regex shared between modules

The system SHALL define a single authoritative `_DEVICE_NAME_SN_RE` regex in `bluetooth/__init__.py` that matches all supported device model prefixes followed by a serial number suffix. The `scrub.py` module SHALL import and use this regex instead of maintaining a separate pattern.

#### Scenario: Recognized model prefix matches
- **WHEN** a BLE device name is "AC2A1234567890123"
- **THEN** `_DEVICE_NAME_SN_RE` matches with group(1)="AC2A" and group(2)="1234567890123"

#### Scenario: Short serial number matches
- **WHEN** a BLE device name is "EB3A123456"
- **THEN** `_DEVICE_NAME_SN_RE` matches with group(1)="EB3A" and group(2)="123456"

#### Scenario: New alphanumeric-suffix model matches
- **WHEN** a BLE device name is "HB500S1234567890123"
- **THEN** `_DEVICE_NAME_SN_RE` matches with group(1)="HB500S" and group(2)="1234567890123"

#### Scenario: scrub.py uses shared regex
- **WHEN** `scrub.py` scrubs a device name
- **THEN** the regex used is the same `_DEVICE_NAME_SN_RE` from `bluetooth/__init__.py`

### Requirement: APK version references updated to 3.0.9

All comments referencing "APK 3.0.8" in the source code SHALL be updated to reference "APK 3.0.9". No functional code changes are implied by this requirement.

#### Scenario: v1_base.py comment updated
- **WHEN** reading `v1_base.py`
- **THEN** the comment line previously reading "APK 3.0.8" now reads "APK 3.0.9"
