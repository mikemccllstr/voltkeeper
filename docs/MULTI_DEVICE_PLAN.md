# Multi-Device Support for `bluetti-cli`

## Context

The CLI currently supports only the AC2A. The factory at `src/bluetti_cli/bluetooth/__init__.py:84-88` always returns `AC2A`, the BLE client at `src/bluetti_cli/bluetooth/client.py` assumes plaintext Modbus, and AC2A is referenced by name in `cli.py:953` (MQTT topic) and `cli.py:483-488` (capabilities display). The base class `BluettiDevice` is already clean — it exposes `polling_commands`, `logging_commands`, `parse()`, `writable_ranges`, `has_field()`, `has_field_setter()`, and `build_setter_command()` — so the contract is reusable.

`docs/FINDINGS.md` documents 100+ Bluetti models. Two protocol generations exist: **V1** (`ProtocolAddr`, `protocolVer < 2000`, §15.5 V1 table) and **V2** (`ProtocolAddrV2`, ≥2000, §15.5 V2 table, AC2A uses this). Newer devices wrap Modbus in **AES-128-CBC over BLE** with session keys derived via ECDH+ECDSA (§15.2 step 3, §15.8). Manufacturer-specific scan data identifies encryption: `BLUETTI` = plaintext, `BLUETTE`/`BLUETTF` = encrypted (§15.1).

Goal: refactor so adding a new device is a self-contained Python file plus a registry entry, ship the encrypted-BLE transport so newer devices work, and provide discovery tooling that lets a contributor with an unfamiliar device produce enough info for us to author a class.

User-confirmed choices:
- **Encryption: implement now** (full ECDH+AES-CBC).
- **Profile format: one Python class per model** (mirror AC2A pattern, no YAML loader).
- **Discovery tools: all four** — active probe, btsnoop parser, profile validator, interactive annotator.

---

## What Bluetti's official GitHub org tells us (independent of, but informed by)

We must remain code-independent — we will not vendor or import from these repos. We can study them for protocol clues and use any released test vectors to validate our reimplementation.

| Repo | Useful? | What we take from it |
|---|---|---|
| `bluetti-official/bluetti-home-assistant` (MIT, Python) | Indirectly | **Reference model list**: AP300, EL300, EL320, EL400, EP13K, EP2000, EP6K, EP760, EP500Pro, FP, PR100V2, EL100V2, AORA100V2, PR200V2, EL200V2, AORA200, PR30V2, EL30V2, AORA30V2, RV5, Balco260, Balco500, AC300, AC500, AC200PL, AC200L. **Pure cloud/OAuth — no BLE.** Tells us nothing about local protocol but defines the product universe. The `profile/` directory pattern (`application.yaml` + `application_profile.py`) is *cloud* metadata — not transferable to our BLE register layout. |
| `bluetti-official/bluetti-bluetooth-lib` (no LICENSE) | Cautionary | Bluetti's official BLE crypto is shipped as a **closed-source binary** (`_bluetti_crypt.so` / `.pyd`) with a Python wrapper. `ble_crypt_link_handler()` returns status codes **0–4**, including a step **status 3 = "SN validation"**. This raises the possibility that some encrypted devices add a **per-SN key-binding step on top of the ECDH handshake we documented in FINDINGS §15.2**. We should design `handshake.py` so it can detect and report this case rather than silently fail. The `examples/` folder likely contains input/output byte patterns we can borrow as known-answer **test vectors** — extracted as data, not code. **No LICENSE file present**, so we must not redistribute or link against the binary; reimplementation is the only path. |
| `bluetti-official/bluetti-open-sdk-java` (sparse) | Watch | Java SDK for the "Open Platform" — likely the cloud OAuth API the HA integration uses. Not relevant to our local-BLE focus today. Worth re-checking when populated, in case a server-side telemetry path becomes useful. |
| `bluetti-official/bluetti-modbus-tcp-slave` (empty stub) | **Watch closely** | When populated, this will be Bluetti's own Modbus TCP slave example. The same physical device exposes the same register map locally over TCP/IP as it does over BLE Modbus, so this would become the **authoritative documentation for the V1/V2 register tables in FINDINGS §15.5**. Set up a manual reminder to re-fetch this repo periodically; incorporate any official register names into our device classes when it lands. |
| `bluetti-official/bluetti-bluetooth-broadcast` (empty stub) | Watch | Likely will document the BLE advertising/scan-record format (manufacturer-specific data, encryption flag prefixes) and possibly broadcast OTA. When populated, validate our `BLUETTI`/`BLUETTE`/`BLUETTF` prefix detection against it. |

