# Test your device

This page walks you through testing a Bluetti power station with voltkeeper and
submitting a structured report that the maintainers can act on. Each step states
the command to run, the expected outcome, and what to do if it fails.

You will produce a `verify` report. The report is automatically scrubbed of
serial numbers and BLE addresses, so you can share it safely.

## Before you start

- **Install voltkeeper:** `pip install voltkeeper` (Python 3.10+ required)
- **Check BLE permissions:** On Linux, your adapter may need elevated privileges
  (`CAP_NET_ADMIN` or `sudo`). On macOS, grant Bluetooth access to your terminal
  app when prompted.
- **Turn on your Bluetti device** (display on, not standby)
- **Review the verify reference:** The [`verify` command documentation](verify.md)
  explains each tier's semantics in detail. This walkthrough refers to verify's
  write-risk levels as *stages* — they are called *tiers* in the verify
  reference and in verify output.

## Step 1 — Scan for your device

```bash
voltkeeper scan
```

You should see your device listed with its BLE address and model:

```
AA:BB:CC:DD:EE:FF  —  AC2A2345001234567  [encrypted]  [hardware_verified]
CC:DD:EE:FF:AA:BB  —  EL100V21234567890  [plaintext]  [hardware_testing]
```

Take note of the **BLE address** (the `AA:BB:CC:DD:EE:FF` part).

**If your device does not appear:**

- Make sure the device is powered on and not connected to the official app.
  Only one BLE connection is allowed at a time.
