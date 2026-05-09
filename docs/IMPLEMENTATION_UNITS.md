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

## Tooling constraints

Every commit is gated on `mise run check` (lint + typecheck + tests). Your
work is not done until that passes:

- **Lint** — `mise run lint` → `uv run ruff check src/ tests/`. Rules:
  `E, F, W, I`.
- **Format** — `mise run format` → `uv run ruff format src/ tests/`.
  `line-length = 120`. **The pre-commit hook runs this on every commit and
  will reformat lines in files you've touched.** Expect "out-of-scope"
  reflows in `git diff` for any file you edit (joining short multi-line
  statements onto one line, etc.). These are non-functional and expected. Do
  *not* try to scope your edits to keep the diff small — let the formatter
  do its job.
- **Typecheck** — `mise run typecheck` → `uv run mypy src/bluetti_cli`.
  Config: `check_untyped_defs = true`, `no_implicit_optional = true`. Type
  new code properly; don't reach for `# type: ignore` to make a problem go
  away.
- **Tests** — `mise run test` → `uv run pytest`.

Test imports use `from src.bluetti_cli...` (not `from bluetti_cli...`) —
match the existing convention in `tests/test_bluetti_cli.py`.

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
                     └── Unit 7  (encrypted-client plumbing) — depends on 5+6
                              ├── Unit 7b (handshake state machine) — depends on 7
                              ├── Unit 8  (V2 base) ── Unit 10 (per-model V2)
                              └── Unit 9  (V1 base) ── Unit 10 (per-model V1)

Unit 11 (probe)         — depends on Units 4, 7, 8, 9 (Unit 7b for encrypted devices)
Unit 12 (validate)      — depends on Unit 11
Unit 13 (annotate)      — depends on Unit 11
Unit 14 (btsnoop + docs)— depends on Unit 7 (for cipher reference); else free
```

Units 5 and 6 can run in parallel. Units 8 and 9 can run in parallel after
Unit 4. Per-model classes within Unit 10 can run in parallel once 8 and 9 land.
Unit 7b can run in parallel with Units 8/9/10 — it touches `handshake.py` and
`client.py`, neither of which Units 8–10 modify.

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

- `mise run check` is green (lint, typecheck, all tests).
- `tests/test_bluetooth_init.py::test_build_device_rejects_unknown` passes.

---

## Unit 2 — Decouple AC2A literals from CLI and MQTT layers

**Depends on:** Unit 1.
**Scope:** ~80 lines across 3 files plus tests.

### Goal

After Unit 1 and the earlier "bug 1c" quality fix (commit `7a54ab9`), exactly
one functional AC2A literal and two direct AC2A class references remain in
upper layers:

```
$ grep -rn '"AC2A"\|AC2A\.' src/
src/bluetti_cli/cli.py:929    device_type = "AC2A"                            ← target
src/bluetti_cli/cli.py:456    caps = AC2A.decode_ctrl_event(ctrl_event)       ← target
src/bluetti_cli/cli.py:460    for name, _ in AC2A.CTRL_EVENT_BITS:            ← target
```

(Line numbers may drift slightly after format reflows. The harmless mentions
in `bluetooth/__init__.py:85` registry and `core/devices/ac2a.py:54`
constructor are definition sites and stay.)

Move all three behind device-class methods so other models can opt in.

### Special case: `cli.py:929` — `mqtt-listen --serial` without ADDRESS

The `mqtt-listen` command accepts ADDRESS, `--serial`, or both. When ADDRESS
is provided we can scan and resolve the device class. When only `--serial` is
provided (the latched-shutdown deployment use case), we have no scan and
therefore no auto-detection. The current code defaults the topic to `"AC2A"`,
which silently breaks for any other model.

Required change: add a `--device-type` Click option (default `None`).
Resolution order in the command body:

1. If `address` is set → resolve via `build_device(...).type` (existing
   path).
2. Else if `--device-type` is set → use it verbatim, but validate against
   the registry (raise `click.BadParameter` for unknown values).
3. Else (only `--serial`, no `--device-type`) → raise `click.UsageError`
   instructing the user to pass `--device-type` so the MQTT topic stays
   correct. Do *not* fall back to AC2A silently — that would re-introduce
   the original bug.

### Files to modify

- `src/bluetti_cli/core/devices/bluetti_device.py` — add an optional
  `decode_ctrl_event` method and a `ctrl_event_bits` property with `None`
  / empty-list defaults.
- `src/bluetti_cli/core/devices/ac2a.py` — port the existing
  `@classmethod decode_ctrl_event` to an instance method and expose
  `CTRL_EVENT_BITS` via the `ctrl_event_bits` property.
- `src/bluetti_cli/cli.py`:
  - The verbose status block (currently around lines 454–460): replace the
    inline `from .core.devices.ac2a import AC2A` plus
    `AC2A.decode_ctrl_event(...)` / `AC2A.CTRL_EVENT_BITS` with
    `device.decode_ctrl_event(ctrl_event)` and iteration over
    `device.ctrl_event_bits`.
  - `mqtt_listen` (currently around line 929): add the `--device-type`
    option, replace the `device_type = "AC2A"` literal with the
    resolution logic above.
- `src/bluetti_cli/bluetooth/__init__.py` — promote `_device_registry()`
  to a public name (e.g. `device_registry()`) or add a small public helper
  `is_supported_device_type(prefix: str) -> bool`. Pick whichever feels
  less intrusive; the CLI needs a way to validate `--device-type`.
- `src/bluetti_cli/mqtt_client.py` — final audit. Should already be
  model-agnostic post-bug-1c; verify with `grep '"AC2A"'`.

### Implementation shape

In `bluetti_device.py`:

```python
class BluettiDevice:
    # ... existing code ...

    # Optional capability hook. Subclasses that expose a ctrl-event bitmask
    # should override and return {bit_name: bool}. Default: None means
    # "device does not expose ctrl events" — caller should skip the section.
    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool] | None:
        return None

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        return []
```

In `ac2a.py`:

```python
class AC2A(...):
    CTRL_EVENT_BITS = [...]  # keep the constant

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        return self.CTRL_EVENT_BITS

    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool]:
        # body unchanged from current @classmethod implementation;
        # just drop @classmethod and `cls` -> `self`.
        ...
