# Implementation Units — Multi-Device Support

This document breaks down `docs/MULTI_DEVICE_PLAN.md` into discrete work units
that can be handed to a sub-agent. Each unit is self-contained: it lists its
dependencies, the exact files to touch, the code shape expected, and the
verification steps that prove it's done.

## Ground rules for every unit

1. **Branch.** All work happens on `claude/multi-device-support-0lktM`. Never
   push to `main`.
2. **TDD per `AGENTS.md`.** Write the failing test first, then implement, then
   confirm it passes.
3. **Run the full unit-test suite before committing:** `uv run pytest`. The
   existing AC2A tests must still pass after every unit.
4. **Do not break plaintext AC2A behaviour.** Until Unit 7, the BLE client is
   plaintext-only. The AC2A is the regression baseline.
5. **No code lifted from `bluetti-official` repos.** Byte-level test vectors
   (raw hex from their `examples/`) are OK as data. Source code is not.
6. **Commit message style.** Lowercase imperative, single line, no period:
   `add cipher module: aes-128-cbc with chained iv per FINDINGS §15.8`. Match
   the repo's existing style (`git log --oneline -5`).
7. **Don't auto-commit.** Present changes for human review unless explicitly
   told to commit (per `AGENTS.md`).

## Dependency graph

```
Unit 1 (registry refactor)
   └── Unit 2 (decouple AC2A literals)
         └── Unit 3 (manufacturer-data scan)
               └── Unit 4 (move GATT UUIDs)
                     ├── Unit 5 (cipher) ───┐
                     │                       │
                     │   Unit 6 (handshake)  │
                     │      └─────── depends on Unit 5
                     │                       │
                     └── Unit 7 (encrypted client) — depends on 5+6
                              ├── Unit 8 (V2 base) ── Unit 10 (per-model V2)
                              └── Unit 9 (V1 base) ── Unit 10 (per-model V1)

Unit 11 (probe)         — depends on Units 4, 7, 8, 9
Unit 12 (validate)      — depends on Unit 11
Unit 13 (annotate)      — depends on Unit 11
Unit 14 (btsnoop + docs)— depends on Unit 7 (for cipher reference); else free
```

Units 5 and 6 can run in parallel. Units 8 and 9 can run in parallel after
Unit 4. Per-model classes within Unit 10 can run in parallel once 8 and 9 land.

---

## Unit 1 — Replace `build_device` with a device registry

**Depends on:** none.
**Scope:** ~30 lines in one file.

### Goal

Today `src/bluetti_cli/bluetooth/__init__.py:84-88` hardcodes `AC2A`. Replace it
with a dict-driven dispatch so adding a new model is a one-line registry
addition.

### Files to modify

- `src/bluetti_cli/bluetooth/__init__.py` — add `DEVICE_REGISTRY`, change
  `build_device` to look up by parsed model prefix.

### Implementation shape

```python
# at module level, after imports:
def _device_registry() -> dict[str, type]:
    # Lazy import to avoid circular imports.
    from ..core.devices.ac2a import AC2A
    return {"AC2A": AC2A}


def build_device(address: str, name: str):
    sn = _parse_sn(name)
    prefix_match = _DEVICE_NAME_SN_RE.match(name.strip())
    prefix = prefix_match[1] if prefix_match else None
    registry = _device_registry()
    cls = registry.get(prefix)
    if cls is None:
        raise ValueError(
            f"Unsupported device model: {name!r}. "
            f"Known prefixes: {sorted(registry)}"
        )
    return cls(address, sn)
```

Keep the existing `_DEVICE_NAME_SN_RE` regex untouched in this unit; later
units expand it.

### Verification

1. `uv run pytest` — all existing tests pass.
2. `uv run bluetti-cli scan` (no hardware required for static check).
3. Manual: a scan that finds an AC2A still produces an `AC2A` instance — verify
   by adding a temporary `print(type(device).__name__)` in `cli.py status` and
   running against a real device, then revert.
4. Expect `ValueError` (not silent fallback) when given a fake non-AC2A name —
   write `tests/test_bluetooth_init.py::test_build_device_rejects_unknown` that
   calls `build_device("AA:BB:CC:DD:EE:FF", "EP600123456")` and asserts
   `ValueError` is raised.

### Done when

- `git diff` touches only `src/bluetti_cli/bluetooth/__init__.py` and one new
  test.
- `uv run pytest` is green.

---

## Unit 2 — Decouple AC2A literals from CLI and MQTT layers

**Depends on:** Unit 1.
**Scope:** ~50 lines across 3 files.

### Goal

Two AC2A literals leak into upper layers:

- `src/bluetti_cli/cli.py:953` — MQTT topic uses literal `"AC2A"`.
- `src/bluetti_cli/cli.py:483-488` — verbose status block calls
  `AC2A.decode_ctrl_event` and reads `AC2A.CTRL_EVENT_BITS` directly.

Move both behind device-class methods so other models can opt in.

### Files to modify

- `src/bluetti_cli/core/devices/bluetti_device.py` — add two optional helper
  methods with default `None`/`{}`.
- `src/bluetti_cli/core/devices/ac2a.py` — already has `decode_ctrl_event` and
  `CTRL_EVENT_BITS`; just confirm the new base-class signatures match.
- `src/bluetti_cli/cli.py` — call `device.decode_ctrl_event(...)` instead of
  `AC2A.decode_ctrl_event(...)`. Use `device.type` for MQTT topic prefix.
