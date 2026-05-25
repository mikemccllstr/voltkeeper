## ADDED Requirements

### Requirement: Child Lock ON/OFF register writable

The system SHALL expose register 2072 as a writable `BoolField` named `child_lock` on V2 device classes whose APK `DeviceFunction.childLockCtrl` flag is `true`. Writing `True` SHALL send value 0x20 (bit 5 set) to register 2072; writing `False` SHALL send value 0x10 (bit 4 set) to register 2072.

#### Scenario: Enable child lock
- **WHEN** user writes `child_lock = on` to a V2 device that supports child lock
- **THEN** the system sends WriteSingleRegister to address 2072 with value 32 (0x20, bit 5)

#### Scenario: Disable child lock
- **WHEN** user writes `child_lock = off` to a V2 device that supports child lock
- **THEN** the system sends WriteSingleRegister to address 2072 with value 16 (0x10, bit 4)

#### Scenario: Child lock not writable on unsupported devices
- **WHEN** a device class does not include `child_lock` in its WRITABLE_FIELD_NAMES
- **THEN** `build_setter_command("child_lock", ...)` raises an appropriate error
- **THEN** `child_lock` does not appear in the CLI writable field listing

### Requirement: Child Lock level register writable

The system SHALL expose register 2076 as a writable `IntField` named `child_lock_level` on V2 device classes that support child lock. The field SHALL accept values 1 and 2.

- Level 1: Prohibits turning ON output switches (outputs can still be turned OFF)
- Level 2: Prohibits both turning ON and OFF all output switches

#### Scenario: Set child lock level 1
- **WHEN** user writes `child_lock_level = 1` to a supported V2 device
- **THEN** the system sends WriteSingleRegister to address 2076 with value 1

#### Scenario: Set child lock level 2
- **WHEN** user writes `child_lock_level = 2` to a supported V2 device
- **THEN** the system sends WriteSingleRegister to address 2076 with value 2

#### Scenario: Invalid child lock level rejected
- **WHEN** user writes `child_lock_level = 3` to a supported V2 device
- **THEN** the write is rejected with a descriptive error indicating valid range is 1-2

### Requirement: Child lock fields read from INV_BASE_SETTINGS

The child lock control state SHALL be read from the INV_BASE_SETTINGS data block (register 2000). `childLockCtrl` SHALL be parsed from the enable-list at data position 145 (registrar offset within the block). `childLockLevel` SHALL be parsed from data position 153.

#### Scenario: Child lock state parsed from block read
- **WHEN** reading INV_BASE_SETTINGS (address 2000) on a device that supports child lock
- **THEN** `child_lock` reflects the parsed `childLockCtrl` value (0/1 interpreted from the bitfield at data position 145)
- **THEN** `child_lock_level` reflects the parsed value at data position 153

### Requirement: Child lock feature-gated per device

Only device classes whose APK `DeviceFunction.childLockCtrl = true` SHALL expose child lock writable fields. The AC180 base class has `childLockCtrl = true`; EL10V2 inherits this. EL400 does NOT have `childLockCtrl = true` and SHALL NOT expose the fields.

#### Scenario: AC180 exposes child lock
- **WHEN** inspecting AC180 writable fields
- **THEN** `child_lock` and `child_lock_level` are present in WRITABLE_FIELD_NAMES

#### Scenario: EL400 does not expose child lock
- **WHEN** inspecting EL400 writable fields
- **THEN** `child_lock` is NOT present in WRITABLE_FIELD_NAMES
