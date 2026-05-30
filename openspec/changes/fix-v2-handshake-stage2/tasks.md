## 1. Status-ack handling — tests first (TDD)

- [ ] 1.1 Extend `tests/test_handshake_state_machine.py` so the simulated device sends a `2A 2A 03 01 00` ack frame (built via `_frame(0x03, 0x01, b"\x00")`) between the legacy reply and the encrypted ECDH block
- [ ] 1.2 Assert the full handshake still completes (ack consumed, ECDH block decrypts without a length error)
- [ ] 1.3 Add a test: a `2A 2A 03 01 <non-zero>` ack aborts the handshake with a descriptive error
- [ ] 1.4 Run and confirm 1.2 fails against current code (the ack misaligns `_collect(144)`)

## 2. Status-ack implementation (`handshake.py`)

- [ ] 2.1 After sending the legacy reply, read one notification and validate it is `2A 2A 03 01 <status>`; raise on non-zero status
- [ ] 2.2 Then `_collect(144)` for the ECDH block (ack no longer in the buffer)
- [ ] 2.3 Run ack tests; confirm green

## 3. ECDH parse offsets

- [ ] 3.1 Change `device_pub_raw` to `plaintext[4:68]` and `signature_rs` to `plaintext[68:132]`; remove the stale "[3:67] unvalidated" caveat comment
- [ ] 3.2 Update the state-machine simulator's device-side ECDH message to use `_frame(0x04, 0x80, pubkey + sig)` so app and device agree on the length-framed layout
- [ ] 3.3 Run the state-machine suite; confirm green

## 4. Live hardware validation (device in range)

- [ ] 4.1 Run `env BLEAK_LOGGING=1 uv run voltkeeper status DC:B4:D9:46:73:96 -v`; confirm the ECDH block decrypts and the `2A 2A 04` header is recognized
- [ ] 4.2 Confirm the device ECDSA signature verifies against `PUBLIC_KEY_K2`; if it fails, capture the decrypted message + signed bytes and reconcile case/layout against the APK (design D3)
- [ ] 4.3 Confirm the app `2A 2A 05` reply is accepted and a `2A 2A 06` confirmation arrives
- [ ] 4.4 Confirm a Modbus read returns valid data; if it decrypts to garbage, switch the post-handshake IV from reset to chained and re-test (design D4)
- [ ] 4.5 Confirm `voltkeeper status DC:B4:D9:46:73:96` prints real values (e.g. SOC)

## 5. Regression

- [ ] 5.1 Run the full test suite; confirm no regressions and pristine output
- [ ] 5.2 Confirm plaintext devices (AC2A) are unaffected by re-checking an existing AC2A path or test

## 6. Documentation

- [ ] 6.1 Update `docs/source/protocol/security.md`: document the `2A 2A 03 01 <status>` status-ack frame between the legacy reply and the ECDH block, and that the app consumes it separately
- [ ] 6.2 Update `security.md`/`encryption-details.md` ECDH offsets if needed so they state pubkey `[4:68]` / signature `[68:132]` after the length byte
- [ ] 6.3 Record the resolved post-handshake IV decision (reset vs chained) replacing the CAVEAT in `handshake.py`
- [ ] 6.4 Confirm `mise run docs` still builds
- [ ] 6.5 Note remaining open item: the per-SN key-binding question (`client.py:80`) as a documented follow-up

## 7. Follow-up tracking

- [ ] 7.1 If Modbus is gated by a per-SN key-binding step, capture the observed behavior and open a separate change for it (do not expand this change's scope)