```

In `cli.py` (verbose status block):

```python
caps = device.decode_ctrl_event(ctrl_event)
if caps is None:
    return  # device does not expose ctrl events; skip the block
for name, label in device.ctrl_event_bits:
    ...
```

In `cli.py` (mqtt_listen — Click option + body):

```python
@click.option(
    "--device-type",
    type=str,
    default=None,
    help="Device model (e.g. AC2A). Required when --serial is given without ADDRESS.",
)
def mqtt_listen(..., device_type, ...):
    ...
    if address:
        _device = build_device(address, lookup_device_name(address))
        device_type_resolved = _device.type
        sn = _device.sn
    elif device_type:
        if not is_supported_device_type(device_type):
            raise click.BadParameter(
                f"Unknown device type {device_type!r}. "
                f"Known: {sorted(device_registry())}"
            )
        device_type_resolved = device_type
    else:
        raise click.UsageError(
            "When ADDRESS is omitted, pass --device-type so the MQTT topic "
            "is correct (e.g. --device-type AC2A)."
        )
```

### Verification

1. `mise run check` — green.
2. `grep -rn '"AC2A"' src/` matches only at:
   - `src/bluetti_cli/bluetooth/__init__.py` (registry definition)
   - `src/bluetti_cli/core/devices/ac2a.py` (`super().__init__(..., "AC2A", ...)` in constructor)
3. `grep -rn "AC2A\." src/bluetti_cli/cli.py` returns no matches (no direct
   class access — must go through `device.<method>`).
4. **New tests** in `tests/test_bluetti_cli.py` (or a new file):
   - `test_mqtt_listen_requires_device_type_when_no_address` — invoke `cli`
     with `mqtt-listen --serial 1234`, assert `UsageError` fires.
   - `test_mqtt_listen_validates_device_type` — pass `--device-type INVALID`,
     assert `BadParameter`.
   - `test_mqtt_listen_uses_explicit_device_type` — pass
     `--serial 1234 --device-type AC2A`, assert the resolved topic prefix
     contains `AC2A`.
   - `test_decode_ctrl_event_default_returns_none` — instantiate the base
     class (or a minimal subclass), assert `decode_ctrl_event(0)` is `None`.
5. Manual: `bluetti-cli status -v <AC2A_ADDR>` — capabilities block looks
   identical to before.
6. Manual: `bluetti-cli mqtt-publish <AC2A_ADDR> --broker localhost` —
   published topic prefix is `bluetti/state/AC2A-<sn>/...` (unchanged).

### Done when

- All four new unit tests pass.
- `grep` checks in steps 2 and 3 above are clean.
- AC2A regression: verbose status block and MQTT topics unchanged.

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

### Padding contract — read this before writing the code

`encrypt()` zero-pads the plaintext to a 16-byte boundary. `decrypt()` returns
**the full block-aligned plaintext including any padding bytes** — it must
*not* `rstrip(b"\x00")` or otherwise try to remove padding. The Bluetti
protocol carries plaintext bytes that legitimately end in `0x00`:

- Modbus register values < 256 → high byte is `0x00`.
- Modbus CRC-16 high bytes are `0x00` for ~0.4% of frames.
- ECDSA signature and sum-checksum bytes can be `0x00`.

The upper layer (Modbus parser, handshake state machine) determines the
actual payload length from protocol-level fields and ignores trailing pad
bytes. Stripping nulls in `decrypt()` would silently corrupt these payloads.

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
    """Returns full block-aligned plaintext. Caller handles framing/padding."""
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

1. `tests/test_cipher.py` — four required tests:
   - **Roundtrip (aligned):** for plaintext sizes that are exact multiples of
     16 (16, 32, 64, 256), `decrypt(encrypt(pt))` returns `pt` unchanged.
   - **Padding is zero-extension, not strip** (regression test): for `pt =
     b"hi"` (2 bytes), `decrypt(encrypt(pt))` returns `pt + b"\x00" * 14` —
     full 16 bytes, with the padding visible. **And** for an aligned 16-byte
     plaintext that ends in `0x00` (e.g. `b"\x01\x03\x02\x12\x34\x00" +
     b"\x00" * 10`), the round-trip preserves every trailing null.
   - **IV derivation:** assert `derive_iv("abc")` equals
     `hashlib.md5(b"abc").digest()` — sanity check that the function reads
     the *string* of hex chars, not raw bytes.
   - **Chained IV:** create `CbcSession`, encrypt three messages, assert that
     decrypting in-order recovers the originals; assert that re-decrypting the
     first message fails to round-trip (because IV state has advanced).
2. `uv run pytest tests/test_cipher.py -v`.
3. `uv pip list | grep cryptography` — confirms dep installed.

### Done when

All four tests pass, and `pyproject.toml` declares the new dep with no upper
bound (e.g., `"cryptography>=42"`). `decrypt()` does **not** strip trailing
nulls.

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

> **Important:** `cipher.decrypt()` returns the full block-aligned plaintext
> *including zero-pad bytes* (Unit 5 padding contract). Slice the decrypted
> buffer by **known offsets from the start** (`[4:68]`, `[68:132]`,
> `[132:134]`) — do NOT use `[-2:]` to grab the checksum, because the last 2
> bytes of the buffer may be padding rather than the actual checksum. The
> intended plaintext length is fixed at 134 bytes (`4` header + `64` pubkey
> + `64` sig + `2` checksum); the ciphertext on the wire is 144 bytes (9
> blocks).

1. Receive `2A 2A 04 ...` AES-CBC encrypted with `bleConnAESKey` and IV
   `derive_iv(randomMd5_hex)`.
2. After decrypt (first 134 bytes of the padded plaintext): bytes `[4:68]` =
   device public key (raw 64-byte uncompressed point, no `0x04` prefix);
   `[68:132]` = ECDSA signature `r||s` (64 bytes); `[132:134]` = sum-checksum.
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
every Modbus frame with `CbcSession`. Plumb the `encrypted` flag from scan
results all the way through to `BluetoothClient` construction.

### Plumbing the encrypted flag (read this first)

Unit 3 introduced `ScanResult(address, name, encrypted)` but two existing APIs
**discard the encrypted field on the floor**:

- `pick_address_after_scan() -> tuple[str, str]` (`bluetooth/__init__.py:80`)
  drops `encrypted` when extracting `(sr.address, sr.name)`.
- `lookup_device_name(address) -> str` (`bluetooth/__init__.py:38`) only
  returns the name string — it scans but never reports the manufacturer-data
  classification.

Two API changes are required as part of Unit 7:

1. **Change `pick_address_after_scan` to return `ScanResult`.** One internal
   call site at `cli.py:139` (the `status` command's interactive scan path).
   Update that caller to unpack `sr.address`, `sr.name`, `sr.encrypted`.

2. **Replace `lookup_device_name` with `lookup_scan_result`.** New signature:

   ```python
   async def lookup_scan_result(address: str, timeout: float = 5.0) -> ScanResult:
       """Scan briefly for a specific address; return its ScanResult.

       If the address is found, the returned ScanResult carries name +
       encrypted classification. If not found (timed out), returns a
       ScanResult with name == address and encrypted=None — caller should
       decide how to proceed (default to plaintext or error out).
       """
   ```

   Then update every existing call site of `lookup_device_name` in `cli.py`
   (six of them — `grep -n 'lookup_device_name' src/`) to use
   `lookup_scan_result` and pass `encrypted=sr.encrypted or False` into
   `BluetoothClient`. **All commands that take an ADDRESS argument need
   updating**: `status`, `write`, `mqtt-publish`, `mqtt-listen`,
   `load-test`. Plus any helpers in `device_handler.py`.

Default-to-plaintext when `encrypted is None`: this preserves AC2A behaviour
when the manufacturer data wasn't observed (e.g., the device was already
connected by the OS or the scan timed out). The plaintext path will fail
loudly with a CRC error against an actually-encrypted device, which is the
right signal for the user to re-run after disconnecting other clients.

### Files to modify

- `src/bluetti_cli/bluetooth/__init__.py`:
  - Change `pick_address_after_scan() -> ScanResult`.
  - Replace `lookup_device_name(address) -> str` with
    `lookup_scan_result(address) -> ScanResult`.
- `src/bluetti_cli/bluetooth/client.py` — accept `encrypted: bool = False`,
  run handshake on connect, wrap `execute()` I/O in cipher.
- `src/bluetti_cli/cli.py` — every `BluetoothClient(address)` constructor
  gets an `encrypted=` kwarg derived from the scan result; every
  `lookup_device_name` call replaced with `lookup_scan_result`.
- `src/bluetti_cli/device_handler.py` — same plumbing for any
  `BluetoothClient(...)` it owns.

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

Caller pattern (in every command that takes ADDRESS):

```python
sr = loop.run_until_complete(lookup_scan_result(address))
device = build_device(address, sr.name)
client = BluetoothClient(address, encrypted=bool(sr.encrypted))
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
2. **Unit test for plumbing:** `test_lookup_scan_result_returns_encryption_flag`
   — mock `BleakScanner.discover` to return an advertisement with
   `PREFIX_ENCRYPTED[0]` manufacturer data; assert returned `ScanResult` has
   `encrypted is True`. Same for plaintext and unknown.
