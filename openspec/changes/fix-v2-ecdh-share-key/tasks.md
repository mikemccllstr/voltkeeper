## 1. Cipher Layer — Support 32-byte Keys

- [x] 1.1 In `cipher.py`, update `encrypt` to accept 16- or 32-byte keys (remove AES-128-only guard; update docstring/comment)
- [x] 1.2 In `cipher.py`, update `decrypt` to accept 16- or 32-byte keys (same guard removal)
- [x] 1.3 In `cipher.py`, update `ShareSession.__init__` to accept 16- or 32-byte keys

## 2. Handshake — Fix Shared Key Derivation (TDD)

- [x] 2.1 In `tests/test_handshake.py`, add a failing test asserting `derive_shared_key` returns 32 bytes
- [x] 2.2 In `handshake.py`, change `derive_shared_key` to return `shared` (all 32 bytes) instead of `shared[:16]`
- [x] 2.3 Run the new test to confirm it passes; run the full suite to confirm no regressions

## 3. Cipher Tests — 32-byte Key Coverage

- [x] 3.1 In `tests/test_cipher.py`, add tests for `ShareSession` with a 32-byte key: encode then decode round-trip
- [x] 3.2 Confirm existing 16-byte-key tests for `CbcSession` still pass (handshake stage unchanged)

## 4. State Machine Test Updates

- [x] 4.1 Update `tests/test_handshake_state_machine.py`: wherever `ShareSession` is constructed with a 16-byte test key, verify the test still makes sense (or update to use a 32-byte key to match real behaviour)

## 5. Hardware Validation

- [ ] 5.1 Run `uv run voltkeeper status DC:B4:D9:46:73:96` and confirm a successful SOC read with no errors
- [x] 5.2 Run the full test suite (`uv run pytest`) and confirm all tests pass
