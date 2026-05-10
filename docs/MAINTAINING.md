# Maintainer Guide — Adding a New Device from Contributor Submissions

This guide is for maintainers receiving a `my-device.yaml` (probe output)
and optionally a `draft.yaml` (annotation output) and/or `btsnoop_hci.log`
from a contributor following [`CONTRIBUTING_DEVICES.md`](CONTRIBUTING_DEVICES.md).

It walks from raw submission to a merged device class.

## 1. Triage

Run the validator on the probe output first:

```bash
bluetti-cli validate-profile my-device.yaml
```

You're looking for:

- **`protocol`** is `v1` or `v2`. `unknown` means the contributor's probe
  couldn't reach the device — go back to them, don't proceed.
- **`protocol_version`** is non-null. For V1 this is in the 1016–1026 range;
  V2 is ≥ 2000.
- **`name`** matches a Bluetti BLE prefix (e.g. `AC2A2305000`). Confirm the
  prefix isn't already in `_device_registry()` in
  `src/bluetti_cli/bluetooth/__init__.py`.
- **`blocks`** has mostly-non-empty `raw_hex` entries. All-zero or all-FF
  blocks suggest the device wasn't responding — flag back to contributor.

## 2. Cross-reference the APK

The decompiled APK at `bluetti-files/jadx_out/` is authoritative for any
device-class flag the contributor's data can't tell you (writable
register set, low-power vs. high-power class, BMS pack support, etc.).

```bash
# Find the model in the APK's central dispatcher:
grep -n '"<MODEL>"' bluetti-files/jadx_out/sources/net/poweroak/bluetticloud/ui/connect/DeviceConnUtil.java
```

In the matching `new DeviceFunction(...)` constructor call, the **6th
positional arg is `isLowPower`** and the **3rd is `minProtocolVer`**.
Other flags worth eyeballing (positions vary; cross-check against the
`copy()` signature in `DeviceFunction.java`):

- `isLowPower` — if `true`, V1 alarm/fault decoding uses the V2
  `lowPowerWarnNames`/`lowPowerFaultNames` tables (see `_v1_alarm_tables.py`).
- `bmsPack` / `bmsPackV2` — controls whether BMS_PACK reads are wired in.
- `chargingMode` / `chgModeCustom` — adds a `charging_mode` writable enum.
- `acECOCtrl` / `dcECOCtrl` — adds eco-mode writables.
- `factoryReset` — adds the `factory_reset` writable bool.

**If the contributor's data disagrees with the APK, the APK wins.**
Document the divergence in the new model file's `# ABOUTME:` comment so
future readers see why the class diverges from the contributor's
submission. (See `src/bluetti_cli/core/devices/ac60.py` for an example.)

## 3. Pick the base class