3. **Unit test for default-to-plaintext:** `test_pick_address_returns_scanresult`
   — verify `pick_address_after_scan` returns a `ScanResult`, not a tuple.
4. **Regression:** `uv run pytest -m integration` against an AC2A — `status`,
   `write ac_output on/off`, and `mqtt-publish` still all work (plaintext
   path unchanged).
5. **Manual encrypted test:** if an encrypted device is reachable, run
   `bluetti-cli scan` (sees `[encrypted]`), then `bluetti-cli status <ADDR>` —
   expect either a populated reading or the SN-validation diagnostic above.

### Done when

- AC2A behaviour identical (regression suite green).
- `pick_address_after_scan` returns `ScanResult`.
- `lookup_device_name` is gone; `lookup_scan_result` is the single source of
  per-address scan info.
- Every `BluetoothClient(...)` construction in `src/` passes an explicit
  `encrypted=` keyword.
- `BluetoothClient.execute()` validates CRC on the **decrypted** Modbus
  frame, not just the plaintext path.
- The SN-validation `BadConnectionError` fires when CRC fails persistently
  on a session-active client.
- No reference to `AC2A` remains in `client.py`.

The encrypted *connect-and-read* path (`HandshakeSession.run` body) is
deferred to **Unit 7b** below — Unit 7 here covers structural plumbing and
post-decrypt validation only.