- On Linux, try `sudo voltkeeper scan`.
- On macOS, the address may appear as a UUID — use that UUID directly.
- If Scan still shows nothing, skip ahead to the
  [BLE troubleshooting](#ble-troubleshooting) section.

**If your device appears but with an unexpected model name or tier,** do not
worry — seeing the device at all means BLE is working. Continue with Step 2.

## Step 2 — Spot-check live data

```bash
voltkeeper status AA:BB:CC:DD:EE:FF
```

Replace `AA:BB:CC:DD:EE:FF` with the BLE address from Step 1.

You should see live readings: battery SOC, pack voltage, input/output wattage,
and charging status. Compare these numbers to what your device's own display
shows. They should be in the same ballpark. The SOC percentage should match
within a few points.

**If status fails to connect:**

- Confirm the device address from Step 1.
- Try `voltkeeper scan` again to confirm the device is still visible.
- If the connection fails at the BLE level (hang, timeout, or GATT error), go to
  the [BLE troubleshooting](#ble-troubleshooting) section.

**If status connects but shows `0` or missing values for fields that the
display reports:** note which fields are missing — you will mention them in your
report. Continue anyway; the verify stage will check parsing more thoroughly.

**If status panics or crashes:** capture the full error output and go to the
[BLE troubleshooting](#ble-troubleshooting) section.

## Step 3 — Verify stages 1–3 (automatic)

This step runs the first three verify stages. These stages do not modify your
device's behaviour; they are safe and fully automatic.

```bash
voltkeeper verify AA:BB:CC:DD:EE:FF --tier 3 --yes
```

- `--tier 3` stops after stage 3 (skip stages 4–6 for now).
- `--yes` pre-consents to supervised prompts (not needed for stages 1–3, but
  safe to include).

**Expected outcome:** Stages 1–3 pass with checkmarks. You will see a progress
summary like:

```
Tier 1  ████████  23/23  ✓
Tier 2  ████████  19/19  ✓
Tier 3  ████████  19/19  ✓
Report written to hardware-data/verify-<MODEL>-<DATE>.yaml
```

A YAML report is written to `hardware-data/`. If any stage shows a partial
progress bar or an ✗, individual fields may have failures — the report records
all of them. Range discrepancies (noted as `range_discrepancy: true`) are
findings, not failures; see [Interpreting verify output](verify-interpretation.md).

**If stage 1 has failures:** fields could not be parsed. Note the failing fields
and continue — even a partial report is useful.

**If the connection drops during the run:** try again. If it drops consistently,
capture a btsnoop log (see [BLE troubleshooting](#ble-troubleshooting)) and
attach it to your report.

## Step 4 — Verify stage 4 under load (supervised)

Stage 4 tests fields that affect connected loads: `ac_output`, `dc_output`,
`ctrl_grid`, `ctrl_feed`, `power_lifting`, `ac_eco_mode`, `dc_eco_mode`.

**Before running:** plug in a load (a lamp, fan, or charger) so the device has
something to toggle. The load should be something you don't mind losing power to
briefly — the stage will cycle the output.

```bash
voltkeeper verify AA:BB:CC:DD:EE:FF --tier 4 --yes
```

The command will run stages 1–3 again, then prompt for stage 4:

```
Tier 4: load-affecting fields — ac_output, dc_output, …
This will toggle outputs that affect anything plugged into the device.
Continue? [y/N]
```

Type `y` and press Enter.

**Expected outcome:** Stage 4 passes. Fields like `ac_output` and `dc_output`
are toggled on and off, and the connected load briefly loses power. The report
is updated with stage 4 results.

**If you cannot run stage 4 (no load available, critical load attached):** skip
it — press Enter or `n` to decline. You can still submit a report and claim
`HARDWARE_TESTING`. Stage 4 is required only for `HARDWARE_VERIFIED`.

## Step 5 — Submit your results

Once you have a report, file it through the structured issue form:

→ [Open a device report](https://github.com/mikemccllstr/voltkeeper/issues/new?template=device-report.yml)

The form asks for:

- Your device model and firmware version (both appear in the report's `device`
  section)
- Your voltkeeper version, OS, and Bluetooth adapter
- The verify report (paste its contents, or attach the file — GitHub requires
  renaming it to `.txt` first)
- The support tier you believe your results warrant

After submitting, a maintainer will review the report and update the device's
tier. Thank you for contributing.

______________________________________________________________________

(ble-troubleshooting)=

## BLE troubleshooting

If your device fails to connect or drops mid-session, a BLE capture helps the
maintainers diagnose the issue. The following steps work on **Linux with BlueZ**.

### 1. Enable btsnoop logging

BlueZ can record all BLE traffic to a file:

```bash
sudo btmon --write /tmp/btsnoop_hci.log &
```

If you don't have `btmon`, install it:

```bash
# Debian/Ubuntu
sudo apt install bluez

# Fedora
sudo dnf install bluez
```

### 2. Reproduce the failure

With `btmon` running in the background, run the command that fails (scan,
status, or verify). Wait for the failure to occur, then stop the capture:

```bash
# Stop btmon
sudo pkill btmon
```

### 3. Decode the capture

Run the project's decoder on the capture file:

```bash
python scripts/parse_btsnoop.py /tmp/btsnoop_hci.log
```

You will see a CSV stream of Modbus frames decoded from the BLE traffic. Review
the output to confirm it contains meaningful data (Modbus function codes 0x03
read, 0x06 write, etc.).

If your device uses Bluetooth encryption, the decoded output will be
unreadable without the session key. The key is negotiated per connection
during the handshake, so there is no fixed key you can look up — deriving it
from a capture is maintainer territory. Just attach the raw
`btsnoop_hci.log` to your report and the maintainers will decode it.

### 4. Attach the capture to your report

Attach the decoded CSV output (or the raw `btsnoop_hci.log` file) to your device
report. Mention which command failed and what error you saw.

### macOS

On macOS use PacketLogger (part of the Additional Tools for Xcode) to record
the session, then export it in **BTSnoop format** (File → Export). The decoder
only reads btsnoop files — a raw `.pklg` capture will be rejected.

### Windows

Btsnoop capture on Windows requires third-party tools (Wireshark with the
USBPcap driver). If you can produce a BTSnoop-format log, `parse_btsnoop.py`
will decode it. Otherwise describe the error and your adapter model in the
device report.
