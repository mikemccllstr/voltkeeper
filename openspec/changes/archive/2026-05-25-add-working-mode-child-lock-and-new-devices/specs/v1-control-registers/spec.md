## ADDED Requirements

### Requirement: WORKING_MODE register documented for V1 protocol

The system SHALL add `WORKING_MODE = 3001` constant to `v1_base.py` and document it in `modbus-registers.md` with the 6-value `WorkingMode` enum mapping: 1=Customized UPS, 2=PV Priority UPS, 3=Standard UPS, 4=Time Control UPS, 5=V2 Time Control UPS, 11=Self-Consumption Export.

#### Scenario: WORKING_MODE constant defined in v1_base
- **WHEN** inspecting `v1_base.py` constants
- **THEN** `WORKING_MODE = 3001` is defined

#### Scenario: WORKING_MODE documented in protocol docs
- **WHEN** reading `modbus-registers.md` V1 register section
- **THEN** register 3001 is listed as WORKING_MODE with the full value mapping
