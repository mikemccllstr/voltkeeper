## Context

`BluetoothClient.connect()` runs an AES-CBC handshake for encrypted devices (`encrypted=True`, advertised prefix `BLUETTE`/`BLUETTF`). The handshake has two stages:

1. **Legacy challenge-response** — the device sends a plaintext challenge; the app proves knowledge of `LOCAL_AES_KEY` by replying with a token derived from the challenge's random bytes. This also establishes the legacy session key (`bleConnAESKey`) and IV used to decrypt stage 2.
2. **ECDH key exchange** — encrypted with the legacy key, the device sends its signed ephemeral public key; the app verifies it, replies with its own signed key, and both derive `bleConnShareKey` for all subsequent Modbus traffic.

`handshake.py` was written from notes, not validated against hardware. A live BLE trace of an Elite 100 V2 (`DC:B4:D9:46:73:96`) shows the device receiving our stage-1 reply, **rejecting** it (re-sending the same challenge six times), then disconnecting after ~5s. The disconnect causes the handshake's `finally: stop_notify()` to run against a dead connection, which is what raises the misleading `Service Discovery has not been performed yet`.

The decompiled APK is the authority for the wire format:
- `connect/ConnectManager.java:1742` `bleEncryptedHandle()` — challenge parse, reply build, key/IV usage.
- `lib_ble/utils/HexUtilKt.java` — `hexStrSum` (checksum), `hexStrXorOther` (key XOR), `intToHexStr` (`%04X`, big-endian, uppercase).
- `lib_mqtt/utils/MD5.java` — `md5Encode` produces a **lowercase** hex digest.
- `connectv2/tools/ConnConstantsV2.java:98` — `LOCAL_AES_KEY`.

## Goals / Non-Goals

**Goals:**
- Make the stage-1 legacy challenge-response reply byte-identical to the APK so an encrypted device accepts it and advances to stage 2.
- Correct the stage-2 legacy session key and IV derivation that stage 2 decryption depends on.
- Lock the framing down with table-driven unit tests built from the captured hardware test vector, so the fix is verifiable without a device.
- Document the corrected frame format in the protocol docs.

**Non-Goals:**
- Stage-2 ECDH signature verification / app-key signing correctness, and the lowercase-vs-uppercase `randomMd5` consistency in the signed message. These are only reachable once stage 1 passes and need their own hardware trace; captured as open questions / follow-up.
- The per-SN key-binding question documented at `client.py:80`.
- Any change to plaintext devices or to the CLI/daemon surface.

## Decisions

### D1: Treat the APK as ground truth; mirror its byte operations exactly

The app builds the reply as a hex **string** (`"2A2A0204" + token + checksum`) and converts the whole thing to bytes at transmit time. That means the 8-hex-char token becomes **4 bytes**, and the `0x04` length field is consistent on both challenge and reply. We will reproduce the same byte-level result in Python rather than approximating.

The four stage-1 corrections in `handshake.py`:

| Step | Current (wrong) | Correct (APK) |
|------|-----------------|---------------|
| random slice | `challenge[3:7]` | `challenge[4:8]` |
| reply token | `randomMd5[16:24].encode("ascii")` (8 B) | `bytes.fromhex(randomMd5[16:24])` (4 B) |
| checksum input | `2A 2A 02 04` + 8 ascii bytes | `02 04` + 4 token bytes |
| checksum endianness | little-endian | big-endian |

Two stage-2 corrections:

| Step | Current (wrong) | Correct (APK) |
|------|-----------------|---------------|
| session key (`derive_legacy_session_key`) | XOR of ASCII codes of hex digits | `xor(bytes.fromhex(randomMd5), bytes.fromhex(LOCAL_AES_KEY))` |
| IV (`cipher.derive_iv`) | `md5(randomMd5_ascii)` | `bytes.fromhex(randomMd5)` |

**Alternative considered:** keep `derive_legacy_session_key` returning the ASCII-XOR for "compatibility." Rejected — it never worked, there is nothing to stay compatible with, and it would keep stage 2 broken.

### D2: `randomMd5` is a lowercase hex string everywhere downstream

`MD5.md5Encode` is lowercase. Today `derive_legacy_session_key` uppercases the digest. Once the token, key, and IV all go through `bytes.fromhex(...)`, the digest's case is irrelevant to those three (hex decode is case-insensitive). We will stop uppercasing so the stored `randomMd5` matches the app exactly, because stage 2's ECDH signed message ASCII-encodes `randomMd5` and case **will** matter there. Keeping it lowercase now avoids planting a stage-2 bug.

### D3: Test with the captured vector, no hardware in the test path

A single real challenge (`2A2A0104 3D9687E0 023F`) yields deterministic outputs (`randomMd5 = a0ce9adc...`, reply `2A2A0204 D271D051 026A`, the key, the IV). Unit tests assert each transformation against these constants. This satisfies the "tests must cover functionality" rule without mocking a BLE device, and gives a regression anchor if anyone "tidies" the framing later.

### D4: Documentation describes the symmetric frame, not just the formula

The current `encryption-details.md` already lists `random_bytes = data[4:8]` in its formula block, but `handshake.py` diverged from it and there is no description of the **frame** (`2A 2A <type> 04 <payload> <BE checksum>`), the `0x04` length field, or the checksum scope/endianness — the exact things that were gotten wrong. We add a frame-format section and the worked test vector so a future reader can validate an implementation by inspection.

## Risks / Trade-offs

- **Stage 1 passes but stage 2 still fails.** → Expected and acceptable: this change's success criterion is that the device stops rejecting/disconnecting and emits the 144-byte ECDH block (visible in a BLE trace). Stage-2 work is a separate, scoped follow-up. The proposal states this explicitly.
- **Test vector encodes a wrong assumption.** → Mitigated by deriving the vector directly from the captured device challenge and the APK algorithm; the buggy code's actual on-wire bytes were reproduced exactly in analysis, confirming our reading of the current code is correct.
- **Hardware not in range at apply time.** → The unit tests are self-contained; final on-device confirmation (BLE trace showing the ECDH block) can be done whenever the Elite 100 V2 is available.
- **Touching `derive_iv` could affect other call sites.** → `derive_iv` is only used by the legacy handshake stage; verify no other caller before changing (grep at implementation time).

## Migration Plan

No data or API migration. Encrypted devices currently cannot connect, so there is no working path to preserve or roll back. Rollback is reverting the commit. Plaintext devices are untouched.

## Open Questions

- Stage 2: does the device's signed ECDH message use the lowercase `randomMd5` ASCII (as the app's MD5 implies)? `verify_device_pubkey` currently assumes uppercase — must be confirmed against a stage-2 trace once stage 1 is unblocked.
- Stage 2 IV chaining: `handshake.py` already flags ambiguity (reset vs. continue) when the key changes to `bleConnShareKey`. Unresolved here; revisit with a real stage-2 transcript.
- Does the per-SN key-binding step (`client.py:80`) actually gate Modbus on this device, or only on some SKUs? Out of scope until stage 2 works.
