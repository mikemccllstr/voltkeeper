## Why

The `fix-v2-handshake-stage2` change fixed the `2A 2A 03` status-ack consumption (validated on a live Elite 100 V2), but stage 2 still cannot complete. A live trace plus the APK source (`ConnectManager.bleEncryptedHandle`, `ProtocolParse.buildAESCBCCmd` / `parseAESCBCData`) reveal three framing facts the prior change guessed at or missed: every encrypted frame carries a 2-byte length prefix before the ciphertext, the ECDSA signature message hex-decodes `randomMd5` (not ASCII), and post-handshake frames embed a fresh per-frame IV seed. Until these are fixed, the ECDH block fails to decrypt, the device signature fails to verify, and no Modbus traffic can be exchanged.

## What Changes

- **Strip/prepend the 2-byte plaintext-length prefix on every encrypted frame.** Inbound: `parseAESCBCData` reads `substring(0,4)` as a `%04X` plaintext byte-length, then decrypts from offset 4. Outbound: `buildAESCBCCmd` emits `%04X` length + ciphertext. Today our code feeds the whole notification (e.g. the 146-byte ECDH block = `00 86` + 144 ciphertext) straight into `decrypt`, causing `Ciphertext length must be a multiple of 16`. This affects the inbound `2A2A04` ECDH block, our outbound `2A2A05` reply, the inbound `2A2A06` confirmation, and all post-handshake Modbus frames.
- **Hex-decode `randomMd5` in the ECDSA signature message** (both verify and sign). The APK signs/verifies over `hexStringToBytes(pubKeyHex + randomMd5Hex)` = 64-byte pubkey + 16-byte digest = 80 bytes. Our code ASCII-encodes the 32-char hex string (96 bytes). Verified against the captured device signature: the 80-byte hex-decoded form verifies against `PUBLIC_KEY_K2`; the 96-byte ASCII form does not. This corrects design D3 of the prior change, which guessed ASCII.
- **Rework the post-handshake frame codec for per-frame IVs.** With `bleConnShareKey` (iv null), `parseAESCBCData`/`buildAESCBCCmd` use `[2-byte len][4-byte random][ciphertext]`, where the CBC IV is `MD5(the 4 random bytes)` — a fresh IV per frame, not a chained or reset IV. This replaces design D4 of the prior change, which framed the question as reset-vs-chained. The handshake stage keeps its existing `[2-byte len][ciphertext]` framing with IV = `randomMd5` bytes, CBC-chained across blocks.
- **Make the state-machine simulator byte-accurate to the APK** so the unit tests exercise the real framing (length prefix, hex-decoded signature message, per-frame post-handshake IV).
- **Docs**: document the 2-byte length prefix, the two encrypted-frame layouts (handshake vs post-handshake), and the corrected signature message in `security.md` / `encryption-details.md`.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `ble-encrypted-handshake`: add requirements for the 2-byte length-prefix on encrypted frames, the hex-decoded ECDSA signature message, and the post-handshake per-frame IV frame layout. The status-ack and ECDH-offset requirements from `fix-v2-handshake-stage2` are unchanged.

## Impact

- Affected specs: `ble-encrypted-handshake`
- Affected code: `src/voltkeeper/bluetooth/handshake.py` (length-prefix strip/prepend on collect/send; hex-decoded signature message in `verify_device_pubkey` / `sign_app_pubkey`), `src/voltkeeper/bluetooth/cipher.py` (post-handshake per-frame IV codec), the encrypted Modbus read/write path that wraps `CbcSession`.
- Affected tests: `tests/test_handshake_state_machine.py` (byte-accurate framing), cipher/codec unit tests.
- Affected docs: `docs/source/protocol/security.md`, `docs/source/protocol/encryption-details.md`.
- **Behavior**: completes the encrypted handshake (`2A2A06` confirmation) and enables the first real Modbus read (`voltkeeper status` → SOC) on encrypted V2 devices. Plaintext devices (AC2A) unaffected.
- **No backward-compatibility concern**: stage 2 has never completed, so there is no working behavior to preserve.
