# MQTT

voltkeeper supports publishing device state to an MQTT broker and subscribing to
watch battery SOC for shutdown control.

## mqtt-publish

Continuously polls the device over BLE and publishes state to an MQTT broker.
Supports Home Assistant MQTT auto-discovery (on by default).

```bash
voltkeeper mqtt-publish AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

### Options

| Option                          | Description                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| `--serial TEXT`                 | Device serial number (overrides BLE lookup for MQTT topic)                           |
| `--broker TEXT`                 | MQTT broker hostname (required)                                                      |
| `--port INTEGER`                | MQTT broker port (default: 1883)                                                     |
| `--username TEXT`               | MQTT broker username                                                                 |
| `--password TEXT`               | MQTT broker password                                                                 |
| `--interval INTEGER`            | Seconds between polling cycles (default: 0 = as fast as possible)                    |
| `--ha-config MODE`              | Home Assistant discovery mode: `normal`, `none`, `advanced` (default: normal)        |
| `--restart-on-source-change`    | Exit cleanly when the voltkeeper package is updated, so systemd restarts the process |
| `--no-restart-on-source-change` | Keep running when source code changes (default)                                      |

## mqtt-listen

Subscribes to the device's MQTT topic and watches battery SOC. When SOC drops
below the threshold, initiates a system shutdown after a grace period.

The shutdown is **latched** — once triggered, it cannot be cancelled by SOC
recovery (use `systemctl stop` to abort before the grace period expires).

```bash
voltkeeper mqtt-listen AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

The BLE address argument can be omitted when `--serial` is provided — useful
when running on a machine without Bluetooth (e.g. a NAS or server receiving
MQTT from another host). When the address is omitted, pass `--device-type` as
well so the MQTT topic uses the correct model name:

```bash
voltkeeper mqtt-listen --serial 2409000123456 --device-type AC2A --broker 192.168.1.100
```

### Options

| Option                          | Description                                                  |
| ------------------------------- | ------------------------------------------------------------ |
| `--serial TEXT`                 | Device serial number (or provide ADDRESS for BLE lookup)     |
| `--device-type MODEL`           | Device model (e.g. `AC2A`); required when ADDRESS is omitted |
| `--broker TEXT`                 | MQTT broker hostname (required)                              |
| `--port INTEGER`                | MQTT broker port (default: 1883)                             |
| `--username TEXT`               | MQTT broker username                                         |
| `--password TEXT`               | MQTT broker password                                         |
| `--shutdown-at INTEGER`         | SOC % threshold for shutdown (default: 10)                   |
| `--grace-period INTEGER`        | Seconds below threshold before shutdown (default: 60)        |
| `--restart-on-source-change`    | Exit cleanly when source code changes                        |
| `--no-restart-on-source-change` | Keep running when source code changes (default)              |