- `src/bluetti_cli/mqtt_client.py` — audit for any hardcoded `AC2A`; replace
  with `device.type`.

### Implementation shape

In `bluetti_device.py`:

```python
class BluettiDevice:
    # ... existing code ...

    # Optional capability hook. Subclasses that expose a ctrl-event bitmask
    # should override and return {bit_name: bool}. Default: None means
    # "device does not expose ctrl events" — caller should skip the section.
    def decode_ctrl_event(self, ctrl_event: int) -> dict | None:
        return None

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        return []
```

In `ac2a.py`, change the existing `@classmethod decode_ctrl_event` into an
instance method and delete the redundant module-level constant access.

In `cli.py:953` (or thereabouts):

```python
topic_prefix = f"bluetti/state/{device.type}-{sn}"
```

In `cli.py:483-488`:

```python
ctrl_event_value = parsed.get("ctrl_event")
if ctrl_event_value is not None:
    decoded = device.decode_ctrl_event(ctrl_event_value)
    if decoded:
        # render the table
```

### Verification

1. `uv run pytest` — green.
2. `grep -rn "AC2A" src/bluetti_cli/cli.py src/bluetti_cli/mqtt_client.py` —
   the only remaining matches should be in import paths or comments, never in
   topic strings or capability lookups.
3. Manual: run `bluetti-cli status -v <ADDR>` against an AC2A — capabilities
   block must look identical to before.
4. Manual: run `bluetti-cli mqtt-publish <ADDR> --broker localhost` and confirm
   the published topic is `bluetti/state/AC2A-<sn>/...` (unchanged).

### Done when

`grep -rn '"AC2A"' src/` returns matches only in `core/devices/ac2a.py`
(definition site) and `bluetooth/__init__.py` (registry).

---

## Unit 3 — Parse manufacturer-specific scan data; classify encryption

**Depends on:** Unit 1.
**Scope:** ~60 lines in `bluetooth/__init__.py` plus tests.

### Goal

Per FINDINGS §15.1, the BLE manufacturer-specific data identifies whether a
device speaks plaintext Modbus or encrypted:

| Hex prefix              | ASCII   | Meaning            |
|-------------------------|---------|--------------------|
| `424c5545545449`        | BLUETTI | Plaintext ESP32    |
| `424c5545545445`        | BLUETTE | Encrypted ESP32    |
| `424c5545545446`        | BLUETTF | Encrypted variant  |

Surface this in scan output so the user (and downstream code) can tell what
they're dealing with.

### Files to modify

- `src/bluetti_cli/bluetooth/__init__.py` — extend `scan_devices` to extract
  manufacturer-specific data via bleak's
  `AdvertisementData.manufacturer_data` dict and classify.

### Implementation shape

```python
from dataclasses import dataclass

PREFIX_PLAINTEXT = bytes.fromhex("424c5545545449")
PREFIX_ENCRYPTED = (
    bytes.fromhex("424c5545545445"),
    bytes.fromhex("424c5545545446"),
)


@dataclass(frozen=True)
class ScanResult:
    address: str
    name: str
    encrypted: bool | None  # None = could not determine

    def display(self) -> str:
        flag = "encrypted" if self.encrypted else "plaintext" if self.encrypted is False else "unknown"
        return f"{self.address}  —  {self.name}  [{flag}]"


def _classify(adv) -> bool | None:
    for blob in adv.manufacturer_data.values():
        if blob.startswith(PREFIX_PLAINTEXT):
            return False
        if any(blob.startswith(p) for p in PREFIX_ENCRYPTED):
            return True
    return None
```

Update `scan_devices` to return `list[ScanResult]`. Update
`pick_address_after_scan` to render the new display string.

### Verification

1. New unit test in `tests/test_bluetooth_init.py`:
   - Construct a `MagicMock` advertisement with
     `manufacturer_data={0xFFFF: PREFIX_PLAINTEXT + b"\x00\x01\x02"}` and
     assert `_classify` returns `False`.
   - Same for each encrypted prefix, assert `True`.
   - Empty manufacturer_data → assert `None`.
2. `uv run pytest`.
3. Manual `bluetti-cli scan` against an AC2A: output now includes
   `[plaintext]`. If you have an encrypted device in range, it shows
   `[encrypted]`.

### Done when

- `_classify` covered by unit tests for all three prefix cases plus the
  empty/unknown case.
- `bluetti-cli scan` output annotates each result.

---

## Unit 4 — Centralise GATT UUIDs

**Depends on:** Unit 3.
**Scope:** ~10 line move + import updates.

### Goal

`SERVICE_UUID` already lives in `bluetooth/__init__.py:9`. Move
`WRITE_UUID` and `NOTIFY_UUID` (currently at `client.py:11-12`) into the same
module so the upcoming handshake/probe/annotate code can import them from one
place.

### Files to modify

- `src/bluetti_cli/bluetooth/__init__.py` — add two constants.
- `src/bluetti_cli/bluetooth/client.py` — drop local definitions, import from
  package init.

### Implementation shape

In `bluetooth/__init__.py`:

```python
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
```

In `client.py`:

```python
from . import WRITE_UUID, NOTIFY_UUID
```

### Verification

1. `uv run pytest` — green.
2. `grep -rn "0000ff0[12]-" src/` should return matches only in
   `bluetooth/__init__.py`.
3. Manual: `bluetti-cli status <AC2A_ADDR>` still works.

### Done when

