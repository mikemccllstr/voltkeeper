# Contributing a new Bluetti device

This guide walks you through capturing the data needed to add support for a
new Bluetti device model to `bluetti-cli`.

## What you need

- The device, charged and powered on
- An Android phone with the official Bluetti app installed
- `adb` access (USB debugging enabled on the phone)
- A Linux/macOS/Windows machine with Python 3.13+ and `uv`
- A Bluetooth adapter

## Step 1: Identify the device

Run a scan to confirm `bluetti-cli` can see the device:

```bash
bluetti-cli scan
```

Note the MAC address and Bluetooth name (e.g. `AC2A2305000`).

## Step 2: Probe the register layout

Use `bluetti-cli probe` to capture every readable Modbus register block:

```bash
bluetti-cli probe <ADDRESS> -o my-device.yaml
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

If your device uses BLE encryption, you'll need the session key.  Start
`bluetti-cli` with `BLUETTI_DEBUG=1` to see key material, or extract it
from the Android app's logcat.  Pass it with `--key` and `--iv`:

```bash
python scripts/parse_btsnoop.py btsnoop_hci.log --key a1b2... --iv c3d4... > capture.csv
```

## Step 4: Submit

Open a GitHub issue on
[bluetti-apk-reverse](https://github.com/mikemccllstr/bluetti-apk-reverse)
with both files attached:

- `my-device.yaml` (the probe output)
- `capture.csv` (the parsed btsnoop timeline)

In your issue, include the device model name and any notes about what
features you tested (e.g. "toggled AC output, observed grid+mode, max
battery SOC was 95%").

A maintainer will use these files to build a device class and get it
merged — no coding required on your part.

## Encryption notes

- Most V1 devices (`protocolVer < 2000`) use plaintext BLE — no key needed.
- V2 devices (e.g. AC2A) may use AES-CBC encryption.  If your probe YAML
  shows `protocol: v2`, try the parse with and without `--key`.

## macOS notes

macOS uses a different Bluetooth stack.  If you encounter device discovery
issues, try using a Linux VM or a Raspberry Pi for the BLE capture step.
The btsnoop parsing step doesn't require Bluetooth — it can run on any
platform.
