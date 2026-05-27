# Systemd Services

Generate systemd unit files for long-running voltkeeper services.

## voltkeeperd daemon

For installing `voltkeeperd` as a systemd user service, use:

```bash
voltkeeper daemon install
```

See the [Daemon](daemon.md) page for the full install workflow, options, and
idempotency behaviour.

### System-level install (advanced)

The default install is a **user service** (`~/.config/systemd/user/`), which
requires no root and runs as your login user. This is the right choice for
personal workstations and always-logged-in users.

For headless servers where the daemon must start before any user logs in,
install as a system service instead:

1. Write a custom unit file at `/etc/systemd/system/voltkeeperd.service`.
   See the generated `~/.config/systemd/user/voltkeeper.service` for the
   recommended hardening directives.
1. Set `User=` to a dedicated service account.
1. Run `sudo systemctl daemon-reload && sudo systemctl enable --now voltkeeperd`.

Consider enabling systemd user lingering as a lighter alternative:

```bash
loginctl enable-linger $USER   # user services survive logout
```

## mqtt-publish-service

Generates a systemd unit file for the MQTT publish command.

```bash
voltkeeper mqtt-publish-service AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

### Options

All options from `mqtt-publish` are accepted, plus:

| Option              | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `--user NAME`       | System user to run as (default: current user)        |
| `--exec PATH`       | Path to voltkeeper executable (default: auto-detect) |
| `-o, --output PATH` | Write to file instead of stdout                      |

## mqtt-listen-service

Generates a systemd unit file for the MQTT listen shutdown watchdog.

```bash
voltkeeper mqtt-listen-service --serial 2409000123456 --broker 192.168.1.100
```

### Options

All options from `mqtt-listen` are accepted, plus:

| Option              | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `--user NAME`       | System user to run as (default: root, needed for shutdown) |
| `--exec PATH`       | Path to voltkeeper executable (default: auto-detect)       |
| `-o, --output PATH` | Write to file instead of stdout                            |

## Installing a generated service

```bash
sudo cp voltkeeper-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now voltkeeper-*.service
```
