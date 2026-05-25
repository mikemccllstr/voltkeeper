# Maintainer Guide — Adding a New Device from Contributor Submissions

This guide is for maintainers receiving a `my-device.yaml` (probe output)
and optionally a `draft.yaml` (annotation output) or `btsnoop_hci.log`
from a contributor.

## 1. Triage

Run the validator on the probe output first:

```bash
voltkeeper validate-profile my-device.yaml
```

You're looking for:

- **`protocol`** is `v1` or `v2`. `unknown` means the contributor's probe
  couldn't reach the device — go back to them, don't proceed.
- **`protocol_version`** is non-null. For V1 this is in the 1016–1026 range;
  V2 is >= 2000.
- **`name`** matches a Bluetti BLE prefix (e.g. `AC2A2305000`). Confirm the
  prefix isn't already in `_device_registry()`.
- **`blocks`** has mostly-non-empty `raw_hex` entries. All-zero or all-FF
  blocks suggest the device wasn't responding — flag back to contributor.

## 2. Cross-reference the APK

The decompiled APK in `bluetti-files/jadx_out/` is authoritative for any
device-class flag the contributor's data can't tell you.

```bash
grep -n '"<MODEL>"' bluetti-files/jadx_out/sources/net/poweroak/bluetticloud/ui/connect/DeviceConnUtil.java
```

In the matching `new DeviceFunction(...)` constructor call, the **6th
positional arg is `isLowPower`** and the **3rd is `minProtocolVer`**.
Other flags worth eyeballing: `bmsPack`, `bmsPackV2`, `chargingMode`,
`chgModeCustom`, `acECOCtrl`, `dcECOCtrl`, `factoryReset`.

**If the contributor's data disagrees with the APK, the APK wins.**
Document the divergence in the new model file's `# ABOUTME:` comment.

## 3. Pick the base class

| `minProtocolVer` (from APK)    | Base class | Notes                                  |
| ------------------------------ | ---------- | -------------------------------------- |
| `< 2000`                       | `V1Base`   | Use V1Base default alarm/fault names   |
| `< 2000` AND `isLowPower=true` | `V1Base`   | Override to `LOW_POWER_*` alarm tables |
| `>= 2000`                      | `V2Base`   | Default /10 voltage scale              |
| `>= 2000`, high-voltage pack   | `V2Base`   | EP600 family                           |

## 4. Build the class from a template

Pick the closest existing model as your starting point:

- **V2 with controls**: copy `ac60.py`
- **V2 read-only**: copy `ep600.py`
- **V1 with controls**: copy `ac300.py`
- **V1 minimal**: copy `eb3a.py`
- **V1 lowPower variant**: copy `ac200l.py`

What to fill in:

- **`WRITABLE_FIELD_NAMES`**: derive from APK's `DeviceFunction` flags
- **`_build_control_struct`**: V1 writable registers in 3000–3099, V2 in 2000–2299
- **`_fill_*` helpers in `parse()`**: only needed for array/struct fields
- **TODO comment**: leave `# TODO(<MODEL>): verify against hardware`

## 5. Wire the registry

In `src/voltkeeper/bluetooth/__init__.py`:

1. Import the new class in `_device_registry()`
1. Add `"<PREFIX>": <ClassName>` to the returned dict
1. Update `_DEVICE_NAME_SN_RE` to include the new prefix

## 6. Tests

In `tests/test_device_registry.py`:

- Add the prefix to `ALL_PREFIXES`
- If V1: add to `test_v1_models_are_v1`
- If V2: add to `test_v2_models_protocol_version`
- If it has writable fields: confirm via registry tests

Run `uv run pytest -q` — the parametrized registry tests will exercise
the new class automatically.

## 7. Decoding encrypted btsnoop captures (V2 only)

If the contributor sent `btsnoop_hci.log` from a V2 device:

> **Warning:** Steps 1–2 require a temporary patch that logs session key material.
> This patch MUST be reverted and MUST NOT be committed or merged.

1. Pair voltkeeper against the same physical device the contributor captured
   from. Patch `src/voltkeeper/bluetooth/handshake.py` temporarily to log
   `shared_key.hex()` and `initial_iv.hex()`
1. Run `voltkeeper status <ADDR>` against the device with `-v`
1. Feed key and IV into the parser:
   ```bash
   python scripts/parse_btsnoop.py contributor.log --key <hex> --iv <hex> > capture.csv
   ```
1. Revert the `handshake.py` patch immediately — verify with `git diff` before pushing

## 8. Merge

- Verify `uv run pytest`, `uv run ruff check src/ tests/`, and
  `uv run mypy src/voltkeeper` all pass
- Open a PR; lowercase imperative commit message
- Reply to the contributor's issue with the merged PR
- If the model is hardware-verified, drop the `TODO: verify against hardware` comment
