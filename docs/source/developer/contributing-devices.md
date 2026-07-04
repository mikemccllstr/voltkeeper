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
1. Open the Bluetti app and exercise the features you want to map
   (toggle AC output, change charging mode, view battery details, etc.).
1. Once you've exercised everything, disable Bluetooth HCI snoop log
   (toggling it off writes the log buffer to disk).
1. Pull the log with `adb bugreport` or extract directly:
   ```bash
   adb pull /sdcard/btsnoop_hci.log
   ```
1. Parse the log into a CSV timeline:
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

### Locating encryption keys in a new APK

When a new encrypted model is released, you need the three key constants
to add to `src/voltkeeper/bluetooth/handshake.py`. They are public
`static final String` fields in the decompiled APK.

**jadx grep recipe.** Decompile the APK with jadx and search the
`sources` directory:

```bash
rg '459FC535808941F17091E0993EE3E93D'   # LOCAL_AES_KEY hex
rg 'PRIVATE_KEY_L1'                      # field name
rg 'PUBLIC_KEY_K2'                       # field name
```

**Source locations (APK v3.0.9):**

| Field            | Class / file              | maps to handshake.py constant |
| ---------------- | ------------------------- | ----------------------------- |
| `LOCAL_AES_KEY`  | `ConnConstantsV2.java:98` | `LOCAL_AES_KEY`               |
| `PRIVATE_KEY_L1` | `SignatureCrypt.java:34`  | `PRIVATE_KEY_L1_HEX`          |
| `PUBLIC_KEY_K2`  | `SignatureCrypt.java:35`  | `PUBLIC_KEY_K2_DER_HEX`       |

The field names have been stable across every APK version examined so far.

**Caveat.** A new device model may ship different key values. If the
handshake reaches the ECDH confirmation step and the device returns status
`0x01` (app-pubkey signature rejected), the baked-in L1/K2 do not match
that model's firmware. Pull the new values from the corresponding APK
version following the recipe above, update `handshake.py`, and open a PR.
See {doc}`/protocol/security` for the status semantics.

## macOS notes

macOS uses a different Bluetooth stack. If you encounter device discovery
issues, try using a Linux VM or a Raspberry Pi for the BLE capture step.
The btsnoop parsing step doesn't require Bluetooth — it can run on any
platform.

## Charging mode register (2020)

V2 devices that expose charging mode on register 2020 use these values
per APK v3.0.10 `DeviceSettingsChgModeActivity` (hardware-confirmed on
EL100V2):

| Value | Mode     |
| ----- | -------- |
| 0     | Standard |
| 1     | Silent   |
| 2     | Turbo    |

**PLP024-series exception.** PLP024-series devices use a different
mapping: `standard=2`, `turbo=3`. If you are adding a PLP024-series
device, do **not** use the v2_base.py `ChargingMode` enum — define a
local enum with the correct values.
