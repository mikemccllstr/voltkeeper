## ADDED Requirements

### Requirement: EL100V2 pack voltage uses centivolt scaling

`El100V2` SHALL override `DEFAULT_PACK_VOLTAGE_SCALE = 2` so `packTotalVoltage` is parsed as raw ÷ 100, matching AC2A/EL10V2/EL30V2. Evidence: the 2026-07-03 captures hold raw 5350 (0x14E6) at 100% SoC and 5333 at 99% — 53.50 V / 53.33 V for a 56 V-class LiFePO4 pack, while the inherited ÷10 default reported a physically impossible 530.5 V.

#### Scenario: captured AC-run pack voltage parses to physical volts
- **WHEN** the grid-connected HOME fixture bytes are parsed
- **THEN** `packTotalVoltage` is 53.50

#### Scenario: captured DC-run pack voltage parses to physical volts
- **WHEN** the on-battery HOME fixture bytes are parsed
- **THEN** `packTotalVoltage` is 53.33