---

## Unit 7b — Implement `HandshakeSession.run` (BLE state machine)

**Depends on:** Units 5, 6, 7.
**Scope:** new BLE-driving body on `HandshakeSession`, plus a unit test that
mocks `BleakClient` end-to-end.

### Goal

Unit 6 stubbed `HandshakeSession.run` to `raise NotImplementedError`. Unit 7
wired the call site (`BluetoothClient.connect()` calls
`HandshakeSession().run(self.client)` when `encrypted=True`). This unit
implements the actual state machine over an active `BleakClient`.

### What's already in place

- Pure crypto helpers: `derive_legacy_session_key`, `verify_device_pubkey`,
  `sign_app_pubkey`, `derive_shared_key` (Unit 6).
- Cipher session class: `CbcSession`, `derive_iv` (Unit 5).
- GATT UUIDs: `WRITE_UUID`, `NOTIFY_UUID` (Unit 4).
- The Bluetti protocol bytes per FINDINGS §15.2 step 3 are documented in
  the Unit 6 "Path 1 / Path 2" section above — re-read them.

### State machine to implement

```python
class HandshakeSession:
    async def run(self, client: BleakClient) -> CbcSession:
        # 1. Subscribe to NOTIFY_UUID with a queue-style notification
        #    handler so `await self._next_notification(...)` blocks until
        #    the next inbound frame, regardless of whether the BluetoothClient's
        #    own _on_notification has been wired yet. (This handshake runs
        #    BEFORE the main client.start_notify hook becomes useful.)

        # 2. Path 1 — legacy challenge-response:
        #    - Read the next notification → expect `2A 2A 01` + 4 random bytes.
        #    - randomMd5_hex, ble_conn_aes_key = derive_legacy_session_key(random_bytes)
        #    - Build reply: `2A 2A 02 04` + ASCII bytes of randomMd5_hex[16:24]
        #      + sum-checksum (2 bytes, little-endian, of preceding 8 bytes).
        #    - write_gatt_char(WRITE_UUID, reply, response=False)

        # 3. Path 2 — ECDH:
        #    - Read next notification(s); concatenate until 144 bytes (9 blocks).
        #    - decrypt(buf, ble_conn_aes_key, derive_iv(randomMd5_hex))
        #    - Slice [4:68] → device pubkey, [68:132] → signature.
        #    - verify_device_pubkey(...)
        #    - Generate ephemeral SECP256R1 keypair.
        #    - app_pub_raw = uncompressed-point bytes of the ephemeral pubkey
        #      (drop the leading 0x04 to match the device's format).
        #    - signature = sign_app_pubkey(app_pub_raw, randomMd5_hex)
        #    - reply = `2A 2A 05 80` + app_pub_raw + signature + sum-checksum
        #    - encrypt with ble_conn_aes_key + chained IV
        #    - write_gatt_char(WRITE_UUID, reply, response=False)
        #    - Read next notification → expect `2A 2A 06 00 ...` confirmation
        #      (decrypted with ble_conn_aes_key + chained IV).

        # 4. shared_key = derive_shared_key(app_priv, device_pub)
        #    return CbcSession(shared_key, derive_iv(randomMd5_hex))
```