UUIDs defined in exactly one place.

---

## Unit 5 — AES-128-CBC cipher with chained IV

**Depends on:** Unit 4. Can run in parallel with Unit 6.
**Scope:** new module + test file.

### Goal

Implement the cipher described in FINDINGS §15.8:

- AES-128-CBC, 16-byte blocks, **no PKCS padding** (zero-pad to block size).
- IV for the first block is `MD5(randomMd5)` (i.e., MD5 of the 32-hex-char MD5
  string itself, taken as bytes).
- Subsequent blocks chain from the previous ciphertext block.

### Files to add

- `src/bluetti_cli/bluetooth/cipher.py` — pure functions plus a small session
  state class.
- `tests/test_cipher.py` — known-answer tests.

### Files to modify

- `pyproject.toml` — add `cryptography` to dependencies. Run `uv sync`
  afterwards.

### Implementation shape

```python
# src/bluetti_cli/bluetooth/cipher.py
import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def derive_iv(random_md5_hex: str) -> bytes:
    """IV is MD5 of the 32-hex-character MD5 string itself (taken as bytes)."""
    return hashlib.md5(random_md5_hex.encode("ascii")).digest()


def _zero_pad(data: bytes, block: int = 16) -> bytes:
    if len(data) % block == 0:
        return data
    return data + b"\x00" * (block - len(data) % block)


def encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    padded = _zero_pad(plaintext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(ciphertext) % 16 != 0:
        raise ValueError("Ciphertext length must be a multiple of 16")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    return dec.update(ciphertext) + dec.finalize()


class CbcSession:
    """Tracks chained-IV state across multiple encrypt/decrypt calls."""

    def __init__(self, key: bytes, initial_iv: bytes):
        self._key = key
        self._iv = initial_iv

    def encrypt(self, plaintext: bytes) -> bytes:
        ct = encrypt(plaintext, self._key, self._iv)
        self._iv = ct[-16:]
        return ct

    def decrypt(self, ciphertext: bytes) -> bytes:
        pt = decrypt(ciphertext, self._key, self._iv)
        self._iv = ciphertext[-16:]
        return pt
```

### Verification

1. `tests/test_cipher.py` — three required tests:
   - **Roundtrip:** for a fixed key and IV, `decrypt(encrypt(pt))` round-trips
     several payloads of varying length (1, 15, 16, 17, 100 bytes).
   - **IV derivation:** assert `derive_iv("abc")` equals
     `hashlib.md5(b"abc").digest()` — a sanity check that the function reads
     the *string* of hex chars, not raw bytes.
   - **Chained IV:** create `CbcSession`, encrypt three messages, assert that
     decrypting in-order recovers the originals; assert that re-decrypting the
     first message fails to round-trip (because IV state has advanced).
2. `uv run pytest tests/test_cipher.py -v`.
3. `uv pip list | grep cryptography` — confirms dep installed.

### Done when

All three tests pass, and `pyproject.toml` declares the new dep with no upper
bound (e.g., `"cryptography>=42"`).

---

## Unit 6 — BLE encryption handshake (legacy + ECDH)

**Depends on:** Unit 5 (uses `cipher` module).
**Scope:** new module + test file.

### Goal

Implement both handshake paths from FINDINGS §15.2 step 3 and §15.8.

**Constants** (FINDINGS §15.8 — embed verbatim):

```python
LOCAL_AES_KEY = bytes.fromhex("459FC535808941F17091E0993EE3E93D")
PRIVATE_KEY_L1_HEX = "4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337"
PUBLIC_KEY_K2_DER_HEX = (
    "3059301306072a8648ce3d020106082a8648ce3d030107"
    "03420004A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251"
    "EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594"
)
```

**Path 1 (legacy, FINDINGS §15.2 step 3a):**
1. Read `2A 2A 01` + 4 random bytes from device on `NOTIFY_UUID`.
2. `randomMd5_hex = md5(reverse(random_bytes)).hexdigest().upper()` (32 chars).
3. Reply on `WRITE_UUID`: `2A 2A 02 04` + ASCII bytes of `randomMd5_hex[16:24]`
   + 2-byte little-endian sum-checksum of preceding bytes.
4. Derive `bleConnAESKey` = byte-wise XOR of the 32-hex-char `randomMd5_hex`
   (interpreted as ASCII bytes — NOT as raw bytes) against `LOCAL_AES_KEY`
   *repeated*. **Re-read FINDINGS §15.8 carefully here:** the pseudocode is
   ambiguous; if the test vectors don't match, try alternative interpretations
   (XOR of `bytes.fromhex(randomMd5_hex)` with `LOCAL_AES_KEY`).

**Path 2 (ECDH, FINDINGS §15.2 step 3b):**
1. Receive `2A 2A 04 ...` AES-CBC encrypted with `bleConnAESKey` and IV
   `derive_iv(randomMd5_hex)`.
2. After decrypt: bytes `[4:68]` = device public key (raw 64-byte uncompressed
   point, no `0x04` prefix); `[68:-2]` = ECDSA signature `r||s` (64 bytes);
   last 2 bytes = sum-checksum.
3. Verify ECDSA signature over `(devicePublicKey || randomMd5_hex_ascii)`
   using `PUBLIC_KEY_K2`.
4. Generate ephemeral SECP256R1 keypair.
5. Sign `(appPublicKey || randomMd5_hex_ascii)` with `PRIVATE_KEY_L1`.
6. Send `2A 2A 05 80 ...` with our public key + signature, AES-CBC encrypted
   with `bleConnAESKey`.