**Net effect on this plan:**
1. Expand the model target universe per the HA integration's published list (Phase 3 gets a longer second tier).
2. Add a sub-task in Phase 2 to capture bytes from `bluetti-bluetooth-lib/examples/` as **test vectors** for our crypto reimplementation (data only, not code).
3. Add a documented failure mode for "SN-validation handshake step" — newer encrypted devices may need additional work that the FINDINGS doc doesn't cover.
4. No code lift from any of these repos. Everything we use is data (model names, byte vectors) or behavioral observation.

---

## Phase 1 — Decouple AC2A assumptions

**Modify `src/bluetti_cli/bluetooth/__init__.py`:**
- Replace `build_device()` with a registry-driven dispatch:
  ```python
  DEVICE_REGISTRY: dict[str, type[BluettiDevice]] = {
      "AC2A": AC2A, "EP600": EP600, "AC300": AC300, ...
  }
  ```
- Expand `_DEVICE_NAME_SN_RE` to match every prefix in the registry.
- Parse manufacturer-specific data in `scan_devices()` and return an `(address, name, encrypted: bool, protocol_hint: str|None)` tuple. Detect prefix `424c5545545449` (BLUETTI = plaintext) vs `424c5545545445`/`424c5545545446` (BLUETTE/F = encrypted).
- When the model prefix is unknown but a device responds, fall back to a `GenericV2Device` (or V1) so `probe` still works on never-before-seen models.

**Modify `src/bluetti_cli/cli.py`:**
- `cli.py:953` — pull the MQTT topic prefix from `device.type`, not the literal `"AC2A"`.
- `cli.py:483-488` — replace direct `AC2A.decode_ctrl_event()` / `AC2A.CTRL_EVENT_BITS` access with optional capability methods on `BluettiDevice` (`decode_ctrl_event(value) -> dict | None`, default `None`). Render the capabilities block only when the device opts in.

**Modify `src/bluetti_cli/mqtt_client.py`:** ensure HA discovery topic and sensor lists are derived from device fields rather than hardcoded names.

---

## Phase 2 — Encrypted BLE transport

Add `cryptography` to `pyproject.toml` dependencies (provides AES-CBC, ECDSA, ECDH on `SECP256R1`).

**New `src/bluetti_cli/bluetooth/handshake.py`:**
- Constants from FINDINGS §15.8:
  - `LOCAL_AES_KEY = bytes.fromhex("459FC535808941F17091E0993EE3E93D")`
  - `PRIVATE_KEY_L1 = bytes.fromhex("4F19A16E…F337")`
  - `PUBLIC_KEY_K2 = bytes.fromhex("3059…8594")` (DER SubjectPublicKeyInfo)
- `async legacy_challenge_response(client) -> bytes` — implements §15.2 step 3a: read `2A 2A 01 + 4 random`, MD5(reverse), reply `2A 2A 02 04 + md5[16:24] + checksum`, return `bleConnAESKey = XOR(randomMd5_hex_str, LOCAL_AES_KEY)`.
- `async ecdh_handshake(client, randomMd5, bleConnAESKey) -> bytes` — implements §15.2 step 3b: receive AES-CBC encrypted device pubkey + ECDSA signature, verify against `PUBLIC_KEY_K2`, generate ephemeral keypair, sign `(appPubKey || randomMd5)` with `PRIVATE_KEY_L1`, send back, derive `bleConnShareKey = ECDH(appPriv, devicePub)`.

