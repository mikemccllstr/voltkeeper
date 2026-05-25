## ADDED Requirements

### Requirement: Time-sliced polling cadence

The system SHALL divide V2 polling register blocks into fast and slow categories. Fast blocks SHALL be polled every cycle. Slow blocks SHALL be polled every 3rd cycle, based on a counter that increments each poll cycle.

#### Scenario: Fast blocks polled every cycle
- **WHEN** a V2 device poll cycle executes
- **THEN** HOME (100) and CONTROLS (2000-2272) register blocks are included in the poll
- **THEN** any dynamically discovered pack or sub-device registers are included

#### Scenario: Slow blocks polled on 3rd cycle
- **WHEN** the poll counter modulo 3 equals 0
- **THEN** INV_BASE_INFO (1100), INV_PV_INFO (1200), INV_GRID_INFO (1300), INV_LOAD_INFO (1400), and INV_INV_INFO (1500) are included in the poll

#### Scenario: Slow blocks skipped on 1st and 2nd cycle
- **WHEN** the poll counter modulo 3 is 1 or 2
- **THEN** slab register blocks are NOT polled

### Requirement: Poll counter lifecycle

The system SHALL maintain a poll cycle counter that increments on each poll and resets to 0 when it reaches a maximum value.

#### Scenario: Counter increments per cycle
- **WHEN** a poll cycle completes
- **THEN** the poll counter is incremented by 1

#### Scenario: Counter wraps at 9999
- **WHEN** the poll counter reaches 9999
- **THEN** it resets to 0 on the next cycle

### Requirement: Forced full poll after write

After a write operation to any register, the system SHALL force the next poll cycle to include all register blocks regardless of the counter value.

#### Scenario: Write triggers full poll
- **WHEN** a write command is issued to a V2 device
- **THEN** the next poll cycle includes both fast and slow register blocks
- **THEN** the counter is reset to a value that triggers a full poll (modulo 3 == 0)

### Requirement: V1 devices unaffected

Time-slicing SHALL NOT apply to V1 protocol devices. V1 devices SHALL continue to poll all register blocks every cycle.

#### Scenario: V1 device polls all blocks every cycle
- **WHEN** a V1 device poll cycle executes
- **THEN** all V1 poll commands are included regardless of counter value
