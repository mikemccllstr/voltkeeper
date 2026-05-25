# Contributing a new Bluetti device

This guide walks you through capturing the data needed to add support for a
new Bluetti device model to voltkeeper.

## What you need

- The device, charged and powered on
- An Android phone with the official Bluetti app installed
- `adb` access (USB debugging enabled on the phone)
- A Linux/macOS/Windows machine with Python 3.13+ and `uv`
- A Bluetooth adapter

## Step 1: Identify the device

Run a scan to confirm voltkeeper can see the device:

```bash
voltkeeper scan
```

Note the MAC address and Bluetooth name (e.g. `AC2A2305000`).

## Step 2: Probe the register layout

Use `voltkeeper probe` to capture every readable Modbus register block:

```bash
voltkeeper probe <ADDRESS> -o my-device.yaml
```

This writes `my-device.yaml` with the device's protocol version and raw
register data. Save this file — you'll submit it later.

## Step 3: Capture official-app traffic

We need to see what the Android app sends and receives so we can map
register values to field names.

1. On your Android phone, enable Developer options, then enable
   **"Enable Bluetooth HCI snoop log"**.
2. Open the Bluetti app and exercise the features you want to map
   (toggle AC output, change charging mode, view battery details, etc.).
3. Once you've exercised everything, disable Bluetooth HCI snoop log
   (toggling it off writes the log buffer to disk).
4. Pull the log with `adb bugreport` or extract directly:
   ```bash
   adb pull /sdcard/btsnoop_hci.log
   ```
5. Parse the log into a CSV timeline:
   ```bash
   python scripts/parse_btsnoop.py btsnoop_hci.log > capture.csv
   ```

If your device uses BLE encryption (`protocolVer >= 2000`), extracting
the per-session AES key is not yet automated. For encrypted devices:
submit the **raw `btsnoop_hci.log`** alongside your `my-device.yaml`
instead of a parsed CSV. A maintainer will derive the session key and
decrypt it.

Once you have a key (16 bytes / 32 hex chars) and initial IV:

```bash
python scripts/parse_btsnoop.py btsnoop_hci.log --key a1b2... --iv c3d4... > capture.csv
```

## Step 4: Submit

Open a GitHub issue on
[voltkeeper](https://github.com/mikemccllstr/voltkeeper)
and attach:

- `my-device.yaml` (the probe output) — always required
- `capture.csv` (the parsed btsnoop timeline) — for plaintext (V1) devices
- `btsnoop_hci.log` (the raw log) — for encrypted (V2) devices instead of the CSV

In your issue, include the device model name and any notes about what
features you tested (e.g. "toggled AC output, observed grid+mode, max
battery SOC was 95%").

A maintainer will use these files to build a device class and get it
merged — no coding required on your part.

## Encryption notes

- Most V1 devices (`protocolVer < 2000`) use plaintext BLE — no key needed.
- V2 devices may use AES-CBC encryption. If your probe YAML shows
  `protocol: v2`, try the parse with and without `--key`.

## macOS notes

macOS uses a different Bluetooth stack. If you encounter device discovery
issues, try using a Linux VM or a Raspberry Pi for the BLE capture step.
The btsnoop parsing step doesn't require Bluetooth — it can run on any
platform.