| `minProtocolVer` (from APK) | Base class | Notes |
|------------------------------|------------|-------|
| `< 2000`                     | `V1Base`   | Use V1Base default `ALARM_NAMES`/`FAULT_NAMES` (ConnectConstants). |
| `< 2000` AND `isLowPower=true` | `V1Base` | Override `ALARM_NAMES`/`FAULT_NAMES` to `LOW_POWER_*` from `_v1_alarm_tables.py`. AC240/AC200L family. |
| `>= 2000`                    | `V2Base`   | Default ÷10 voltage scale. |
| `>= 2000`, high-voltage pack | `V2Base`   | EP600 family — keep ÷10 voltage scale (it's already the V2Base default). |

If you're unsure, dispatch: V1 vs V2 hinges on `protocolVer < 2000` per
`ProtocolParse.getReadTask` — same threshold the runtime uses.

## 4. Build the class from a template

Pick the closest existing model as your starting point:

- **V2 with controls**: copy `src/bluetti_cli/core/devices/ac60.py`.
- **V2 read-only**: copy `src/bluetti_cli/core/devices/ep600.py`.
- **V1 with controls**: copy `src/bluetti_cli/core/devices/ac300.py`.
- **V1 minimal**: copy `src/bluetti_cli/core/devices/eb3a.py`.
- **V1 lowPower variant**: copy `src/bluetti_cli/core/devices/ac200l.py`.

What to fill in:

- **`WRITABLE_FIELD_NAMES`**: derive from the APK's `DeviceFunction`
  flags (which control surfaces are wired up). Use existing names
  (`ac_output`, `dc_output`, `charging_mode`, `power_lifting`,
  `battery_range_start`, `soc_low`, `soc_high`, `factory_reset`,
  `inv_voltage`, `inv_freq`) before inventing new ones.
- **`_build_control_struct`**: V1 writable registers are in 3000–3099,
  V2 in 2000–2299. Cross-reference `ProtocolAddr` (V1) and
  `ProtocolAddrV2` (V2) constants for canonical names.
- **`_fill_*` helpers in `parse()`**: only needed if the model has
  array/struct fields (PV strings, AC phases) the base class doesn't
  parse generically. Most new models won't need this.
- **TODO comment**: leave `# TODO(<MODEL>): verify against hardware` at
  the top until a maintainer (or the contributor) has run
  `bluetti-cli status` and confirmed sane values.

If the contributor sent an annotation YAML (`draft.yaml`), each entry
in `annotations` says *"in block X, byte offset Y is field Z"*. Convert
those to register fields:

```
register = block.address + (byte_offset // 2)
byte_within_register = byte_offset % 2  # 0=high, 1=low
```

Then add a `s.add_uint_field("z", register)` (or the appropriate
typed helper) to `_build_real_data_struct`.

## 5. Wire the registry

In `src/bluetti_cli/bluetooth/__init__.py`:

1. Import the new class in `_device_registry()`.
2. Add `"<PREFIX>": <ClassName>` to the returned dict.
3. Update `_DEVICE_NAME_SN_RE` to include the new prefix in its
   alternation. The regex must match the BLE-advertised name exactly.

## 6. Tests

In `tests/test_device_registry.py`:

- Add the prefix to `ALL_PREFIXES`.
- If V1: add to `test_v1_models_are_v1`.
- If V2: add to `test_v2_models_protocol_version`.
- If it has writable fields: confirm via `test_v1_model_has_writable_control_struct`
  (or write the V2 equivalent if needed).

Run `uv run pytest -q` — the parametrized registry tests will exercise
the new class automatically.

## 7. Decoding encrypted btsnoop captures (V2 only)

If the contributor sent `btsnoop_hci.log` from a V2 device, the BLE
frames are AES-128-CBC encrypted with a per-session key. The
`scripts/parse_btsnoop.py` script accepts `--key` and `--iv` but
extracting them currently requires running a paired session.

**Recipe:**

1. Pair `bluetti-cli` against the same physical device the contributor
   captured from. Patch `src/bluetti_cli/bluetooth/handshake.py:144`
   temporarily to log `shared_key.hex()` and `initial_iv.hex()`:
   ```python
   import logging
   logging.getLogger(__name__).warning(
       "session: key=%s iv=%s", shared_key.hex(), initial_iv.hex()
   )
   return CbcSession(shared_key, initial_iv)
   ```
2. Run `bluetti-cli status <ADDR>` against the device with `-v` so the
   handshake fires. Capture the logged key + IV.
3. Feed them into the parser:
   ```bash
   python scripts/parse_btsnoop.py contributor.log --key <hex> --iv <hex> > capture.csv
   ```
4. Revert the handshake.py patch — don't merge the key-logging into
   main; sessions are per-pair so logging them indefinitely leaks
   privacy without value.

**Caveat: only the first encrypted frame in the capture decrypts
cleanly.** The Bluetti per-frame IV chain (FINDINGS §15.8) isn't yet
implemented in `_make_decryptor`. For now, use the parser to confirm the
first frame's plaintext, then walk the remaining frames manually with a
small Python script that maintains the IV chain.

## 8. Document the divergence

If the APK said one thing and the contributor's data said another,
record it in the new model file's ABOUTME block. Pattern from
`src/bluetti_cli/core/devices/ac60.py`:

```python
# ABOUTME: AC60 small portable — V2 protocol per Android code (minProtocolVer=2000).
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC60 as V1Base, but the Android
# ABOUTME:   DeviceConnUtil.java sets minProtocolVer=2000, which is V2.
# ABOUTME: TODO(AC60): verify against hardware.
```

This is how future maintainers (and sub-agents) understand why the
class doesn't match the most obvious-looking source.

## 9. Merge

- Verify `uv run pytest`, `uv run ruff check src/ tests/`, and
  `uv run mypy src/bluetti_cli` all pass.
- Open a PR; commit message style is lowercase imperative (see
  `IMPLEMENTATION_UNITS.md` ground rules for examples).
- Reply to the contributor's issue with the merged PR + a thank-you.
- If the model is hardware-verified (by you or the contributor), drop
  the `TODO(<MODEL>): verify against hardware` comment.
