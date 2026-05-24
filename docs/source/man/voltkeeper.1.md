# voltkeeper(1) -- CLI tool for Bluetti power stations

## SYNOPSIS

`voltkeeper` *COMMAND* [*OPTIONS*]

## DESCRIPTION

**voltkeeper** scans, connects to, and reads data from Bluetti power stations
over Bluetooth Low Energy. It supports plaintext Modbus (V1 protocol) and
AES-128-CBC encrypted devices (V2 protocol), with automatic handshake.

Commands are organized as subcommands under `voltkeeper`.

## COMMANDS

### scan

`voltkeeper scan` [**-t** *SECONDS*]

Scan for nearby Bluetti BLE devices. Displays the Bluetooth address, device
name, and the exact command to connect to each one.

| Option | Description |
|---|---|
| **-t**, **--timeout** *FLOAT* | Scan timeout in seconds (default: 10.0) |

### status

`voltkeeper status` [*ADDRESS*] [**-t** *SECONDS*] [**-v**]

Read battery status. If no address is given, scans for devices and prompts
for selection.

Output includes SOC (%), pack voltage, charging status, time estimates,
and load readings (DC, AC, total in watts).

| Option | Description |
|---|---|
| **-t**, **--timeout** *FLOAT* | Scan timeout in seconds (default: 10.0) |
| **-v**, **--verbose** | Display all available device information |

### write

`voltkeeper write` *ADDRESS* *FIELD* *VALUE*

Write a setting to the device.

| Field | Values |
|---|---|
| **ac_output**, **dc_output**, **power_off**, **dc_eco_mode**, **ac_eco_mode**, **power_lifting**, **alarm_sound** | **on**, **off** |
| **charging_mode** | **standard**, **turbo**, **silent** |
| **battery_range_start**, **battery_range_end**, **lcd_timeout**, **led_color**, **soc_low**, **soc_high**, **inv_voltage**, **inv_freq**, **working_mode** | (numeric) |

### mqtt-publish

`voltkeeper mqtt-publish` *ADDRESS* **--broker** *HOST* [*OPTIONS*]

Continuously polls the device over BLE and publishes state to an MQTT broker.
Supports Home Assistant MQTT auto-discovery.

| Option | Description |
|---|---|
| **--serial** *TEXT* | Device serial number (overrides BLE lookup for MQTT topic) |
| **--broker** *TEXT* | MQTT broker hostname (required) |
| **--port** *INTEGER* | MQTT broker port (default: 1883) |
| **--username** *TEXT* | MQTT broker username |
| **--password** *TEXT* | MQTT broker password |
| **--interval** *INTEGER* | Seconds between polling cycles (default: 0) |
| **--ha-config** *MODE* | HA discovery mode: **normal**, **none**, **advanced** (default: normal) |
| **--restart-on-source-change** | Exit cleanly when source code changes |

### mqtt-listen

`voltkeeper mqtt-listen` [*ADDRESS*] **--serial** *SERIAL* **--broker** *HOST* [*OPTIONS*]

Subscribes to the device's MQTT topic and watches battery SOC. When SOC drops
below the threshold, initiates a system shutdown after a grace period.
The shutdown is **latched** -- once triggered, it cannot be cancelled by SOC
recovery.

| Option | Description |
|---|---|
| **--serial** *TEXT* | Device serial number (or provide ADDRESS for BLE lookup) |
| **--broker** *TEXT* | MQTT broker hostname (required) |
| **--port** *INTEGER* | MQTT broker port (default: 1883) |
| **--username** *TEXT* | MQTT broker username |
| **--password** *TEXT* | MQTT broker password |
| **--shutdown-at** *INTEGER* | SOC % threshold for shutdown (default: 10) |
| **--grace-period** *INTEGER* | Seconds below threshold before shutdown (default: 60) |
| **--restart-on-source-change** | Exit cleanly when source code changes |

### mqtt-publish-service

`voltkeeper mqtt-publish-service` *ADDRESS* **--broker** *HOST* [*OPTIONS*]

Generate a systemd unit file for the MQTT publish command.

| Option | Description |
|---|---|
| **--user** *NAME* | System user to run as (default: current user) |
| **--exec** *PATH* | Path to voltkeeper executable (default: auto-detect) |
| **-o**, **--output** *PATH* | Write to file instead of stdout |

### mqtt-listen-service

`voltkeeper mqtt-listen-service` **--serial** *SERIAL* **--broker** *HOST* [*OPTIONS*]

Generate a systemd unit file for the MQTT listen shutdown watchdog.

| Option | Description |
|---|---|
| **--user** *NAME* | System user to run as (default: root) |
| **--exec** *PATH* | Path to voltkeeper executable (default: auto-detect) |
| **-o**, **--output** *PATH* | Write to file instead of stdout |

### probe

`voltkeeper probe` *ADDRESS* [**-o** *FILE*]

Connects to the device, sweeps all known register blocks, and emits a YAML
profile. Useful for device reverse-engineering and new-model support.

| Option | Description |
|---|---|
| **-o**, **--output** *PATH* | Output YAML file |

### annotate

`voltkeeper annotate` *ADDRESS* [**-o** *FILE*]

Live-polls the device and highlights byte-level changes in real time. Prompts
for field names at each changed offset, saving annotations incrementally to a
YAML draft. Press Ctrl-C to stop.

| Option | Description |
|---|---|
| **-o**, **--output** *PATH* | Output draft YAML file |

### validate-profile

`voltkeeper validate-profile` *FILE*

Parses the register blocks in a probe YAML and flags fields with suspect
values (stuck-at-zero, all-0xFFFF, out of range).

### load-test

`voltkeeper load-test` *ADDRESS* [*OPTIONS*]

Run a controlled battery discharge test. Coaches through setup, then logs
device stats every N seconds to a CSV file until the battery reaches 0%.

| Option | Description |
|---|---|
| **-o**, **--output** *PATH* | CSV output file (default: auto-named) |
| **-i**, **--interval** *SECONDS* | Sample interval, minimum 15s (default: 60) |
| **-l**, **--expected-load** *W* | Known load wattage for analysis reference |
| **-p**, **--phase** *TEXT* | Label for this test phase |

## SEE ALSO

**systemd**(1), **mosquitto**(8)
