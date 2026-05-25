## ADDED Requirements

### Requirement: Shutdown watchdog configuration

The config file SHALL support an optional `shutdown_watchdog` section with `enabled`, `device`, `soc_threshold`, and `grace_period` fields.

#### Scenario: Watchdog enabled with valid config

- **WHEN** config contains `shutdown_watchdog: {enabled: true, device: "AA:BB:CC:DD:EE:FF", soc_threshold: 10, grace_period: 60}`
- **THEN** the daemon registers a shutdown watchdog listener for the specified device

#### Scenario: Watchdog disabled

- **WHEN** `shutdown_watchdog.enabled` is false or the section is absent
- **THEN** no shutdown watchdog listener is registered

### Requirement: SOC-based shutdown trigger

The shutdown watchdog SHALL monitor the SOC of the configured device via the state store. When SOC drops below the threshold, a latched countdown SHALL begin. On expiry, `sudo shutdown -h now` SHALL be executed.

#### Scenario: SOC drops below threshold and countdown expires

- **WHEN** SOC transitions from above threshold to below threshold
- **THEN** a latched countdown begins; after the grace period, the system executes `sudo shutdown -h now`

#### Scenario: SOC recovers during countdown

- **WHEN** a countdown is in progress and SOC rises above the threshold
- **THEN** the countdown continues unabated (latched); the system still shuts down when the countdown expires

#### Scenario: SOC stays above threshold

- **WHEN** SOC remains above the threshold across all poll cycles
- **THEN** no countdown is started and no shutdown occurs

### Requirement: Watchdog logging

The shutdown watchdog SHALL log a warning on countdown start and at regular intervals during the countdown, and SHALL log an informational message when the watchdog is active but no countdown is in progress.

#### Scenario: Countdown start logged

- **WHEN** SOC drops below threshold and countdown starts
- **THEN** a warning log message is emitted with the threshold, current SOC, and remaining seconds

#### Scenario: Shutdown command logged

- **WHEN** the countdown expires and shutdown is triggered
- **THEN** a warning log message is emitted before executing the shutdown command
