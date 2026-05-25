## ADDED Requirements

### Requirement: WORKING_MODE register available as writable enum

The system SHALL expose the WORKING_MODE register (V1 address 3001, V2 address 2005) as a writable `EnumField` on device classes that support it. The field SHALL accept values from the `WorkingMode` enum with the following mapping:

- `CUSTOMIZED_UPS = 1` — Customized (advanced) UPS mode
- `PV_PRIORITY_UPS = 2` — PV priority (self-consumption) mode
- `STANDARD_UPS = 3` — Standard UPS (backup) mode
- `TIME_CTRL_UPS = 4` — Time-controlled UPS (V1 protocol)
- `V2_TIME_CTRL_UPS = 5` — Time-controlled UPS (V2 protocol)
- `SELF_CONSUMPTION_EXPORT = 11` — Self-consumption with grid export

Existing UPS_MODE (3035) SHALL remain as the Online/Standby sub-toggle (boolean).

#### Scenario: Write WORKING_MODE on V2 device
- **WHEN** user writes `working_mode = "PV Priority"` to a V2 device
- **THEN** the system sends WriteSingleRegister to address 2005 with value 2

#### Scenario: Read WORKING_MODE from V2 device
- **WHEN** polling INV_BASE_SETTINGS (address 2000) on a V2 device
- **THEN** the working_mode field at data index 11 is parsed as an integer
- **THEN** the parsed value maps to the correct WorkingMode enum name in output

#### Scenario: Write WORKING_MODE on V1 device
- **WHEN** user writes `working_mode = "Standard UPS"` to a V1 device
- **THEN** the system sends WriteSingleRegister to address 3001 with value 3

#### Scenario: WorkingMode enum serialized for CLI output
- **WHEN** displaying device status in CLI mode
- **THEN** working_mode shows the human-readable enum name (e.g., "PV Priority")
- **THEN** the integer value is also available via machine-readable output

#### Scenario: UPS_MODE (3035) unchanged
- **WHEN** user writes `ups_mode = on` to a device
- **THEN** the system sends WriteSingleRegister to address 3035 with value 1 (Online)
- **THEN** this is separate from WORKING_MODE and does not affect the strategy selection

### Requirement: WorkingMode enum defined in shared location

The `WorkingMode` enum SHALL be defined in `src/voltkeeper/core/commands.py` (alongside `ChargingMode`) so both V1 and V2 base classes can reference it without circular imports.

#### Scenario: WorkingMode importable from commands module
- **WHEN** importing `WorkingMode` from `voltkeeper.core.commands`
- **THEN** the import succeeds with all 6 enum values accessible
