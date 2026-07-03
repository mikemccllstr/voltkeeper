## ADDED Requirements

### Requirement: V2 INV-block array parsing lives in V2Base

`V2Base.parse()` SHALL parse the array-shaped payloads of the INV register blocks for every V2 device: the MCU software version array in INV_BASE_INFO, per-string PV data in INV_PV_INFO, and per-phase data in INV_GRID_INFO, INV_LOAD_INFO, and INV_INV_INFO. This matches APK v3.0.10 `ProtocolParserV2`, which parses these arrays unconditionally for all V2 devices. Device subclasses SHALL NOT need to override `parse()` to obtain this data.

#### Scenario: EL100V2 parses arrays without overriding parse
- **WHEN** an `El100V2` instance parses an INV_GRID_INFO payload reporting `sysPhaseNumber = 1`
- **THEN** the result contains `gridPhase[0].power`, `gridPhase[0].voltage`, and `gridPhase[0].current`
- **THEN** `El100V2` defines no `parse()` override

#### Scenario: AC2A behavior preserved through inheritance
- **WHEN** the existing AC2A register-block fixtures are parsed after the helpers move to `V2Base`
- **THEN** all parse results are identical to the pre-move behavior (existing AC2A test suite passes unchanged)

### Requirement: PV string array parsed from INV_PV_INFO

For each reported PV string (count = `acPvNumber + dcPvNumber`, clamped to 5), `V2Base` SHALL emit `pv[i].workingStatus`, `pv[i].type`, `pv[i].inputPower`, `pv[i].inputVoltage` (÷10), and `pv[i].inputCurrent` (÷10) from 16-byte entries starting at byte offset 20.

#### Scenario: Single PV string parsed
- **WHEN** an INV_PV_INFO payload reports `acPvNumber = 0` and `dcPvNumber = 1`
- **THEN** the result contains `pv[0].inputPower`, `pv[0].inputVoltage`, and `pv[0].inputCurrent`
- **THEN** no `pv[1].*` keys are emitted

#### Scenario: Short payload truncates safely
- **WHEN** the payload ends before a PV entry's 10 required bytes
- **THEN** iteration stops without error and without partial keys for that entry

### Requirement: Phase arrays parsed from grid, load, and inv blocks

For each reported phase (`sysPhaseNumber`, clamped to 3, defaulting to 3 when unreported), `V2Base` SHALL emit: `gridPhase[i].power/voltage/current` from 12-byte entries at byte offset 26 of INV_GRID_INFO (power and current as absolute values of signed words), `acPhase[i].power/voltage/current` from 12-byte entries at byte offset 60 of INV_LOAD_INFO, and `invPhase[i].workStatus/power/voltage/current` from 12-byte entries at byte offset 18 of INV_INV_INFO. Voltages and currents scale ÷10.

#### Scenario: Grid phase values parsed with sign handling
- **WHEN** an INV_GRID_INFO payload reports one phase with a negative signed power word
- **THEN** `gridPhase[0].power` is the absolute value

#### Scenario: Load phases parsed
- **WHEN** an INV_LOAD_INFO payload reports `sysPhaseNumber = 1`
- **THEN** the result contains `acPhase[0].power`, `acPhase[0].voltage`, and `acPhase[0].current`

#### Scenario: Inverter phases parsed
- **WHEN** an INV_INV_INFO payload reports `sysPhaseNumber = 1`
- **THEN** the result contains `invPhase[0].workStatus`, `invPhase[0].power`, `invPhase[0].voltage`, and `invPhase[0].current`

#### Scenario: Short payload truncates safely
- **WHEN** any phase block payload ends before an entry's required bytes
- **THEN** iteration stops without error
