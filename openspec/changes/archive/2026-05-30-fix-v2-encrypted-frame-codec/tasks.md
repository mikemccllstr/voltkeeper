## 1. Length-prefix codec — tests first (TDD)

- [x] 1.1 Add a cipher/codec test: encode a plaintext as `[%04X len][ciphertext]` and decode it back, asserting the decoded output is trimmed to exactly `len` bytes (padding discarded)
- [x] 1.2 Add a test using the captured 146-byte ECDH block (`00 86` + 144 bytes) with the captured key/IV, asserting it decodes to a `2a2a0480…` plaintext of 134 bytes
- [x] 1.3 Run and confirm 1.2 fails against current code (no prefix handling)

## 2. Length-prefix codec implementation

- [x] 2.1 Add an inbound decode helper: read the 2-byte BE length, collect `ceil(len/16)*16` ciphertext bytes, decrypt, trim to `len`
- [x] 2.2 Add an outbound encode helper: prepend `len.to_bytes(2,"big")` to the ciphertext
- [x] 2.3 Replace the fixed `_collect(144)` ECDH read in `handshake.py` with the prefix-aware decode; prepend the prefix on the outbound `2A2A05` reply
- [x] 2.4 Run codec tests; confirm green

## 3. Hex-decoded signature message

- [x] 3.1 Add a test that the captured device signature verifies against `PUBLIC_KEY_K2` over `(pubkey || bytes.fromhex(randomMd5))` (80 bytes) and fails over the ASCII form (96 bytes)
- [x] 3.2 Change `verify_device_pubkey` and `sign_app_pubkey` to use `bytes.fromhex(random_md5_hex)` instead of `random_md5_hex.encode("ascii")`
- [x] 3.3 Run signature tests; confirm green

## 4. Post-handshake per-frame IV codec — tests first (TDD)

- [x] 4.1 Add a test for the post-handshake layout `[len][4B seed][ciphertext]` with IV = `MD5(seed)`: round-trip encrypt/decrypt with an injected seed, asserting trimmed plaintext matches
- [x] 4.2 Add a test that the post-handshake decode rejects/ignores a wrong layout cleanly (no silent mis-decrypt)
- [x] 4.3 Run and confirm 4.1 fails against current code

## 5. Post-handshake codec implementation

- [x] 5.1 Implement the post-handshake encode/decode: generate 4 random seed bytes (injectable source), IV = `MD5(seed)`, frame `[len][seed][ciphertext]`
- [x] 5.2 Wire the post-handshake codec into the encrypted Modbus read/write path that wraps the session returned by the handshake
- [x] 5.3 Run codec tests; confirm green

## 6. Byte-accurate state-machine simulator

- [x] 6.1 Update the device-side simulator to prepend the `%04X` length prefix on encrypted handshake frames
- [x] 6.2 Sign the device ECDH message with the hex-decoded message; drop the `verify_device_pubkey` mock in the full-handshake test now that the real signature verifies
- [x] 6.3 Add a post-handshake round-trip through the simulator using the `[len][seed][ciphertext]` layout
- [x] 6.4 Run the state-machine suite; confirm green

## 7. Live hardware validation (device in range)

- [x] 7.1 Run `env BLEAK_LOGGING=1 uv run voltkeeper status DC:B4:D9:46:73:96 -v`; confirm the ECDH block decrypts and the `2A2A04` header is recognized
- [x] 7.2 Confirm the device ECDSA signature verifies against `PUBLIC_KEY_K2`
- [x] 7.3 Confirm the app `2A2A05` reply is accepted and a `2A2A06` confirmation arrives
- [ ] 7.4 Confirm a Modbus read returns valid data via the post-handshake codec
- [ ] 7.5 Confirm `voltkeeper status DC:B4:D9:46:73:96` prints real values (e.g. SOC)

## 8. Regression

- [x] 8.1 Run the full test suite; confirm no regressions and pristine output
- [x] 8.2 Confirm plaintext devices (AC2A) are unaffected by re-checking an existing AC2A path or test

## 9. Documentation

- [x] 9.1 Update `security.md`: document the 2-byte length prefix and the two frame layouts (handshake `[len][ct]` vs post-handshake `[len][seed][ct]`, IV = `MD5(seed)`)
- [x] 9.2 Update `security.md`/`encryption-details.md`: correct the ECDSA signature message to `(pubkey || hex_decode(randomMd5))`, 80 bytes
- [x] 9.3 Confirm `mise run docs` still builds

## 10. Follow-up tracking

- [x] 10.1 If Modbus is gated by a per-SN key-binding step (clean `2A2A06` then Modbus timeout/exception), capture the behavior and open a separate change (do not expand this change's scope)

After `2A2A06` the device sends a NEW `2A2A01` challenge instead of responding to the first Modbus command, indicating a second authentication round is required (per-SN key-binding). Opened as a separate change `fix-v2-per-sn-key-binding` (TODO — open after archiving this change).
