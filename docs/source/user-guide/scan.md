# scan

Scan for nearby Bluetti devices.

```bash
voltkeeper scan
```

Displays all nearby Bluetti devices and prints the `voltkeeper status` command
to connect to each one.

## Options

| Option                | Description                             |
| --------------------- | --------------------------------------- |
| `-t, --timeout FLOAT` | Scan timeout in seconds (default: 10.0) |

## Example

```
$ voltkeeper scan

2 device(s) found:

  00:11:22:33:44:55  AC2A2305000
  66:77:88:99:AA:BB  AC3001502000

To read data from a specific device:
  voltkeeper status 00:11:22:33:44:55
  voltkeeper status 66:77:88:99:AA:BB
```
