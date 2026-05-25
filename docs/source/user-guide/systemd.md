# Systemd Services

Generate systemd unit files for long-running voltkeeper services.

## mqtt-publish-service

Generates a systemd unit file for the MQTT publish command.

```bash
voltkeeper mqtt-publish-service AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

### Options

All options from `mqtt-publish` are accepted, plus:

| Option | Description |
|---|---|
| `--user NAME` | System user to run as (default: current user) |
| `--exec PATH` | Path to voltkeeper executable (default: auto-detect) |
| `-o, --output PATH` | Write to file instead of stdout |

## mqtt-listen-service

Generates a systemd unit file for the MQTT listen shutdown watchdog.

```bash
voltkeeper mqtt-listen-service --serial 2409000123456 --broker 192.168.1.100
```

### Options

All options from `mqtt-listen` are accepted, plus:

| Option | Description |
|---|---|
| `--user NAME` | System user to run as (default: root, needed for shutdown) |
| `--exec PATH` | Path to voltkeeper executable (default: auto-detect) |
| `-o, --output PATH` | Write to file instead of stdout |

## Installing a generated service

```bash
sudo cp voltkeeper-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now voltkeeper-*.service
```