**New `src/bluetti_cli/bluetooth/cipher.py`:**
- `build_aes_cbc_cmd(plaintext: bytes, key: bytes, iv: bytes) -> bytes` — AES-128-CBC, IV chained from `MD5(randomMd5)`, 16-byte blocks, **no PKCS padding** (zero-pad to block boundary per §15.8).
- `parse_aes_cbc_data(ciphertext: bytes, key: bytes, iv: bytes) -> bytes` — inverse.
- IV-chaining helper that tracks the previous ciphertext block across calls within a session.

**Modify `src/bluetti_cli/bluetooth/client.py`:**
- `BluetoothClient(address, encrypted: bool = False)`. When `encrypted`, after `connect()` run the handshake module and store the session key + IV state.
- `execute()` wraps the outgoing Modbus frame in `build_aes_cbc_cmd` and unwraps notifications via `parse_aes_cbc_data` when a session key exists. Otherwise falls through to the existing plaintext path.
- Keep CRC validation on the *plaintext* (post-decrypt) frame.

**Cross-check against Bluetti's own crypto lib (data only, no code lift):**
- Pull byte fixtures from `bluetti-official/bluetti-bluetooth-lib/examples/` — request bytes, encrypted-response bytes, and any documented session-key inputs.
- Bake those into `tests/test_handshake_vectors.py` and `tests/test_cipher_vectors.py` as **known-answer tests**. If our reimplementation doesn't reproduce their outputs bit-for-bit, the test fails.
- **Anticipate `ble_crypt_link_handler` status 3 (SN validation):** if our handshake reaches the data-exchange phase but every Modbus response decrypts to garbage, log a clear "this device may use the per-SN key-binding step Bluetti's licensed lib provides — not yet implemented" message rather than silent failure. Capture the full handshake transcript in a debug log so it can be analysed and added later.

**Move GATT UUIDs** from `client.py:11-12` to `bluetooth/__init__.py` (reused by handshake, probe, annotate). The service/notify/write UUIDs are universal across Bluetti models per §15.1.

---

## Phase 3 — Per-model device classes

Add a thin protocol-version base under `core/devices/` so per-model files stay short:

**New `src/bluetti_cli/core/devices/v2_base.py`** — implements the generic V2 register-block layout from §15.5 V2:
- `home_struct` (100), `inv_base_struct` (1100), `inv_pv_struct` (1200), `inv_grid_struct` (1300), `inv_load_struct` (1400), `inv_inv_struct` (1500), `control_struct` (2000–2300).
- Default scale factors using the *typical* V2 device convention (`packTotalVoltage` ÷10 for high-voltage packs).
- Default `parse()` dispatching by address range.
- Default `polling_commands` covering all blocks.

**New `src/bluetti_cli/core/devices/v1_base.py`** — analogous for §15.5 V1 register layout (registers 1, 7, 10, 16, 21, 22, 70, 91, 130, 157, 3000-series settings, etc.).

**Refactor `src/bluetti_cli/core/devices/ac2a.py`** to inherit from `V2Base`, keeping only:
- `protocol_version = 2000`
- The `÷100` voltage scale override (already commented at `ac2a.py:62-64`)
- AC2A-specific custom parsers (`_fill_software_versions`, `_fill_pv_strings`, etc.)
- `WRITABLE_FIELD_NAMES`, `CTRL_EVENT_BITS`, `decode_ctrl_event`

