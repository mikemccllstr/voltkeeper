## Why

Hardware testing shows the BLE encrypted handshake completes successfully (through the `2A 2A 06` confirmation), but all subsequent Modbus reads fail — the device responds with unencrypted `2A 2A` frames, indicating it cannot decrypt our requests. The root cause is confirmed by APK source analysis: `ECDHUtils.getSharedSecret()` returns the full 32-byte ECDH shared secret and it is used directly as an AES-256 key, but our `derive_shared_key` truncates it to 16 bytes (AES-128), making post-handshake communication impossible.

## What Changes

- **`derive_shared_key` in `handshake.py`**: Return the full 32-byte ECDH shared secret instead of `shared[:16]`.
- **`ShareSession` in `cipher.py`**: Remove the 16-byte key length restriction; accept 32-byte keys (AES-256).
- **`encrypt`/`decrypt` helpers in `cipher.py`**: Relax the AES-128-only guard to accept both 16-byte (AES-128) and 32-byte (AES-256) keys.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ble-encrypted-handshake`: Add a requirement specifying that `bleConnShareKey` is the **full 32-byte** raw ECDH shared secret (not truncated), used as an AES-256 key for all post-handshake frames.

## Impact

- `src/voltkeeper/bluetooth/handshake.py` — `derive_shared_key`
- `src/voltkeeper/bluetooth/cipher.py` — `encrypt`, `decrypt`, `ShareSession`
- Tests: `tests/test_handshake.py`, `tests/test_cipher.py`, `tests/test_handshake_state_machine.py`
