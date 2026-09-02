# voltkeeper(1) -- CLI tool for Bluetti power stations

## SYNOPSIS

`voltkeeper` *COMMAND* \[*OPTIONS*\]

## DESCRIPTION

**voltkeeper** scans, connects to, and reads data from Bluetti power stations
over Bluetooth Low Energy. It supports plaintext Modbus (V1 protocol) and
AES-128-CBC encrypted devices (V2 protocol), with automatic handshake.

Commands are organized as subcommands under `voltkeeper`.

## COMMANDS

### scan

`voltkeeper scan` \[**-t** *SECONDS*\]

Scan for nearby Bluetti BLE devices. Displays the Bluetooth address, device
name, and the exact command to connect to each one.

| Option                        | Description                             |
| ----------------------------- | --------------------------------------- |
| **-t**, **--timeout** *FLOAT* | Scan timeout in seconds (default: 10.0) |

### status

`voltkeeper status` \[*ADDRESS*\] \[**-t** *SECONDS*\] \[**-v**\] \[**--daemon** *URL*\]

Read battery status. If no address is given, scans for devices and prompts
for selection.

Output includes SOC (%), pack voltage, charging status, time estimates,
and load readings (DC, AC, total in watts).

| Option                        | Description                                                    |
| ----------------------------- | -------------------------------------------------------------- |
| **-t**, **--timeout** *FLOAT* | Scan timeout in seconds (default: 10.0)                        |
| **-v**, **--verbose**         | Display all available device information                       |
| **--daemon** *URL*            | Query the voltkeeperd daemon instead of BLE (e.g. `localhost`) |

### write

`voltkeeper write` *ADDRESS* *FIELD* *VALUE* \[**--daemon** *URL*\]

`voltkeeper write` *ADDRESS* **--help-field** *FIELD*

Write a setting to the device.

`--help-field` prints the type, valid values, and range for a writable field
and performs no write. *FIELD* and *VALUE* are omitted in that mode, but
*ADDRESS* is still required: it is used for a BLE scan lookup to identify the
device model.

| Option                   | Description                                         |
| ------------------------ | --------------------------------------------------- |
| **--help-field** *FIELD* | Show type and valid values for a writable field     |
| **--daemon** *URL*       | Send the command through voltkeeperd instead of BLE |

| Field                                                                                                                                                             | Values                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| **ac_output**, **dc_output**, **power_off**, **dc_eco_mode**, **ac_eco_mode**, **power_lifting**, **alarm_sound**                                                 | **on**, **off**                     |
| **charging_mode**                                                                                                                                                 | **standard**, **turbo**, **silent** |
| **sys_low_power**, **sys_high_power**, **lcd_timeout**, **led_color**, **soc_holding_low**, **soc_holding_high**, **inv_voltage**, **inv_freq**, **working_mode** | (numeric)                           |

### mqtt-publish

`voltkeeper mqtt-publish` *ADDRESS* **--broker** *HOST* \[*OPTIONS*\]

Continuously polls the device over BLE and publishes state to an MQTT broker.
Supports Home Assistant MQTT auto-discovery.

| Option                            | Description                                                             |
| --------------------------------- | ----------------------------------------------------------------------- |
| **--serial** *TEXT*               | Device serial number (overrides BLE lookup for MQTT topic)              |
| **--broker** *TEXT*               | MQTT broker hostname (required)                                         |
| **--port** *INTEGER*              | MQTT broker port (default: 1883)                                        |
| **--username** *TEXT*             | MQTT broker username                                                    |
| **--password** *TEXT*             | MQTT broker password                                                    |
| **--interval** *INTEGER*          | Seconds between polling cycles (default: 0)                             |
| **--ha-config** *MODE*            | HA discovery mode: **normal**, **none**, **advanced** (default: normal) |
| **--restart-on-source-change**    | Exit cleanly when source code changes                                   |
| **--no-restart-on-source-change** | Keep running when source code changes (default)                         |

### mqtt-listen

`voltkeeper mqtt-listen` \[*ADDRESS*\] **--broker** *HOST* \[*OPTIONS*\]

Subscribes to the device's MQTT topic and watches battery SOC. When SOC drops
below the threshold, initiates a system shutdown after a grace period.
The shutdown is **latched** -- once triggered, it cannot be cancelled by SOC
recovery.

Provide either *ADDRESS* (BLE lookup) or **--serial** with **--device-type**
(when running on a machine without Bluetooth).

| Option                            | Description                                                                   |
| --------------------------------- | ----------------------------------------------------------------------------- |
| **--serial** *TEXT*               | Device serial number (or provide ADDRESS for BLE lookup)                      |
| **--device-type** *MODEL*         | Device model (e.g. **AC2A**); required with --serial when no ADDRESS is given |
| **--broker** *TEXT*               | MQTT broker hostname (required)                                               |
| **--port** *INTEGER*              | MQTT broker port (default: 1883)                                              |
| **--username** *TEXT*             | MQTT broker username                                                          |
| **--password** *TEXT*             | MQTT broker password                                                          |
| **--shutdown-at** *INTEGER*       | SOC % threshold for shutdown (default: 10)                                    |
| **--grace-period** *INTEGER*      | Seconds below threshold before shutdown (default: 60)                         |
| **--restart-on-source-change**    | Exit cleanly when source code changes                                         |
| **--no-restart-on-source-change** | Keep running when source code changes (default)                               |

### mqtt-publish-service

`voltkeeper mqtt-publish-service` *ADDRESS* **--broker** *HOST* \[*OPTIONS*\]

