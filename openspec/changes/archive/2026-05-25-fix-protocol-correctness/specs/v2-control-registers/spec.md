## MODIFIED Requirements

### Requirement: EL400 system-power register modeled as a single enum

The EL400 device class SHALL model V2 register 2013 (`SYSTEM_POWER_OFF`) as a single `EnumField` named `system_power` using the `SystemPowerOff` enum (`NORMAL=0, SHUTDOWN=1, POWER_DOWN_V1=2, POWER_DOWN_V2=3, SLEEP=4`). It SHALL NOT expose two BoolFields on the same address. Writes SHALL accept the enum member name (`"sleep"`, `"shutdown"`, etc.) or the integer value, and SHALL emit the corresponding integer to register 2013 via `WriteSingleRegister`.

#### Scenario: Read register 2013 with sleep value
- **WHEN** EL400 parses register 2013 with raw value `4`
- **THEN** the parsed result contains `system_power = SystemPowerOff.SLEEP`
- **THEN** the result does NOT contain `power_off` or `sleep_mode` keys

#### Scenario: Write sleep mode
- **WHEN** user runs `voltkeeper write <addr> system_power sleep` on an EL400
- **THEN** the system sends `WriteSingleRegister(address=2013, value=4)`

#### Scenario: Write shutdown
- **WHEN** user runs `voltkeeper write <addr> system_power shutdown` on an EL400
- **THEN** the system sends `WriteSingleRegister(address=2013, value=1)`

#### Scenario: Invalid value rejected
- **WHEN** user writes `system_power = "wakeup"` (not an enum member)
- **THEN** `build_setter_command` raises `KeyError` or `ValueError` before sending any BLE traffic

### Requirement: SystemPowerOff enum lives in shared commands module

The `SystemPowerOff(Enum)` SHALL be defined in `src/voltkeeper/core/commands.py` alongside `WorkingMode` and `ChargingMode`, with members and integer values matching the V2 `SYSTEM_POWER_OFF` register semantics documented in `docs/source/protocol/modbus-registers.md`.

#### Scenario: Enum importable from commands module
- **WHEN** importing `SystemPowerOff` from `voltkeeper.core.commands`
- **THEN** the import succeeds with all five members accessible
- **THEN** `SystemPowerOff.SLEEP.value == 4`
