## Requirements

### Requirement: Configured interval is the start-to-start poll period

The device polling loop SHALL begin poll cycles such that the time between the start of one cycle and the start of the next equals the configured interval, provided the cycle itself completes within the interval. The loop SHALL sleep for the interval exactly once per cycle.

#### Scenario: Poll period matches configured interval
- **WHEN** the interval is configured as N seconds and a poll cycle takes E seconds where E < N
- **THEN** the loop sleeps N − E seconds after the cycle, so the next cycle starts N seconds after the previous one started

#### Scenario: Slow cycle does not accumulate extra delay
- **WHEN** a poll cycle takes longer than the configured interval
- **THEN** the next cycle starts immediately without a negative or additional sleep

### Requirement: Continuous polling when interval is zero

When the configured interval is 0, the polling loop SHALL poll continuously without sleeping between cycles.

#### Scenario: Zero interval polls back-to-back
- **WHEN** the interval is configured as 0
- **THEN** the next poll cycle starts as soon as the previous one completes
