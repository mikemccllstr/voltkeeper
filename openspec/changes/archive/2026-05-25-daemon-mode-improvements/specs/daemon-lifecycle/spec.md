## ADDED Requirements

### Requirement: Install daemon as user systemd service
`voltkeeper daemon install` SHALL install voltkeeperd as a user-level systemd service at `~/.config/systemd/user/voltkeeper.service`. The command SHALL be idempotent: if the service unit file already exists, it SHALL print the current service status, config file path, API URL, and log command, then exit 0 without modifying anything. On first install, the command SHALL: generate a random API key if none is set in the config, write or create `~/.config/voltkeeper/config.yaml`, write the hardened unit file, run `systemctl --user daemon-reload`, `systemctl --user enable voltkeeper`, and `systemctl --user start voltkeeper`. The command SHALL print a human-readable summary of each action taken, including the full unit file contents, so experienced users understand exactly what was installed.

#### Scenario: First install, no existing config
- **WHEN** the user runs `voltkeeper daemon install` and no config or unit file exists
- **THEN** a config file is created at `~/.config/voltkeeper/config.yaml` with a generated API key, the hardened unit file is written to `~/.config/systemd/user/voltkeeper.service`, the service is enabled and started, and the command prints what was created and how to reach the daemon

#### Scenario: Already installed
- **WHEN** the user runs `voltkeeper daemon install` and the unit file already exists
- **THEN** the command prints the current service status, config path, URL, and log command, makes no changes, and exits 0

#### Scenario: Install with --lan flag
- **WHEN** the user runs `voltkeeper daemon install --lan`
- **THEN** the config is written with `server.host: "0.0.0.0"` and `server.mdns: true`, the generated API key is printed prominently with a security note, and the rest of the install proceeds as normal

### Requirement: Uninstall daemon service
`voltkeeper daemon uninstall` SHALL stop the running service, disable it, remove the unit file at `~/.config/systemd/user/voltkeeper.service`, and run `systemctl --user daemon-reload`. The command SHALL prompt for confirmation before acting. It SHALL NOT remove the config file or any user data.

#### Scenario: Uninstall running service
- **WHEN** the user runs `voltkeeper daemon uninstall` and confirms
- **THEN** the service is stopped, disabled, and the unit file is removed; the config file is preserved; a message is printed confirming what was removed

#### Scenario: Uninstall with no service installed
- **WHEN** the user runs `voltkeeper daemon uninstall` and no unit file exists
- **THEN** the command prints a message indicating no service is installed and exits 0

### Requirement: Stop running daemon
`voltkeeper daemon stop` SHALL stop the running daemon. If the unit file `~/.config/systemd/user/voltkeeper.service` exists, it SHALL stop the service via `systemctl --user stop voltkeeper`. Otherwise it SHALL call `POST /api/shutdown` on the daemon's URL. In both cases the command SHALL print what it is doing. After stopping, systemd will NOT automatically restart the service if it was stopped via `systemctl stop` (systemd does not restart manually-stopped services with `Restart=on-failure` unless the unit is re-triggered).

#### Scenario: Stop service-installed daemon
- **WHEN** the user runs `voltkeeper daemon stop` and the unit file exists
- **THEN** the command runs `systemctl --user stop voltkeeper`, prints confirmation, and exits 0

#### Scenario: Stop foreground daemon
- **WHEN** the user runs `voltkeeper daemon stop` and no unit file exists but the daemon is reachable
- **THEN** the command calls `POST /api/shutdown`, the daemon shuts down gracefully, and the command exits 0

#### Scenario: Daemon not reachable
- **WHEN** `voltkeeper daemon stop` is called and the daemon is not reachable and no unit file exists
- **THEN** the command prints an informative error and exits non-zero

### Requirement: Hardened systemd unit file
The generated unit file SHALL include the following security directives: `PrivateTmp=true`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=read-only`, `ReadWritePaths=%h/.config/voltkeeper`, `RestrictAddressFamilies=AF_INET AF_INET6 AF_BLUETOOTH AF_UNIX`, `SystemCallFilter=@system-service`, `SystemCallArchitectures=native`, `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW`, `CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW`, `MemoryMax=256M`, `TasksMax=64`, `Restart=on-failure`, `RestartSec=30`, `WantedBy=default.target`.

#### Scenario: Unit file contains hardening directives
- **WHEN** `voltkeeper daemon install` writes the unit file
- **THEN** the written file contains all required security directives listed in this requirement

### Requirement: Daemon shutdown API endpoint
The daemon SHALL expose `POST /api/shutdown` (protected by API key) that triggers a graceful shutdown of the daemon process. This is used by `voltkeeper daemon stop` when no systemd unit file is present.

#### Scenario: Authorized shutdown request
- **WHEN** a POST request is made to `/api/shutdown` with a valid API key
- **THEN** the daemon begins graceful shutdown (stops device polling, closes connections) and the HTTP response is 202 Accepted before the process exits

#### Scenario: Unauthorized shutdown request
- **WHEN** a POST request is made to `/api/shutdown` with no or invalid API key
- **THEN** the daemon returns 401 Unauthorized and does not shut down
