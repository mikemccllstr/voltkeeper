## 1. Status-ack handling — tests first (TDD)

- [x] 1.1 Extend `tests/test_handshake_state_machine.py` so the simulated device sends a `2A 2A 03 01 00` ack frame (built via `_frame(0x03, 0x01, b"\x00")`) between the legacy reply and the encrypted ECDH block
- [x] 1.2 Assert the full handshake still completes (ack consumed, ECDH block decrypts without a length error)
- [x] 1.3 Add a test: a `2A 2A 03 01 <non-zero>` ack aborts the handshake with a descriptive error
- [x] 1.4 Run and confirm 1.2 fails against current code (the ack misaligns `_collect(144)`)

## 2. Status-ack implementation (`handshake.py`)

- [x] 2.1 After sending the legacy reply, read one notification and validate it is `2A 2A 03 01 <status>`; raise on non-zero status
- [x] 2.2 Then `_collect(144)` for the ECDH block (ack no longer in the buffer)
- [x] 2.3 Run ack tests; confirm green

## 3. ECDH parse offsets

- [x] 3.1 Change `device_pub_raw` to `plaintext[4:68]` and `signature_rs` to `plaintext[68:132]`; remove the stale "[3:67] unvalidated" caveat comment
- [x] 3.2 Update the state-machine simulator's device-side ECDH message to use `_frame(0x04, 0x80, pubkey + sig)` so app and device agree on the length-framed layout
- [x] 3.3 Run the state-machine suite; confirm green

## 4. Regression

- [x] 4.1 Run the full test suite; confirm no regressions and pristine output
- [x] 4.2 Confirm plaintext devices (AC2A) are unaffected by re-checking an existing AC2A path or test

## 5. Documentation

- [x] 5.1 Update `docs/source/protocol/security.md`: document the `2A 2A 03 01 <status>` status-ack frame between the legacy reply and the ECDH block, and that the app consumes it separately
- [x] 5.2 Update `security.md` ECDH offsets so they state pubkey `[4:68]` / signature `[68:132]` after the length byte
- [x] 5.3 Confirm `mise run docs` still builds

## Descoped — moved to `fix-v2-encrypted-frame-codec`

Live hardware validation revealed three further framing facts (2-byte encrypted-frame length
prefix, hex-decoded `randomMd5` in the ECDSA signature message, post-handshake per-frame IV) that
disproved this change's design D3/D4 and block handshake completion. Completing the ECDH exchange
(`2A 2A 05` reply, `2A 2A 06` confirmation, `bleConnShareKey` derivation), the post-handshake IV
decision, the first Modbus read, and the per-SN key-binding follow-up are owned by the
`fix-v2-encrypted-frame-codec` change. This change delivers the status-ack consumption and ECDH
parse offsets only — both confirmed against a live Elite 100 V2 (status-ack consumed cleanly) and
an offline decrypt of the captured ECDH block (offsets correct).