7. Read `2A 2A 06 00 ...` confirmation.
8. Compute `bleConnShareKey = ECDH(appPriv, devicePub)`. Take the X
   coordinate of the shared point — first 16 bytes are the new session key.

### Files to add

- `src/bluetti_cli/bluetooth/handshake.py`
- `tests/test_handshake.py`

### Implementation shape

```python
# handshake.py
import hashlib

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature, encode_dss_signature,
)
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

# constants here…


def derive_legacy_session_key(random_bytes: bytes) -> tuple[str, bytes]:
    """Returns (randomMd5_hex, bleConnAESKey)."""
    reversed_bytes = random_bytes[::-1]
    digest = hashlib.md5(reversed_bytes).hexdigest().upper()  # 32 hex chars
    digest_ascii = digest.encode("ascii")
    # Repeat LOCAL_AES_KEY twice to match length
    extended_local = (LOCAL_AES_KEY * 2)[: len(digest_ascii)]
    aes_key_bytes = bytes(a ^ b for a, b in zip(digest_ascii, extended_local))
    # Take first 16 bytes as session key
    return digest, aes_key_bytes[:16]


def verify_device_pubkey(device_pub_raw: bytes, signature_rs: bytes,
                         random_md5_hex: str) -> ec.EllipticCurvePublicKey:
    """Verify device pubkey against PUBLIC_KEY_K2; return parsed pubkey."""
    # K2 verifies signature over (device_pub_raw + randomMd5_hex_ascii)
    k2 = load_der_public_key(bytes.fromhex(PUBLIC_KEY_K2_DER_HEX))
    r = int.from_bytes(signature_rs[:32], "big")
    s = int.from_bytes(signature_rs[32:], "big")
    der_sig = encode_dss_signature(r, s)
    message = device_pub_raw + random_md5_hex.encode("ascii")
    try:
        k2.verify(der_sig, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as e:
        raise ValueError("device pubkey signature does not verify against K2") from e
    # Convert raw 64-byte pubkey to EllipticCurvePublicKey
    return ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), b"\x04" + device_pub_raw,
    )


def sign_app_pubkey(app_pub_raw: bytes, random_md5_hex: str) -> bytes:
    """Sign with hardcoded L1 key. Returns raw r||s 64-byte signature."""
    private_value = int(PRIVATE_KEY_L1_HEX, 16)
    priv = ec.derive_private_key(private_value, ec.SECP256R1())
    der = priv.sign(
        app_pub_raw + random_md5_hex.encode("ascii"),
        ec.ECDSA(hashes.SHA256()),
    )
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def derive_shared_key(app_priv: ec.EllipticCurvePrivateKey,
                      device_pub: ec.EllipticCurvePublicKey) -> bytes:
    shared = app_priv.exchange(ec.ECDH(), device_pub)
    return shared[:16]
```

The above are pure functions — no BLE I/O. The orchestration (read from
`NOTIFY_UUID`, write to `WRITE_UUID`, drive the state machine) belongs in a
class but lives in this same module:

```python
class HandshakeSession:
    """Orchestrates challenge-response + ECDH over a connected BleakClient."""

    async def run(self, client) -> CbcSession:
        ...
```

### Verification

1. `tests/test_handshake.py` (no BLE — feed bytes directly):
   - **Legacy KAT:** for `random_bytes = b"\x01\x02\x03\x04"`, assert
     `derive_legacy_session_key` returns deterministic
     `(randomMd5_hex, ble_conn_aes_key)`. Hardcode the expected values from
     a manual computation in the test.
   - **Sign + verify roundtrip:** generate a fake "device pubkey", sign it
     with `PRIVATE_KEY_L1`, verify with K2 — expect `InvalidSignature`
     (because L1 and K2 are not a keypair). Then verify *should* succeed when
     signed with the matching private of K2 — but we don't have that. So
     instead, just confirm `sign_app_pubkey` produces a 64-byte output and
     `verify_device_pubkey` raises on garbage input.
   - **ECDH determinism:** generate two fixed-seed ephemeral keys, derive
     shared secret both ways, assert equality.
   - **Optional: vectors from `bluetti-bluetooth-lib/examples/`** — if that
     folder has captured handshake bytes, paste them in as a known-answer
     test. Document where the data came from.
2. `uv run pytest tests/test_handshake.py -v`.

### Done when

All unit tests pass. `HandshakeSession.run` is left as a documented stub if
real BLE is unavailable — Unit 7 wires it.

---

## Unit 7 — Encrypted-aware `BluetoothClient`

**Depends on:** Units 5, 6.
**Scope:** modifications to one file + integration test.

### Goal

Make `BluetoothClient` optionally drive the handshake at connect-time and wrap
every Modbus frame with `CbcSession`.

### Files to modify

- `src/bluetti_cli/bluetooth/client.py` — accept `encrypted: bool`, run
  handshake on connect, wrap `execute()` I/O in cipher.
- `src/bluetti_cli/device_handler.py` and `src/bluetti_cli/cli.py` — propagate
  the `encrypted` flag from scan results into `BluetoothClient(...)`.

### Implementation shape