### Implementation notes

- **Notification capture during handshake:** The handshake needs to read
  notifications BEFORE `BluetoothClient` has set up its own polling
  notification handler (`_on_notification` is for Modbus frames, not
  handshake frames). Two clean approaches:
  1. Have `BluetoothClient.connect()` call `start_notify` with a
     handshake-aware handler that demultiplexes the first few frames to
     the `HandshakeSession`, then hands off to `_on_notification`.
  2. Or, simpler: `HandshakeSession.run()` calls
     `await client.start_notify(NOTIFY_UUID, self._handler)` itself, then
     `await client.stop_notify(NOTIFY_UUID)` before returning so
     `BluetoothClient.connect()` can re-subscribe its own handler.
  
  Option (2) is cleaner — it keeps the handshake self-contained. Update
  `BluetoothClient.connect()` so the order becomes:
  ```python
  await self.client.connect(timeout=timeout)
  if self.encrypted:
      self._session = await HandshakeSession().run(self.client)
  await self.client.start_notify(NOTIFY_UUID, self._on_notification)
  ```

- **Sum-checksum:** the spec says "2-byte little-endian sum-checksum of
  preceding bytes." That's the unsigned sum of all preceding bytes, modulo
  `0x10000`, packed little-endian. Validate by computing it on outgoing
  frames and asserting incoming `2A 2A 06 ...` confirmation passes the
  same check.

