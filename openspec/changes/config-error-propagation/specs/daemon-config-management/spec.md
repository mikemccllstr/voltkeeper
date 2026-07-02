## MODIFIED Requirements

### Requirement: Config reload API endpoint
The daemon SHALL expose `POST /api/reload` (protected by API key) that re-reads the config file and applies any hot-reloadable changes. Hot-reloadable changes are: device list, scan interval, scan timeout. Restart-required changes are: server host, port. The response SHALL indicate which changes were applied and whether a restart is needed.

#### Scenario: Reload with hot-reloadable changes
- **WHEN** `POST /api/reload` is called after a change to `scan.interval`
- **THEN** the daemon applies the new value immediately and responds with `{"reloaded": true, "restart_required": false}`

#### Scenario: Reload with restart-required changes
- **WHEN** `POST /api/reload` is called after a change to `server.port`
- **THEN** the daemon responds with `{"reloaded": false, "restart_required": true, "reason": "server.port changed"}` and does not apply the new port

#### Scenario: Config file not found or invalid on reload
- **WHEN** `POST /api/reload` is called but the config file has a parse error or fails validation
- **THEN** the daemon responds with 400 Bad Request and continues running with its current config
- **THEN** the response error message includes the specific failure — the config file path and the field or parse problem — not a generic "could not be loaded"