```python
class BluetoothClient:
    def __init__(self, address: str, *, encrypted: bool = False):
        self.address = address
        self.encrypted = encrypted
        self.client: BleakClient | None = None
        self._session: CbcSession | None = None
        # ... existing fields ...

    async def connect(self, timeout: float = 15.0) -> None:
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=timeout)
        await self.client.start_notify(NOTIFY_UUID, self._on_notification)
        if self.encrypted:
            self._session = await HandshakeSession().run(self.client)

    async def execute(self, cmd: DeviceCommand) -> bytes:
        # ... existing retry loop, but:
        outgoing = bytes(cmd)
        if self._session:
            outgoing = self._session.encrypt(outgoing)
        await self.client.write_gatt_char(WRITE_UUID, outgoing, response=False)
        # ... wait for notification, then:
        raw = await asyncio.wait_for(self._notify_future, timeout=RESPONSE_TIMEOUT)
        if self._session:
            raw = self._session.decrypt(raw)
        # CRC check happens on the plaintext
        ...
```

**Diagnostic for SN-validation failure** (FINDINGS context — Bluetti's
licensed `_bluetti_crypt.so` has a status-3 SN-validation step that we do not
implement):

```python
# In execute(), if every CRC check fails despite a successful handshake:
raise BadConnectionError(
    "Encrypted handshake completed but Modbus responses do not validate. "
    "This device may require the per-SN key-binding step that Bluetti's "
    "licensed library performs (status 3 in ble_crypt_link_handler). "
    "Run with -v to capture the handshake transcript and open an issue."
)
```

### Verification

1. **Unit test:** mock `BleakClient`, feed pre-recorded handshake bytes,
   verify `connect()` produces a `CbcSession` with the expected key.
2. **Regression:** `uv run pytest -m integration` against an AC2A — `status`,
   `write ac_output on/off`, and `mqtt-publish` still all work (plaintext
   path unchanged).
3. **Manual encrypted test:** if an encrypted device is reachable, run
   `bluetti-cli scan` (sees `[encrypted]`), then `bluetti-cli status <ADDR>` —
   expect either a populated reading or the SN-validation diagnostic above.

### Done when

- AC2A behaviour identical.
- Encrypted-device path either works or fails with a clear, actionable error.
- No reference to `AC2A` remains in `client.py`.

---

## Unit 8 — Generic V2 base device class

**Depends on:** Unit 4. Can run in parallel with Unit 9.
**Scope:** new module + refactor of `ac2a.py`.

### Goal

Most of `ac2a.py` is the V2 register layout from FINDINGS §15.5 V2. Move the
generic structure into `v2_base.py` so per-model files just override what
differs.

### Files to add

- `src/bluetti_cli/core/devices/v2_base.py`

### Files to modify

- `src/bluetti_cli/core/devices/ac2a.py` — inherit from `V2Base`, keep only
  the AC2A-specific overrides:
  - `protocol_version = 2000`
  - The `÷100` `packTotalVoltage` scale (currently at `ac2a.py:62-64`)
  - Custom array helpers (`_fill_software_versions`, `_fill_pv_strings`,
    `_fill_grid_phases`, `_fill_load_phases`, `_fill_inv_phases`)
  - `WRITABLE_FIELD_NAMES`, `CTRL_EVENT_BITS`, `decode_ctrl_event`
  - `type = "AC2A"` in `__init__`

### Implementation shape

```python
# v2_base.py
APP_HOME_DATA = 100
INV_BASE_INFO = 1100
INV_PV_INFO = 1200
INV_GRID_INFO = 1300
INV_LOAD_INFO = 1400
INV_INV_INFO = 1500
INV_BASE_SETTINGS = 2000
INV_ADVANCE_SETTINGS = 2200


class V2Base(BluettiDevice):
    """Generic V2-protocol device (protocolVer >= 2000).

    Subclasses set self.type, optionally override scale factors by re-adding
    fields after super().__init__, and optionally append custom array
    parsers in parse().
    """

    DEFAULT_PACK_VOLTAGE_SCALE = 1  # ÷10. AC2A overrides to 2 (÷100).

    def __init__(self, address: str, type: str, sn: str):
        # build all six register-block structs with default field layouts
        # mirroring FINDINGS §15.5 V2 …
        super().__init__(address, type, sn)
        self.protocol_version = 2000

    def _build_home_struct(self): ...   # default ÷10 voltage
    def _build_inv_base_struct(self): ...
    # … etc, copy from ac2a.py verbatim, parameterised by scale …

    def parse(self, address: int, data: bytes) -> dict:
        # exact dispatch from ac2a.py:212-238, but no custom array helpers
        ...

    @property
    def polling_commands(self): ...   # default
    @property
    def logging_commands(self): return self.polling_commands
    @property
    def writable_ranges(self): return [range(2000, 2087), range(2200, 2272)]
```

`ac2a.py` becomes:

```python
class AC2A(V2Base):
    DEFAULT_PACK_VOLTAGE_SCALE = 2  # ÷100

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC2A", sn)

    def parse(self, address: int, data: bytes) -> dict:
        result = super().parse(address, data)
        if INV_BASE_INFO <= address < INV_PV_INFO:
            self._fill_software_versions(result, data)
        elif INV_PV_INFO <= address < INV_GRID_INFO:
            self._fill_pv_strings(result, data)
        # ... etc.
        return result

    # _fill_* helpers preserved verbatim
    # CTRL_EVENT_BITS, decode_ctrl_event preserved
    # WRITABLE_FIELD_NAMES preserved
```

### Verification