- **Frame fragmentation:** BLE notifications are MTU-bounded (~20 bytes
  default; up to 244 with extended MTU). The 144-byte ECDH response will
  arrive across multiple notifications. Concatenate until you have at
  least the expected length; do not assume one notification = one frame.

### Files to modify

- `src/bluetti_cli/bluetooth/handshake.py` — replace
  `HandshakeSession.run`'s `NotImplementedError` body with the state
  machine. Keep the pure helpers untouched.
- `src/bluetti_cli/bluetooth/client.py` — re-order `connect()` per the
  notification-capture note above. No other changes.

### Verification

1. **Unit test:** `tests/test_handshake_state_machine.py` —
   `test_handshake_session_run_against_mock_client`:
   - Construct a `MagicMock` `BleakClient`.
   - Pre-script the notification stream with bytes captured from a real
     handshake (or, lacking that, bytes generated by a fake "device side"
     that uses the same crypto helpers in reverse — i.e., a pure-Python
     simulator of the device end of the handshake).
   - Drive `HandshakeSession().run(mock_client)`.
   - Assert: returns a `CbcSession`, the session's key length is 16,
     the mock received the expected number of `write_gatt_char` calls
     with the expected first-bytes (`2A 2A 02` then `2A 2A 05`).
2. **Unit test:** `test_handshake_rejects_invalid_device_signature` —
   pre-script the device pubkey with a bad signature; assert
   `HandshakeSession().run` raises `ValueError` (from
   `verify_device_pubkey`).
3. **Unit test:** `test_bluetoothclient_connect_runs_handshake_when_encrypted`
   — mock `BleakClient` + `HandshakeSession`; verify `connect()` calls
   the handshake exactly when `encrypted=True`.
4. **Manual encrypted test (hardware):** if an encrypted device is
   reachable, run `bluetti-cli status <ADDR>` and confirm a populated
   reading — OR confirm the SN-validation diagnostic fires (per Unit 7).

### Done when

- `HandshakeSession.run` no longer raises `NotImplementedError`.
- The three unit tests above pass.
- AC2A regression suite still green (`uv run pytest`).
- A `bluetti-cli status` against an encrypted device either succeeds or
  fails with the SN-validation diagnostic — no opaque tracebacks.

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

### Mirror the V2Base writable-field design

After Unit 8's follow-up, V2Base provides default `has_field`,
`has_field_setter`, and `build_setter_command` plus a default empty
`self.control_struct`. V1Base should do the same so V1 device classes in
Unit 10 stay short:

- V1Base.__init__ creates `self.control_struct = DeviceStruct()` (empty
  default) and the V1 read-only struct(s).
- V1Base.parse() dispatches the V1 control range (3000–3090) to
  `self.control_struct`.
- V1Base.WRITABLE_FIELD_NAMES = [] (subclasses override).
- V1Base provides default has_field/has_field_setter/build_setter_command
  iterating over `self._all_polling_structs()` (returning the V1 read-only
  struct(s) plus `control_struct`).

Subclasses (Unit 10) only need to define `WRITABLE_FIELD_NAMES` and a
`_build_control_struct(self)` method called from their `__init__`.

### V1 + BLE encryption — extra investigation

Unit 7b's `HandshakeSession.run` always proceeds to Path 2 (ECDH) after Path 1.
Per FINDINGS §15.2 step 3b, ECDH is **V2+ only**. If a V1 device sets
`isBLEEncrypted == true` (or `isESP32Encrypted == true`), the current state
machine will hang at `_collect(144)` waiting for an ECDH frame the device
never sends.

Before/while writing `v1_base.py`, do the following:

1. **Research:** grep `docs/FINDINGS.md` (and the decompiled APK metadata
   under `apk_decompiled/`) for any V1 model (`protocolVer < 2000`) where
   `isBLEEncrypted` or `isESP32Encrypted` is true. The encryption-flag
   thresholds in §15.4 are the primary source.
