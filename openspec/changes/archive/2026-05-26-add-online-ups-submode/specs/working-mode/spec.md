## ADDED Requirements

### Requirement: ups_mode exposed on V1 devices that support Online UPS

V1 device classes whose APK `DeviceFunction` flags Online UPS support (`AC300`, `AC500`, `AC200L`, `AC200PL`, `EP500`, `EP600`) SHALL expose `ups_mode` as a writable `BoolField` on register 3035. The field SHALL accept truthy values (`on`, `1`, `true`, `yes`) mapping to integer `1` (Online) and falsy values mapping to integer `0` (Standby). Devices that do not support Online UPS (`EB3A`, `AC60`, `AC180`, `AC2A`, `AORA Mini`) SHALL NOT expose this field.

#### Scenario: Writable on AC300
- **WHEN** `voltkeeper write <ac300-address> ups_mode on` runs
- **THEN** the system emits `WriteSingleRegister(address=3035, value=1)`

#### Scenario: Writable off on EP600
- **WHEN** `voltkeeper write <ep600-address> ups_mode off` runs
- **THEN** the system emits `WriteSingleRegister(address=3035, value=0)`

#### Scenario: Not exposed on AC2A
- **WHEN** inspecting `AC2A.WRITABLE_FIELD_NAMES`
- **THEN** `"ups_mode"` is not present
- **WHEN** `voltkeeper write <ac2a-address> ups_mode on` runs
- **THEN** the command fails with an "Unknown writable field" error before any BLE traffic

### Requirement: ups_mode documented as a sub-mode of working_mode

The documentation SHALL clarify that `ups_mode` is meaningful only when `working_mode = STANDARD_UPS`. The device-models documentation SHALL include a per-device "Online UPS supported" column showing which device classes expose the field.

#### Scenario: Documentation lists Online UPS support
- **WHEN** reading `docs/source/protocol/device-models.md`
- **THEN** the feature matrix table includes an "Online UPS" column with `y` for supporting devices and `—` for others

### Requirement: V2 Online UPS field exposed when APK parse offset is identified

When the implementation identifies the V2 byte offset for the UPS sub-mode in `INV_BASE_SETTINGS` (register 2000) from `ProtocolParserV2.parseInvBaseSettings`, V2 device classes whose APK `DeviceFunction.hasOnlineUPS` is true (e.g. `EL10V2`, `EL30V2`, `EL100V2`, `EL400`) SHALL expose `ups_mode` as a writable field. If the offset cannot be confidently identified, V2 exposure SHALL be deferred to a follow-up change rather than guessed.

#### Scenario: V2 read decodes Online state
- **GIVEN** the V2 offset has been identified
- **WHEN** an `INV_BASE_SETTINGS` block is parsed with the UPS sub-mode byte set to `1`
- **THEN** the result contains `ups_mode = True`

#### Scenario: V2 write produces the correct command
- **GIVEN** the V2 offset has been identified
- **WHEN** `voltkeeper write <el400-address> ups_mode on` runs
- **THEN** the system emits the correct `WriteSingleRegister` (or multi-register write) per the identified APK encoding
