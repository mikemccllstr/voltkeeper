## ADDED Requirements

### Requirement: WORKING_MODE register writable on V2 devices

The system SHALL add `WORKING_MODE = 2005` constant to `v2_base.py` and support it as a writable `EnumField` via the `WorkingMode` enum defined in `commands.py`. The field SHALL be included in INV_BASE_SETTINGS parsing at data index 11.

#### Scenario: WORKING_MODE constant defined in v2_base
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `WORKING_MODE = 2005` is defined

#### Scenario: WORKING_MODE writable on AC2A
- **WHEN** user writes `working_mode = "Standard UPS"` to an AC2A
- **THEN** the system sends WriteSingleRegister to address 2005 with value 3

### Requirement: Child Lock registers available on V2 devices

The system SHALL add `CTRL_CHILD_LOCK = 2072` and `CHILD_LOCK_LEVEL = 2076` constants to `v2_base.py`. Devices whose APK `DeviceFunction.childLockCtrl = true` SHALL expose these as writable BoolField and IntField respectively.

#### Scenario: Child lock constants defined in v2_base
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `CTRL_CHILD_LOCK = 2072` and `CHILD_LOCK_LEVEL = 2076` are defined

#### Scenario: Child lock writable on AC180
- **WHEN** user writes `child_lock = on` to an AC180
- **THEN** the system sends WriteSingleRegister to address 2072 with value 0x20

### Requirement: Sleep configuration registers on V2 devices

The system SHALL add sleep configuration register constants to `v2_base.py`: `AUTO_SLEEP_DAYS = 2073`, `REMOTE_STARTUP_SOC = 2074`, `SLEEP_POWER_THRESHOLD = 2079`. These SHALL be exposed as writable fields on device classes whose APK feature flags enable remote power control or sleep mode (e.g., EL400).

#### Scenario: Sleep register constants defined
- **WHEN** inspecting `v2_base.py` constants
- **THEN** `AUTO_SLEEP_DAYS = 2073`, `REMOTE_STARTUP_SOC = 2074`, `SLEEP_POWER_THRESHOLD = 2079` are defined

#### Scenario: Sleep fields writable on EL400
- **WHEN** user writes `remote_startup_soc = 50` to an EL400
- **THEN** the system sends WriteSingleRegister to address 2074 with value 50

### Requirement: SYSTEM_POWER_OFF multi-value encoding documented

The protocol documentation SHALL document that SYSTEM_POWER_OFF (V2: 2013, V1: 3060) accepts values 1-4 with the following semantics: 1=shutdown, 2=power down (V1 protocol), 3=power down (V2 protocol with powerOffFuncV2), 4=sleep mode.

#### Scenario: SYSTEM_POWER_OFF value documentation
- **WHEN** reading `modbus-registers.md`
- **THEN** SYSTEM_POWER_OFF entry lists values 1-4 with descriptions
