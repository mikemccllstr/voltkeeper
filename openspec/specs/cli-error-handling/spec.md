## ADDED Requirements

### Requirement: CLI handles unrecognized device names gracefully

When a CLI command cannot resolve a BLE-advertised device name to a known device model, the system SHALL display a user-friendly error message explaining the likely cause (device connected to another app) and how to resolve it (disconnect and retry), instead of a bare Python traceback.

#### Scenario: Device advertises without model-name prefix
- **WHEN** a CLI command receives a scan result where the BLE name does not match any known device prefix (e.g. raw MAC address like `DC:B4:D9:46:73:96`)
- **THEN** the command exits with a clear error message indicating the device may be connected to the Bluetti app
- **THEN** the error message includes the received device name for debugging
- **THEN** the command exits with exit code 1
