## 1. Stage-1 framing tests (TDD — write first, confirm they fail)

- [ ] 1.1 Add `tests/test_handshake_framing.py` with the captured vector: challenge `2A2A0104 3D9687E0 023F` → `randomMd5 == "a0ce9adc2c5341f1d271d0518c4e7773"` and reply == `2A2A0204 D271D051 026A` (10 bytes)
- [ ] 1.2 Assert the random value is read from `challenge[4:8]` (`3D 96 87 E0`), not `challenge[3:7]`
- [ ] 1.3 Assert the reply token is the 4 hex-decoded bytes of `randomMd5[16:24]`, and the reply is 10 bytes (not 14)
- [ ] 1.4 Assert the checksum is the big-endian 2-byte sum of `02 04` + the 4 token bytes (`02 6A`)
- [ ] 1.5 Run the suite and confirm these tests fail against current code

## 2. Stage-1 implementation (`handshake.py`)

- [ ] 2.1 Read random from `challenge[4:8]`; collect enough bytes to cover offset 8
- [ ] 2.2 Stop uppercasing the MD5 digest — keep `randomMd5` lowercase (matches APK; needed for stage 2)
- [ ] 2.3 Build the reply token via `bytes.fromhex(randomMd5[16:24])` (4 bytes), not ASCII encoding
- [ ] 2.4 Replace `_checksum` usage in the reply: big-endian 2-byte sum over `02 04` + the 4 token bytes only (exclude `2A 2A`)
- [ ] 2.5 Run stage-1 tests; confirm green

## 3. Stage-2 key & IV tests (TDD)

- [ ] 3.1 Add vectors: legacy session key == `bytes.fromhex(randomMd5) XOR bytes.fromhex(LOCAL_AES_KEY)` (16 bytes) for the captured `randomMd5`
- [ ] 3.2 Add vector: IV == `bytes.fromhex(randomMd5)` == `a0ce9adc2c5341f1d271d0518c4e7773` decoded (16 bytes), not `md5(randomMd5_ascii)`
- [ ] 3.3 Run and confirm these fail against current code

## 4. Stage-2 implementation (`handshake.py`, `cipher.py`)

- [ ] 4.1 Rewrite `derive_legacy_session_key` to byte-wise XOR the decoded `randomMd5` and decoded `LOCAL_AES_KEY` (16 bytes)
- [ ] 4.2 Change `cipher.derive_iv` to return `bytes.fromhex(randomMd5)`; grep for other `derive_iv` callers and confirm the legacy stage is the only one affected
- [ ] 4.3 Run stage-2 tests; confirm green

## 5. Full suite & regression

- [ ] 5.1 Run the entire test suite; confirm no plaintext-device handshake tests regressed and output is pristine
- [ ] 5.2 (When hardware available) capture a fresh BLE trace of the Elite 100 V2 connect and confirm the device now emits the 144-byte ECDH block (no re-issued challenge, no premature disconnect)

## 6. Documentation

- [ ] 6.1 Update `docs/source/protocol/encryption-details.md`: add a "Legacy challenge-response frame format" section — symmetric 10-byte frame `2A 2A <01|02> 04 <4 bytes> <2-byte BE checksum>`, the `0x04` length field, token = hex-decoded `randomMd5[16:24]`, checksum scope (`02 04` + token) and big-endian sum; include the worked test vector
- [ ] 6.2 Update `encryption-details.md` key/IV notes: legacy key = byte-wise XOR of decoded `randomMd5` and decoded `LOCAL_AES_KEY`; IV = decoded `randomMd5` (not a second MD5); note `randomMd5` is lowercase
- [ ] 6.3 Update `docs/source/protocol/security.md` if it restates the handshake, so it agrees with the corrected framing; cross-check `docs/source/protocol/index.md` for stale references
- [ ] 6.4 Confirm docs nav/toctree still builds (no new pages added, but verify the edited pages render)
- [ ] 6.5 Note the stage-2 follow-ups (ECDH signature/case consistency, per-SN key binding) as documented open items so future readers know stage 2 is not yet validated
