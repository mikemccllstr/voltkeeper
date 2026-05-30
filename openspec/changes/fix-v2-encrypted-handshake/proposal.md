## Why

Encrypted Bluetti devices (advertising prefix `BLUETTE`/`BLUETTF`, e.g. the Elite 100 V2) cannot connect at all. The legacy challenge-response handshake in `bluetooth/handshake.py` was written from documentation but never validated against real hardware, and it frames the reply wrong in several independent ways. The device rejects our reply, re-issues its challenge, and disconnects after ~5s — which surfaces as a misleading `Error: Service Discovery has not been performed yet` thrown during cleanup. Every command (`verify`, `status`, `set`, daemon, load-test) is blocked on this for any encrypted device.

The decompiled APK (`ConnectManager.bleEncryptedHandle` + `HexUtilKt`) plus a live BLE trace from a real Elite 100 V2 give us ground truth for the exact framing, so we can fix it with certainty rather than guesswork.

## What Changes

- Fix the **stage-1 legacy challenge-response** in `handshake.py` to match the APK byte-for-byte:
  - Read the 4 random bytes from `challenge[4:8]` (skip the `0x04` length field), not `challenge[3:7]`.
  - Build the reply token by **hex-decoding** `randomMd5[16:24]` to 4 bytes, not ASCII-encoding it to 8 bytes.
  - Compute the trailing checksum as a **big-endian** 2-byte sum over **`02 04` + the 4 token bytes only** (not little-endian, not including `2A 2A`).
- Fix the **stage-2 legacy session key + IV** derivation (reached only once stage 1 passes):
  - Derive `bleConnAESKey` as the **byte-wise XOR** of `decode(randomMd5)` and `decode(LOCAL_AES_KEY)` (16 bytes), not by XOR-ing the ASCII codes of hex digits.
  - Derive the CBC IV as `decode(randomMd5)` (the 16-byte digest), not `md5(randomMd5_ascii)`.
- Add a unit test using the captured test vector (challenge `2A2A0104 3D9687E0 023F` → reply `2A2A0204 D271D051 026A`) plus key/IV vectors, so the framing is locked down without hardware.
- Update the protocol docs (`docs/source/protocol/encryption-details.md` and `security.md`) to describe the correct 10-byte symmetric frame format, the `0x04` length field, the checksum rule, and the key/IV derivation — so future readers don't re-derive the wrong layout.

Out of scope (documented as follow-ups, not fixed here): stage-2 ECDH signature/case-consistency validation and the per-SN key-binding question in `client.py:80`. Those are only reachable once stage 1 works and need their own hardware validation.

## Capabilities

### New Capabilities
- `ble-encrypted-handshake`: The AES-CBC encryption handshake performed on connect to encrypted Bluetti devices — the legacy challenge-response frame format, reply construction, and session-key/IV derivation.

### Modified Capabilities
<!-- None: no existing spec covers the BLE encrypted handshake. -->

## Impact

- **Code**: `src/voltkeeper/bluetooth/handshake.py` (challenge parse, reply build, `derive_legacy_session_key`), `src/voltkeeper/bluetooth/cipher.py` (`derive_iv`).
- **Tests**: new handshake framing/key/IV unit tests under `tests/`.
- **Docs**: `docs/source/protocol/encryption-details.md`, `docs/source/protocol/security.md`.
- **Behavior**: unblocks BLE connection for all encrypted devices (Elite 100 V2 confirmed in range). Plaintext devices (e.g. AC2A) are unaffected — they never enter this path.
- **No API/CLI surface changes.** No backward-compatibility concerns: the current code never successfully completed this handshake, so there is no working behavior to preserve.