Generate a systemd unit file for the MQTT publish command.

| Option                      | Description                                          |
| --------------------------- | ---------------------------------------------------- |
| **--user** *NAME*           | System user to run as (default: current user)        |
| **--exec** *PATH*           | Path to voltkeeper executable (default: auto-detect) |
| **-o**, **--output** *PATH* | Write to file instead of stdout                      |

### mqtt-listen-service

`voltkeeper mqtt-listen-service` **--serial** *SERIAL* **--broker** *HOST* \[*OPTIONS*\]

Generate a systemd unit file for the MQTT listen shutdown watchdog.

| Option                      | Description                                          |
| --------------------------- | ---------------------------------------------------- |
| **--user** *NAME*           | System user to run as (default: root)                |
| **--exec** *PATH*           | Path to voltkeeper executable (default: auto-detect) |
| **-o**, **--output** *PATH* | Write to file instead of stdout                      |

### verify

`voltkeeper verify` *ADDRESS* \[**-o** *FILE*\] \[**--tier** *N*\] \[*OPTIONS*\]

Run a six-tier integration test against a Bluetti device. Tiers 1-3 run
automatically (read, identity writes, probe writes); tiers 4-6 prompt before
running (load toggles, mode changes, irreversible operations). Writes a YAML
report that is safe to share in a GitHub issue.

| Option                      | Description                                                             |
| --------------------------- | ----------------------------------------------------------------------- |
| **-o**, **--output** *PATH* | Output YAML file (default: `hardware-data/verify_MODEL_TIMESTAMP.yaml`) |
| **--tier** *INTEGER*        | Run through this tier only (1-6)                                        |
| **--yes**                   | Pre-consent to all supervised tiers                                     |
| **--no-scrub**              | Keep real SN and BLE address in report                                  |
| **--ground-truth**          | Attended mode: compare device-screen values against parsed registers    |
| **--skip-category** *NAME*  | Skip a ground-truth category (repeatable)                               |

### config

`voltkeeper config` *SUBCOMMAND* \[*OPTIONS*\]

Read and write the voltkeeper daemon configuration without hand-editing YAML.

`voltkeeper config show`

Display the current daemon configuration and device list.

`voltkeeper config set` *KEY* *VALUE* \[**--daemon-url** *URL*\]

Set a configuration value. Settable keys: **server.host**, **server.port**,
**server.api_key**, **server.mdns**, **scan.interval**, **scan.timeout**.
Changes are applied via hot-reload where supported; host, port, and api_key
changes require a daemon restart.

`voltkeeper config add-device` *ADDRESS* \[**--name** *NAME*\]

Add a device to the daemon configuration.

`voltkeeper config remove-device` *ADDRESS*

Remove a device from the daemon configuration.

### daemon

`voltkeeper daemon` *SUBCOMMAND* \[*OPTIONS*\]

Manage the voltkeeperd daemon process (the long-running service that serves
the REST API and Web UI). The daemon itself runs as `voltkeeperd`.

`voltkeeper daemon start`

Run voltkeeperd in the foreground. For production use, install it as a
systemd service instead.

`voltkeeper daemon status` \[**--daemon-url** *URL*\]

Show the status of the running daemon and its connected devices.

`voltkeeper daemon stop` \[**--daemon-url** *URL*\]

Stop the running daemon: via systemctl when a user service is installed,
otherwise via a shutdown request to the daemon API.

`voltkeeper daemon install` \[**--lan**\]

Install voltkeeperd as a user-level systemd service. Generates a config file
with a fresh API key, writes a hardened unit file, and enables and starts the
service. Safe to run again.

| Option    | Description                                   |
| --------- | --------------------------------------------- |
| **--lan** | Bind on all interfaces and advertise via mDNS |

`voltkeeper daemon uninstall`

Stop, disable, and remove the systemd user service. Config files and data are
not removed.

### probe

`voltkeeper probe` *ADDRESS* \[**-o** *FILE*\]

Connects to the device, sweeps all known register blocks, and emits a YAML
profile. Useful for device reverse-engineering and new-model support.

| Option                      | Description      |
| --------------------------- | ---------------- |
| **-o**, **--output** *PATH* | Output YAML file |

### annotate

`voltkeeper annotate` *ADDRESS* \[**-o** *FILE*\]

Live-polls the device and highlights byte-level changes in real time. Prompts
for field names at each changed offset, saving annotations incrementally to a
YAML draft. Press Ctrl-C to stop.

| Option                      | Description            |
| --------------------------- | ---------------------- |
| **-o**, **--output** *PATH* | Output draft YAML file |

### validate-profile

`voltkeeper validate-profile` *FILE*

Parses the register blocks in a probe YAML and flags fields with suspect
values (stuck-at-zero, all-0xFFFF, out of range).

### load-test

`voltkeeper load-test` *ADDRESS* \[*OPTIONS*\]

Run a controlled battery discharge test. Coaches through setup, then logs
device stats every N seconds to a CSV file until the battery reaches 0%.

| Option                           | Description                                |
| -------------------------------- | ------------------------------------------ |
| **-o**, **--output** *PATH*      | CSV output file (default: auto-named)      |
| **-i**, **--interval** *SECONDS* | Sample interval, minimum 15s (default: 60) |
| **-l**, **--expected-load** *W*  | Known load wattage for analysis reference  |
| **-p**, **--phase** *TEXT*       | Label for this test phase                  |

## SEE ALSO

**systemd**(1), **mosquitto**(8)
