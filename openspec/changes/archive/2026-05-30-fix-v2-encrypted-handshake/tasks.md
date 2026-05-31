## 1. Stage-1 framing tests (TDD — write first, confirm they fail)

- [x] 1.1 Add `tests/test_handshake_framing.py` with the captured vector: challenge `2A2A0104 3D9687E0 023F` → `randomMd5 == "a0ce9adc2c5341f1d271d0518c4e7773"` and reply == `2A2A0204 D271D051 026A` (10 bytes)
- [x] 1.2 Assert the random value is read from `challenge[4:8]` (`3D 96 87 E0`), not `challenge[3:7]`
- [x] 1.3 Assert the reply token is the 4 hex-decoded bytes of `randomMd5[16:24]`, and the reply is 10 bytes (not 14)
- [x] 1.4 Assert the checksum is the big-endian 2-byte sum of `02 04` + the 4 token bytes (`02 6A`)
- [x] 1.5 Run the suite and confirm these tests fail against current code

## 2. Stage-1 implementation (`handshake.py`)

- [x] 2.1 Read random from `challenge[4:8]` via `parse_legacy_challenge`
- [x] 2.2 Stop uppercasing the MD5 digest — keep `randomMd5` lowercase (matches APK; needed for stage 2)
- [x] 2.3 Build the reply token via `bytes.fromhex(randomMd5[16:24])` (4 bytes), not ASCII encoding
- [x] 2.4 Replace `_checksum` usage in the reply: big-endian 2-byte sum over `02 04` + the 4 token bytes only (exclude `2A 2A`) — extracted a shared `_frame()` helper; stage-2 reply now uses it too
- [x] 2.5 Run stage-1 tests; confirm green

## 3. Stage-2 key & IV tests (TDD)

- [x] 3.1 Add vectors: legacy session key == `bytes.fromhex(randomMd5) XOR LOCAL_AES_KEY` (16 bytes) for the captured `randomMd5`
- [x] 3.2 Add vector: IV == `bytes.fromhex(randomMd5)` == `a0ce9adc2c5341f1d271d0518c4e7773` decoded (16 bytes), not `md5(randomMd5_ascii)`
- [x] 3.3 Run and confirm these fail against current code

## 4. Stage-2 implementation (`handshake.py`, `cipher.py`)

- [x] 4.1 Rewrite `derive_legacy_session_key` to byte-wise XOR the decoded `randomMd5` and `LOCAL_AES_KEY` (16 bytes; `LOCAL_AES_KEY` is already `bytes`)
- [x] 4.2 Change `cipher.derive_iv` to return `bytes.fromhex(randomMd5)`; confirmed the legacy handshake stage is the only caller
- [x] 4.3 Run stage-2 tests; confirm green

## 5. Full suite & regression

- [x] 5.1 Run the entire test suite; confirm no plaintext-device handshake tests regressed and output is pristine (665 passed). Updated the existing `test_handshake.py`/`test_cipher.py`/`test_handshake_state_machine.py` vectors that encoded the old behavior
- [x] 5.2 Captured a live Elite 100 V2 trace: device challenge `2A2A0104 89CAE040 0278`, our reply `2A2A0204 B4BE4E8F 0255` — **device accepted it** (no re-issued challenge, no device-side disconnect) and sent a `2A 2A 03 01 00` status-ack followed by the 144-byte ECDH block. Stage 1 confirmed working on hardware. (Stage 2 then fails on a new, separate issue — see notes.)

## 6. Documentation

- [x] 6.1 Update `docs/source/protocol/encryption-details.md`: add a "Legacy challenge-response frame format" section — symmetric 10-byte frame `2A 2A <01|02> 04 <4 bytes> <2-byte BE checksum>`, the `0x04` length field, token = hex-decoded `randomMd5[16:24]`, checksum scope (`02 04` + token) and big-endian sum; include the worked test vector
- [x] 6.2 Update `encryption-details.md` key/IV notes: legacy key = byte-wise XOR of decoded `randomMd5` and `LOCAL_AES_KEY`; IV = decoded `randomMd5` (not a second MD5); note `randomMd5` is lowercase
- [x] 6.3 Update `docs/source/protocol/security.md` so it agrees with the corrected framing (challenge/reply frames, hex-decoded token, big-endian checksum, IV = decoded digest); `index.md` had no stale handshake specifics
- [x] 6.4 Confirm docs nav/toctree still builds — `mise run docs` succeeds; edited pages render (pre-existing `index.md` H2 warnings only)
- [x] 6.5 Note the stage-2 follow-ups (ECDH parse offset, signature/case consistency, per-SN key binding) as documented open items — in `design.md` Open Questions and a `handshake.py` code comment at the stage-2 parse

## Notes

- The "Service Discovery has not been performed yet" symptom was a red herring: bleak raised it during `stop_notify()` cleanup after the device disconnected us for the rejected reply. No bleak/service-discovery change was needed.
- Stage 2 (ECDH) remains unvalidated against hardware. While fixing stage-1 framing, the stage-2 reply checksum was corrected to the same proven big-endian-over-body rule via `_frame()`, and the stage-2 device-pubkey parse offset (`[3:67]` vs APK `subList(4,68)`) is flagged in a code comment for the next hardware session.
- NEW stage-2 finding from the live run (next change): after accepting the legacy reply the device sends a `2A 2A 03 01 <status>` ack frame (status `00` = OK; the "status 3" referenced in `client.py:80`) *before* the encrypted ECDH block. `HandshakeSession.run`'s `_collect(144)` swallows that 7-byte ack, so the collected ciphertext is misaligned (151 bytes) and decryption raises `Ciphertext length must be a multiple of 16`. Stage 2 needs to consume/skip the `2A 2A 03` ack before collecting the 144-byte block. Track in a follow-up change together with the parse-offset and signature/case items.
