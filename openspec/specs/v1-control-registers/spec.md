## ADDED Requirements

### Requirement: V1 settable register constants defined in v1_base.py

The system SHALL define module-level constants in `v1_base.py` for all V1 protocol writable/readable registers documented in the APK 3.0.9 V1 register map (section 15.5 of modbus-registers.md) that are within the V1 writable range (3000–3100) or are commonly-used read registers.

#### Scenario: All documented writable range constants are present
- **WHEN** inspecting `v1_base.py` module-level constants
- **THEN** the following constants are defined with their documented addresses:
  - `MACHINE_MODE = 3004`
  - `MACHINE_ADDRESS = 3005`
  - `MAX_PV_CHARGE_CURRENT = 3014`
  - `LOW_POWER_SETTINGS = 3015`
  - `HIGH_POWER_SETTINGS = 3016`
  - `MAX_DISCHARGING_CURRENT = 3018`
  - `MAX_CHARGING_CURRENT_OF_GRID = 3019`
  - `SYSTEM_TIME = 3031`
  - `WORKING_TIME = 3039`
  - `MAX_CHARGING_POWER = 3057`
  - `MAX_DISCHARGE_POWER = 3058`
  - `ECO_AUTO_OFF = 3064`

### Requirement: V1 device classes expose new writable controls

V1 device classes (EB3A, AC200L, AC200PL, AC200M, AC300, AC500) SHALL expose the newly-defined register constants as writable fields in their control struct definitions, where the APK's `DeviceFunction` flags indicate the feature is supported.

#### Scenario: AC200L exposes SYSTEM_TIME control
- **WHEN** building the control struct for AC200L
- **THEN** `SYSTEM_TIME` (address 3031) is included as a writable `Uint32Field`

#### Scenario: AC200L exposes MAX_CHARGING_POWER control
- **WHEN** building the control struct for AC200L
- **THEN** `MAX_CHARGING_POWER` (address 3057) is included as a writable `UintField`

#### Scenario: AC200M does NOT expose unsupported controls
- **WHEN** building the control struct for AC200M
- **THEN** only registers supported by AC200M's `DeviceFunction.flags` in the APK are exposed
- **THEN** unsupported register fields are not included

### Requirement: probe.py V1_BLOCKS includes missing read blocks

The system SHALL add `FAULT_HISTORY_START` (address 2000) to `V1_BLOCKS` in `probe.py` if it is within a reasonable probe sweep range, to enable fault history discovery during device probing.

#### Scenario: Fault history block is probed on V1 devices
- **WHEN** probing a V1 device
- **THEN** register 2000 is included in the probe sweep
- **THEN** the resulting profile YAML includes any fault history data present