**Initial new model files** (one Python class each, ~50–150 lines, depending on quirks):
- `ep600.py`, `ep760.py`, `ep500pro.py`, `ep13k.py`, `ep2000.py`, `ep6k.py` — V2 home power stations (the EP-series Bluetti's HA integration emphasises)
- `ac300.py`, `ac500.py`, `ac200pl.py`, `ac200l.py` — V2, larger inverter class
- `ac200max.py` — V2, mid-range
- `eb3a.py` — V1 small portable (per §15.4 thresholds)
- `ac60.py` — V1 portable

The full target universe (mirroring `bluetti-official/bluetti-home-assistant` published support): AP300, EL300, EL320, EL400, EP13K, EP2000, EP6K, EP760, EP500Pro, FP, PR100V2, EL100V2, AORA100V2, PR200V2, EL200V2, AORA200, PR30V2, EL30V2, AORA30V2, RV5, Balco260, Balco500, AC300, AC500, AC200PL, AC200L (plus AC2A which is already supported). Note: HA's list reflects what they support over **cloud OAuth**, which doesn't guarantee BLE Modbus parity — some of these may not expose the same register surface locally. Treat the list as a target wishlist, not a contract.

Pick which models to ship in the first PR by tractability: prefer ones whose register quirks are documented in FINDINGS or that we can probe on real hardware. Every other model lands as a separate PR once a contributor runs the discovery tools against it.

---

## Phase 4 — Discovery toolkit (the "let another user help" surface)

### 4a. `bluetti-cli probe ADDRESS [-o profile.yaml]` — active register sweep

New `src/bluetti_cli/probe.py`:
1. Connect (auto-detecting encrypted vs plaintext from scan record).
2. Read protocol version: register 16 (V1) or register 1100 first word (V2 fallback).
3. Read base config (register 1 V1 / 2000 V2), device SN, model name (register 110 V2 / 21 V1).
4. Sweep every register block listed in §15.5 V1+V2 in 32-register chunks; on each block, record: address, length read back, raw hex, parsed by `V1Base` / `V2Base` if structure is known.
5. Emit a YAML draft profile with: model name, prefix, encryption flag, protocol version, per-block raw hex dumps, fields that parsed to sane values, fields that need attention (always-zero, all-0xFFFF, out-of-range).

Output is meant to be pasted into a GitHub issue; we use it to author the per-model class manually.

### 4b. btsnoop helper (documentation + parser)

New `scripts/parse_btsnoop.py` (one-shot script, kept out of the package):
- Reads Android `btsnoop_hci.log` (BR/EDR + LE both supported via Bluetooth HCI Snoop format).
- Filters ATT writes/notifications on the Bluetti GATT handles.
- Optionally decrypts AES-CBC frames given a session key (printed by Bluetti app under verbose logcat or recovered from a paired session).
- Emits a CSV/JSON timeline of (timestamp, direction, modbus_function, register, value).

New `docs/CONTRIBUTING_DEVICES.md` with step-by-step guide:
1. Enable Developer Options + "Enable Bluetooth HCI snoop log" on Android.
2. Reproduce a Bluetti app workflow against your device (e.g., toggle AC, change charging mode).
3. `adb bugreport` → extract `btsnoop_hci.log`.
4. `python scripts/parse_btsnoop.py btsnoop_hci.log > capture.csv`.
5. Run `bluetti-cli probe ADDRESS -o my_device.yaml`.
6. Open a GitHub issue with both files attached.

### 4c. `bluetti-cli validate-profile profile.yaml ADDRESS`

New `src/bluetti_cli/validate.py`:
- Load YAML draft (the format `probe` emits).
- Connect, run polling against every block in the profile.
- For each field: check value is within a declared sane range; flag `SUSPECT` (always 0/0xFFFF; floats wildly out of bounds; signed/unsigned mismatch).
- Report a table grouped by block with OK / SUSPECT / ERROR counts and example values.

### 4d. `bluetti-cli annotate ADDRESS`

New `src/bluetti_cli/annotate.py` (interactive REPL):
- Connect, poll all known register blocks at 1 Hz.
- Render a live diff view: when any register value changes, highlight it.
- Prompt: "Register 2011 just changed `0 → 1`. Suggested name (`<enter>` to skip): "
- Append annotations to a YAML draft profile in-place; persist immediately so a Ctrl-C never loses work.
- Operator workflow: toggle each switch on the physical device, watch which registers move, label them.

---

## Phase 5 — Tests (TDD per `AGENTS.md`)

**Unit (no BLE):**
- `tests/test_handshake.py` — challenge-response + ECDH against fixed inputs from FINDINGS §15.8 (verify `bleConnAESKey` and ECDH shared secret derivations match expected hex).
- `tests/test_cipher.py` — AES-CBC roundtrip with chained IV; known-answer test.
- `tests/test_v2_base.py` — replay a recorded AC2A polling response (move from existing tests if any) and verify identical output.
- `tests/test_devices_<model>.py` — one per new model, replaying recorded responses from `tests/fixtures/<model>/`.
- `tests/test_probe.py` — pass a synthetic captured response, verify YAML emission.

**Integration (gated by `-m integration`, requires hardware):**
- `tests/test_integration.py` extension — for each model the test machine has, run `probe`, `validate-profile`, and a minimal `status` round-trip.

---

## Files to add or modify

**Modify:**
- `pyproject.toml` — add `cryptography` dep
- `src/bluetti_cli/bluetooth/__init__.py` — registry, regex, manufacturer-data
- `src/bluetti_cli/bluetooth/client.py` — optional cipher hookup
- `src/bluetti_cli/cli.py` — remove AC2A literals; add `probe` / `validate-profile` / `annotate` subcommands
- `src/bluetti_cli/mqtt_client.py` — model-agnostic topic
- `src/bluetti_cli/core/devices/ac2a.py` — re-parent on `V2Base`; trim duplicates
- `README.md` — add multi-device section pointing at `docs/CONTRIBUTING_DEVICES.md`

**Add:**
- `src/bluetti_cli/bluetooth/handshake.py`
- `src/bluetti_cli/bluetooth/cipher.py`
- `src/bluetti_cli/core/devices/v1_base.py`
- `src/bluetti_cli/core/devices/v2_base.py`
- `src/bluetti_cli/core/devices/ep600.py`, `ac300.py`, `ac500.py`, `ac200max.py`, `eb3a.py`, `ac60.py` (initial set)
- `src/bluetti_cli/probe.py`
- `src/bluetti_cli/validate.py`
- `src/bluetti_cli/annotate.py`
- `scripts/parse_btsnoop.py`
- `docs/CONTRIBUTING_DEVICES.md`
- `tests/fixtures/<model>/polling_response.bin` (one per recorded model)
- `tests/test_handshake.py`, `tests/test_cipher.py`, `tests/test_v2_base.py`, `tests/test_v1_base.py`, `tests/test_probe.py`, `tests/test_devices_<model>.py`

---

## Verification

End-to-end checks before merging:

1. `uv run pytest` — all unit tests pass; existing AC2A tests untouched.
2. `uv run pytest -m integration` against an AC2A — `status`, `write ac_output on`, and `mqtt-publish` still work.
3. `bluetti-cli scan` — encrypted vs plaintext devices both classified in output.
4. `bluetti-cli probe AA:BB:CC:DD:EE:FF -o draft.yaml` against any reachable Bluetti device — produces a usable draft even for unsupported models.
5. `bluetti-cli validate-profile draft.yaml AA:BB:CC:DD:EE:FF` — runs cleanly on the device used to generate it.
6. On at least one non-AC2A device available in development (target: EP600 if hardware accessible), `bluetti-cli status` returns a populated reading.
7. Run `scripts/parse_btsnoop.py` against a captured trace from the Android app and confirm Modbus frames are reconstructed.

---

## Platform support

| Surface | Linux | macOS | Windows | Notes |
|---|---|---|---|---|
| `scan`, `status`, `write` | yes | yes | yes | All BLE goes through `bleak`, which has BlueZ / CoreBluetooth / WinRT backends. |
| `probe`, `validate-profile`, `annotate` (new) | yes | yes | yes | Pure `bleak` + `cryptography` + stdlib. No OS-specific calls. |
| Encrypted handshake (new) | yes | yes | yes | `cryptography` (AES, ECDSA, ECDH on `SECP256R1`) is wheels-on-all-three. |
| `mqtt-publish` | yes | yes | yes | `paho-mqtt` is cross-platform. |
| `mqtt-listen` (latched shutdown) | yes | abort | abort | Calls `shutdown` / `systemctl`. Stays Linux-only. On macOS/Windows we should detect and abort with a clear message rather than try to run it. |
| `mqtt-publish-service`, `mqtt-listen-service` | yes | n/a | n/a | Generates **systemd** unit files. Linux-only by design. macOS would need a `launchd` plist and Windows a Service or Task — out of scope for this plan. |
| `scripts/parse_btsnoop.py` | yes | yes | yes | Pure-Python file reader; runs anywhere. The btsnoop log itself comes from Android. |
| `load-test` | yes | yes | yes | CSV + console output; cross-platform. |

**macOS quirk to document, not solve:** CoreBluetooth doesn't expose hardware MAC addresses — bleak surfaces a per-host CoreBluetooth UUID instead. Our scan output and `status ADDRESS` flow already accept whatever bleak returns, so this works, but the printed "address" on macOS won't match the MAC printed on a Linux box. We'll note this in `README.md` so users don't expect Linux-style MACs to be portable.

**Windows note:** WinRT requires Windows 10 build 19041+. Worth calling out in `README.md` once we list Windows as supported.

**README.md update:** widen the existing "Requirements" section from "Linux with BlueZ" to "Linux (BlueZ), macOS 11+, or Windows 10 build 19041+". Keep the systemd/`mqtt-listen` notes scoped to the Linux subsection.

---

## Risks and mitigations

- **Crypto correctness** — IV chaining + zero-padding (no PKCS) is unusual; mistakes show up as garbage decrypts. Mitigate with known-answer tests built from (a) a btsnoop capture and (b) byte fixtures lifted from `bluetti-bluetooth-lib/examples/` (data only).
- **Per-SN crypto step (status 3)** — Bluetti's licensed `_bluetti_crypt.so` performs an SN-validation phase that the FINDINGS doc may not fully cover. Some encrypted devices may reject our purely-ECDH-derived session key. We won't know which models until we try; mitigation is a clear diagnostic message and a debug-log transcript so the handshake can be extended later.
- **Per-model register quirks** — FINDINGS documents the AC2A in detail; other models may diverge in scales or reserved fields. The probe + validate workflow surfaces these before they become user bug reports.
- **Bluetti firmware drift** — protocol thresholds (§15.4) keep changing; pin docs to APK 3.0.8 (versionCode 1371) and refresh via `mise run prepare-all` when adding new models.
- **Hardware coverage** — we can only verify models we can physically test. Land the discovery tools first; let real-world contributors fill in the remaining classes via PR.
- **Upstream-watch chore** — `bluetti-modbus-tcp-slave` and `bluetti-bluetooth-broadcast` are empty stubs today. When Bluetti populates them, our V1/V2 register tables and scan-record parsing should be cross-checked against the official examples. Add a maintainer task: re-fetch both repos at each `prepare-all` cycle.
- **License hygiene** — `bluetti-bluetooth-lib` ships no LICENSE; `bluetti-home-assistant` is MIT but cloud-only. We may study either, lift byte-level test data from the unlicensed lib (factual data, not copyrightable), and reimplement from observation. We must not vendor source from the MIT repo without preserving the notice — but we have no need to, since it's cloud OAuth code irrelevant to BLE.