2. **If no V1-encrypted model exists:** add a one-line claim to the top of
   `v1_base.py` ("V1 devices are always plaintext per FINDINGS §15.4 as of
   APK 3.0.8") and call it out in `tests/test_v1_base.py` so future device
   classes can rely on the assumption.
3. **If at least one V1-encrypted model exists:** extend
   `HandshakeSession.run` with a `skip_ecdh: bool = False` parameter (or a
   second method `run_legacy_only`). When set, return
   `CbcSession(ble_conn_aes_key, initial_iv)` immediately after Path 1
   completes. Plumb the flag from the per-model class (V1-encrypted models
   pass `skip_ecdh=True` when constructing the handshake) — do **not**
   plumb it through `BluetoothClient`'s public API; keep it internal.
   Add a unit test that drives the V1-encrypted path end-to-end with a
   mock device that only does Path 1.

### Verification

1. **Synthetic input fixture:** craft a 220-byte hex blob simulating a known
   V1 device's `BASE_REAL_DATA` response (ASCII model name in bytes 0–11,
   protocolVer=1018, batterySOC=75 at offset 66–67, etc.).
2. **Parse test:** assert `V1Base().parse(10, fixture)` returns
   `{"deviceModel": "EB3A", "protocolVer": 1018, "batterySOC": 75, ...}`.
3. `uv run pytest tests/test_v1_base.py -v`.
4. **V1-encryption claim:** either the documentation note (case 2 above)
   or the new `skip_ecdh` test (case 3 above) is in place.

### Done when

The synthetic-fixture test parses every documented field from FINDINGS §15.6,
**and** the V1-encryption question above is resolved (either documented away
or implemented).

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

A vanilla read-only V2 model is essentially empty after Unit 8's follow-up:

```python
from .v2_base import V2Base


class EP600(V2Base):
    """EP600 home power station. V2 protocol, high-voltage pack (÷10)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP600", sn)
        # EP600 uses the V2 default ÷10 voltage scale; no override needed.

    # If/when probe data shows EP600-specific quirks, add overrides here.
```

A V2 model **with** writable controls (e.g., AC300) is roughly:

```python
from enum import Enum, unique

from ..struct import DeviceStruct
from .v2_base import V2Base


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


class AC300(V2Base):
    WRITABLE_FIELD_NAMES = [
        "ac_output", "dc_output", "charging_mode", ...
    ]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC300", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ac_output", 2011)
        s.add_enum_field("charging_mode", 2020, ChargingMode)
        # ...
```

V2Base inherits all the heavy lifting (`parse`, `polling_commands`, `has_field`,
`has_field_setter`, `build_setter_command`). Subclasses only need
`WRITABLE_FIELD_NAMES` + `_build_control_struct` for writable fields, plus any
model-specific `_fill_*` array helpers in an overridden `parse()`.

For each model, leave a `# TODO(<model>): verify against hardware` comment at
the top until a maintainer has confirmed `bluetti-cli status` works.

### V1 model classes — alarm/fault decoding

V1Base intentionally leaves `alarmInfo` (BASE_REAL_DATA registers 54-57, 4×
16-bit) and `faultInfo` (registers 58-64, 7× 16-bit) unparsed because the
bit-to-name map differs per device class. V1 model classes (EB3A, AC60) should
add an `_fill_alarms` helper invoked from their overridden `parse()` that
decodes these bitmasks using the FINDINGS §15.6 fault-name tables:

- **Low-power devices** (EB3A, AC60): `lowPowerWarnNames` + `lowPowerFaultNames`
- **High-power inverters** (none in the V1 subset, but document the mapping for
  future contributors): `highPowerWarnNames` + `highPowerFaultNames`
- **Battery packs**: `packHighVoltAlarmNames`, `packHighVoltErrorNames`,
  `bmuWarnNames` (only relevant if the model exposes BMS_PACK at register 91)

The helper reads register pairs from the BASE_REAL_DATA blob, walks set bits,
and emits keys like `alarm.<name>: True` / `fault.<name>: True` so the CLI
display surface treats them the same as any other parsed field.

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
