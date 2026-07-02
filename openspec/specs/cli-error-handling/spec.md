## ADDED Requirements

### Requirement: CLI handles unrecognized device names gracefully

When a CLI command cannot resolve a BLE-advertised device name to a known device model, the system SHALL display a user-friendly error message explaining the likely cause (device connected to another app) and how to resolve it (disconnect and retry), instead of a bare Python traceback.

#### Scenario: Device advertises without model-name prefix
- **WHEN** a CLI command receives a scan result where the BLE name does not match any known device prefix (e.g. raw MAC address like `DC:B4:D9:46:73:96`)
- **THEN** the command exits with a clear error message indicating the device may be connected to the Bluetti app
- **THEN** the error message includes the received device name for debugging
- **THEN** the command exits with exit code 1

### Requirement: Config file errors produce friendly errors at process edges

Config loading failures (file not found, YAML parse error, validation error) SHALL be raised as a typed `ConfigError` by the config module rather than terminating the process from library code. Each process entry point (CLI commands that read config, `voltkeeperd` startup) SHALL catch this error, print a single-line message naming the config file and the problem — prefixed with that program's own name — and exit with code 1 and no traceback.

#### Scenario: CLI config command with an invalid config file
- **WHEN** a `voltkeeper config` subcommand reads a config file containing invalid YAML or a failing field validation
- **THEN** the command prints one line naming the file and the specific problem, without a `voltkeeperd:` prefix or Python traceback
- **THEN** the command exits with exit code 1

#### Scenario: Daemon startup with a missing config file
- **WHEN** `voltkeeperd` starts and no config file exists at any search path
- **THEN** it prints a `voltkeeperd:`-prefixed message listing the searched paths
- **THEN** it exits with exit code 1

#### Scenario: Library callers observe an exception, not process exit
- **WHEN** `load_config()` is called programmatically (e.g. by the reload API handler or a test) with an invalid config
- **THEN** a `ConfigError` carrying the message and file path is raised
- **THEN** the calling process is not terminated and nothing is written to stderr by the config module