1. **Capture a baseline first.** Before refactoring: run any existing AC2A
   parsing test, capture `dict` outputs to a JSON fixture in
   `tests/fixtures/ac2a_baseline.json`.
2. **After refactor:** the same test inputs must produce *identical* dicts.
   Add `tests/test_ac2a_refactor.py::test_parse_matches_baseline` that loads
   the JSON and asserts equality.
3. `uv run pytest` — all tests green.
4. Live AC2A regression: `bluetti-cli status -v <AC2A_ADDR>` output looks
   identical to before.

### Done when

`ac2a.py` is under ~150 lines (down from 367) and the baseline JSON test
passes.

---

## Unit 9 — Generic V1 base device class

**Depends on:** Unit 4. Can run in parallel with Unit 8.
**Scope:** new module + tests.

### Goal

Implement the V1 register layout from FINDINGS §15.5 V1 (`protocolVer < 2000`)
in a base class. No per-model subclasses ship in this unit — those land in
Unit 10. The goal here is to have the layout ready and tested via synthetic
data.

### Files to add

- `src/bluetti_cli/core/devices/v1_base.py`
- `tests/test_v1_base.py`

### Implementation shape

V1 differs from V2 in register addresses. From FINDINGS §15.5 V1:

```python
BASE_CONFIG = 1
BLUETOOTH_PASSWORD = 7
BASE_REAL_DATA = 10
MODBUS_PROTOCOL_VER = 16
DEVICE_SN = 21
MCU_STATUS = 22
ADDITIONAL_DATA = 70
BMS_PACK = 91
THREE_PHASE_DATA = 130
PV_CHARGE_DATA = 157
WIFI_SWITCH_STATUS = 190
SETTABLE_DATA = 3000  # main switch
WORKING_MODE = 3001
INVERTER_FREQUENCY = 3003
AC_SWITCH = 3007
DC_SWITCH = 3008
PV_CONTROL = 3009
GRID_CHARGING_SWITCH = 3011
LED_CONTROL = 3034
UPS_MODE = 3035
SYSTEM_POWER_OFF = 3060
LCD_SCREEN_TIME = 3061
SET_FACTORY_RESET = 3062
ECO_CONTROL = 3063
CHARGING_MODE = 3065
POWER_LIFTING_MODE = 3066
CTRL_AC_ECO_MODE = 3067
DC_ECO_POWER = 3069
AC_ECO_POWER = 3070
OUTPUT_VOLTAGE = 3079
SYS_SWITCH_RECOVERY = 3090
```

The `BASE_REAL_DATA` block at register 10 is parsed per FINDINGS §15.6 — it's
~110 registers with a fixed offset table. Implement `_parse_base_real_data`
following that table.

The `BASE_CONFIG` block at register 1 is parsed per FINDINGS §15.7.

### Verification

1. **Synthetic input fixture:** craft a 220-byte hex blob simulating a known
   V1 device's `BASE_REAL_DATA` response (ASCII model name in bytes 0–11,
   protocolVer=1018, batterySOC=75 at offset 66–67, etc.).
2. **Parse test:** assert `V1Base().parse(10, fixture)` returns
   `{"deviceModel": "EB3A", "protocolVer": 1018, "batterySOC": 75, ...}`.
3. `uv run pytest tests/test_v1_base.py -v`.

### Done when

The synthetic-fixture test parses every documented field from FINDINGS §15.6.

---

## Unit 10 — First batch of per-model classes

**Depends on:** Units 8, 9.
**Scope:** ~50–150 lines per model, all small files. Can run multiple in
parallel as long as each agent's files don't overlap.

### Goal

Add the following models. Pick the first 3 if hardware is available; the rest
can wait for contributor PRs.

| Model    | Base class | Notes                                                |
|----------|-----------|------------------------------------------------------|
| EP600    | V2Base    | High-voltage pack — keep `÷10` voltage scale         |
| AC300    | V2Base    | Mid-large inverter                                   |
| AC500    | V2Base    | Larger inverter                                      |
| AC200L   | V2Base    | Mid-range                                            |
| AC200PL  | V2Base    | Variant of AC200L                                    |
| AC200MAX | V2Base    | Older mid-range; verify protocolVer ≥ 2000           |
| EB3A     | V1Base    | Small portable, FINDINGS §15.4 lists as V1 exception |
| AC60     | V1Base    | Small portable                                       |

### Files to add (one per model)

- `src/bluetti_cli/core/devices/ep600.py`
- `src/bluetti_cli/core/devices/ac300.py`
- `src/bluetti_cli/core/devices/ac500.py`
- `src/bluetti_cli/core/devices/eb3a.py`
- `src/bluetti_cli/core/devices/ac60.py`
- (etc.)

### Files to modify

- `src/bluetti_cli/bluetooth/__init__.py` — register every new class in
  `_device_registry()`. Update `_DEVICE_NAME_SN_RE` to match new prefixes.

### Implementation shape (example `ep600.py`)

```python
from .v2_base import V2Base


class EP600(V2Base):
    """EP600 home power station. V2 protocol, high-voltage pack."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP600", sn)
        # EP600 uses the V2 default ÷10 voltage scale; no override needed.

    # If/when probe data shows EP600-specific quirks, add overrides here.
```

For each model, leave a `# TODO(<model>): verify against hardware` comment at
the top until a maintainer has confirmed `bluetti-cli status` works.

### Verification

1. **Registry test:** parametrised pytest over the registry —
   `for prefix, cls in _device_registry().items(): assert cls.__name__`.
2. **Construction smoke:** for each model, `cls("AA:BB:CC:DD:EE:FF",
   "1234567")` must not raise.
3. `bluetti-cli scan` against any of these devices auto-selects the right
   class. Verify with a temporary `print(type(device).__name__)`.
4. **Hardware regression:** if you have any of these models, run
   `bluetti-cli status <ADDR>` and verify SOC, voltage, and load values look
   sane (compare against the device's LCD).

### Done when

- Every model in the chosen subset has a class file, registry entry, and
  regex match.
- Construction smoke test passes.
- At least one hardware-verified model.

---

## Unit 11 — `bluetti-cli probe` (active register sweep)

**Depends on:** Units 4, 7, 8, 9.
**Scope:** new module + new CLI subcommand + tests.

### Goal

Connect to a device (encrypted or plaintext), sweep documented register
blocks, and emit a YAML draft profile that a human can paste into a GitHub
issue.

### Files to add

- `src/bluetti_cli/probe.py` — sweep logic and YAML emitter.
- `tests/test_probe.py` — round-trip a synthetic capture through the YAML
  emitter.

### Files to modify

- `src/bluetti_cli/cli.py` — add `probe` subcommand.
- `pyproject.toml` — add `pyyaml` dependency.

### Implementation shape

```python
# probe.py
async def probe_device(address: str, *, encrypted: bool) -> dict:
    """Connect, sweep register blocks, return a structured profile dict."""
    client = BluetoothClient(address, encrypted=encrypted)
    await client.connect()
    profile = {"address": address, "encrypted": encrypted, "blocks": {}}
    try:
        # Try V2 protocol first (read register 1100)
        # Fall back to V1 (register 16)
        for block_addr, block_size, name in V2_BLOCKS:
            try:
                resp = await client.execute(ReadHoldingRegisters(block_addr, block_size))
                profile["blocks"][name] = {
                    "address": block_addr,
                    "size": block_size,
                    "raw_hex": resp.hex(),
                }
            except (ModbusError, BadConnectionError):
                profile["blocks"][name] = {"address": block_addr, "error": "no response"}
        return profile
    finally:
        await client.disconnect()


def emit_yaml(profile: dict, path: pathlib.Path) -> None:
    yaml.safe_dump(profile, path.open("w"), sort_keys=False)
```

CLI wiring:

```python
@cli.command()
@click.argument("address")
@click.option("-o", "--output", type=click.Path(), default="profile.yaml")
def probe(address: str, output: str) -> None:
    """Probe a Bluetti device and emit a draft profile YAML."""
    # Determine encrypted flag from a quick scan
    ...
    profile = asyncio.run(probe_device(address, encrypted=encrypted))
    emit_yaml(profile, pathlib.Path(output))
    click.echo(f"Wrote profile draft to {output}")
```

The list of register blocks to sweep is the union of FINDINGS §15.5 V1 and V2
tables — define `V1_BLOCKS` and `V2_BLOCKS` as module constants so they're
auditable.

### Verification

1. **Unit test:** `tests/test_probe.py::test_emit_yaml_round_trips` —
   construct a synthetic profile dict, emit, re-load with `yaml.safe_load`,
   assert equality.
2. **Live test (AC2A):** `bluetti-cli probe <AC2A_ADDR> -o /tmp/ac2a.yaml`.
   Open `/tmp/ac2a.yaml` and confirm it contains hex dumps for all six V2
   blocks (home, inv_base, inv_pv, inv_grid, inv_load, inv_inv).
3. **Resilience:** point probe at an unreachable address — must time out
   gracefully and still write a valid (empty-blocks) YAML.

### Done when

YAML round-trips cleanly and the AC2A probe output covers all V2 blocks.

---

## Unit 12 — `bluetti-cli validate-profile`

**Depends on:** Unit 11 (uses the YAML format probe emits).
**Scope:** new module + CLI subcommand.

### Goal

Load a draft profile YAML, connect to the device, and report which fields
parse to sane values vs. which look suspect (always-zero, all-0xFFFF, or
out-of-range).

### Files to add

- `src/bluetti_cli/validate.py`
- `tests/test_validate.py`

### Files to modify

- `src/bluetti_cli/cli.py` — add `validate-profile` subcommand.

### Implementation shape

```python
# validate.py
@dataclass
class FieldVerdict:
    name: str
    value: object
    status: Literal["ok", "suspect", "error"]
    note: str = ""


def assess_field(name: str, value, expected_range=None) -> FieldVerdict:
    if value in (0, 0xFFFF, 0xFFFFFFFF):
        return FieldVerdict(name, value, "suspect", "stuck-at value")
    if expected_range and not (expected_range[0] <= value <= expected_range[1]):
        return FieldVerdict(name, value, "suspect", f"out of {expected_range}")
    return FieldVerdict(name, value, "ok")
```

CLI output is a per-block table with an OK/SUSPECT/ERROR count summary.

### Verification

1. **Unit test:** craft synthetic field values, confirm `assess_field`
   returns expected verdicts.
2. **Live AC2A:** run `bluetti-cli validate-profile` against the AC2A's own
   probe output — expect mostly OK for known fields.

### Done when

The AC2A's probe output validates with zero ERROR entries.

---

## Unit 13 — `bluetti-cli annotate` (interactive REPL)

**Depends on:** Unit 11.
**Scope:** new module + CLI subcommand.

### Goal

Live polling that highlights changing register values and prompts the
operator for field names. Saves to a YAML draft incrementally.

### Files to add

- `src/bluetti_cli/annotate.py`
- `tests/test_annotate.py` (annotation-logic tests; UI not tested)

### Files to modify

- `src/bluetti_cli/cli.py` — add `annotate` subcommand.

### Implementation shape

```python
# annotate.py
async def annotate_loop(address: str, profile_path: pathlib.Path,
                       *, encrypted: bool) -> None:
    profile = _load_or_init(profile_path)
    last = {}  # block_addr -> raw bytes
    client = BluetoothClient(address, encrypted=encrypted)
    await client.connect()
    try:
        while True:
            for block in PROBE_BLOCKS:
                resp = await client.execute(...)
                changes = _diff(last.get(block.addr), resp)
                for offset, old, new in changes:
                    name = await _prompt_user(block, offset, old, new)
                    if name:
                        profile.setdefault("annotations", []).append(
                            {"block": block.name, "offset": offset, "name": name}
                        )
                        _save(profile, profile_path)
                last[block.addr] = resp
            await asyncio.sleep(1)
    finally:
        await client.disconnect()
```

Use `click.prompt` for the interactive prompt — cross-platform out of the
box.

### Verification

1. **Unit test:** feed a sequence of raw-bytes snapshots into `_diff`, assert
   it yields the expected `(offset, old, new)` tuples.
2. **Live test (AC2A):** run `bluetti-cli annotate <AC2A_ADDR> -o
   /tmp/draft.yaml`. Toggle the AC switch on the device; verify register 2011
   appears in the change feed. Type `ac_output` at the prompt; confirm
   `/tmp/draft.yaml` updates within ~1s.
3. **Crash safety:** Ctrl-C mid-session — the YAML written so far must be
   valid (load it back with `yaml.safe_load`).

### Done when

Live AC2A annotation produces a correctly-named annotation entry that
survives Ctrl-C.

---

## Unit 14 — btsnoop parser + contributor docs

**Depends on:** Unit 7 (uses `cipher` module if a session key is supplied).
**Scope:** standalone script + new doc + README update.

### Goal

Help contributors capture BLE traffic from the official Android app and turn
it into a register-level Modbus timeline. Then document the end-to-end
contributor workflow.

### Files to add

- `scripts/parse_btsnoop.py` — standalone CLI script (not packaged).
- `docs/CONTRIBUTING_DEVICES.md`.

### Files to modify

- `README.md` — widen Requirements (Linux/macOS 11+/Windows 10 build 19041+),
  link to `CONTRIBUTING_DEVICES.md`, note macOS UUID-vs-MAC quirk.

### Implementation shape

```python
# scripts/parse_btsnoop.py
#!/usr/bin/env python3
"""Parse Android btsnoop_hci.log and extract Bluetti BLE Modbus frames.

Usage:
    python parse_btsnoop.py <btsnoop_hci.log> [--key HEX] [--iv HEX]

Outputs CSV: timestamp, direction, function_code, register, length, value_hex
"""
# Use only stdlib + cryptography (already a dep after Unit 5).
# btsnoop format: 16-byte header + records of (length, ts_us, flags, payload).
# Filter by ATT writes/notifications on Bluetti GATT handles (0xff01/0xff02).
```

`docs/CONTRIBUTING_DEVICES.md` outline:

```
# Contributing a new Bluetti device

## You need
- The device, charged and on
- An Android phone with the official Bluetti app
- adb access (USB debugging enabled)

## Step 1: Probe with bluetti-cli
- bluetti-cli scan
- bluetti-cli probe <ADDR> -o my-device.yaml

## Step 2: Capture official-app traffic
- Enable Developer options + "Enable Bluetooth HCI snoop log"
- Open the Bluetti app, exercise features
- adb bugreport → extract btsnoop_hci.log
- python scripts/parse_btsnoop.py btsnoop_hci.log > capture.csv

## Step 3: Submit
- Open a GitHub issue with my-device.yaml and capture.csv attached
```

### Verification

1. Run `parse_btsnoop.py` against a small known-good capture file (commit one
   under `tests/fixtures/btsnoop/sample.log`, anonymised — strip any real
   serial numbers). Confirm output CSV has expected rows.
2. Render `CONTRIBUTING_DEVICES.md` in a markdown viewer; check links and
   commands.
3. `python -m mdformat README.md` (or any markdown linter) — README parses.

### Done when

A sample btsnoop log produces a non-empty CSV, and the contributor doc walks
end-to-end without referencing internal-only paths.

---

## Final integration checklist (after all units land)

Run before opening the PR:

- [ ] `uv run pytest` — all unit tests pass.
- [ ] `uv run pytest -m integration` — AC2A regression suite passes.
- [ ] `bluetti-cli scan` shows manufacturer-data classification.
- [ ] `bluetti-cli status <AC2A_ADDR>` output identical to pre-refactor.
- [ ] `bluetti-cli probe`, `validate-profile`, `annotate` work against AC2A.
- [ ] At least one non-AC2A device works with `bluetti-cli status` (or the
      handshake-failure diagnostic fires correctly).
- [ ] `grep -rn '"AC2A"' src/` only in `core/devices/ac2a.py` (definition).
- [ ] `README.md` Requirements lists Linux/macOS/Windows.
- [ ] `docs/CONTRIBUTING_DEVICES.md` is published.
- [ ] No code lifted from `bluetti-official/*` repos.
