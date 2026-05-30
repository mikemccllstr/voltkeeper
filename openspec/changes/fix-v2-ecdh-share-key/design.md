## Context

The BLE encrypted handshake for V2 devices uses two distinct AES sessions:

1. **Handshake stage** (`bleConnAESKey`): AES-128, 16-byte key derived from XOR of `randomMd5` and `LOCAL_AES_KEY`. Used for ECDH message exchange frames.
2. **Post-handshake stage** (`bleConnShareKey`): AES-256, 32-byte key = full ECDH shared secret. Used for all Modbus command/response frames.

Our current `derive_shared_key` returns only the first 16 bytes of the 32-byte ECDH shared secret. The APK's `ECDHUtils.getSharedSecret()` returns all 32 bytes and uses them directly as the AES key. Hardware testing confirmed this: the handshake completes but the device cannot decrypt our AES-128 post-handshake requests and responds with plaintext error frames (`2A 2A ...`).

The cipher code (`encrypt`, `decrypt`, `ShareSession`) currently asserts a 16-byte key, which would also need to be relaxed.

## Goals / Non-Goals

**Goals:**
- Derive `bleConnShareKey` as the full 32-byte ECDH shared secret
- Support 32-byte (AES-256) keys throughout the cipher layer
- Restore end-to-end encrypted Modbus communication with V2 devices

**Non-Goals:**
- Change the handshake-stage AES-128 key derivation (that part is correct)
- Change the frame format for either stage
- Support 24-byte (AES-192) keys (not used by this protocol)

## Decisions

### D1: Return full 32 bytes from `derive_shared_key`

The APK uses `keyAgreement.generateSecret()` directly — the full x-coordinate of the ECDH shared point on SECP256R1, which is 32 bytes. No truncation, no KDF. We match this exactly.

**Alternative considered**: Apply a KDF (HKDF or SHA-256) to derive a 16-byte key. Rejected: the APK does no such derivation, and we must match the device firmware's expectation precisely.

### D2: Relax key-length validation in `encrypt`/`decrypt`/`ShareSession` to accept 16 or 32 bytes

The validation comment currently says "AES-128 key must be 16 bytes". The handshake stage genuinely uses 16-byte keys; the post-handshake stage uses 32-byte keys. Both are valid uses of the same `encrypt`/`decrypt` primitives — AES supports 128, 192, and 256-bit keys with the same block size (16 bytes). The validation should allow both.

**Alternative considered**: Split into `encrypt128`/`encrypt256`. Rejected: unnecessary complexity; `algorithms.AES(key)` already selects the correct mode based on key length.

### D3: No changes to `_on_notification` expected size calculation

`expected = 6 + ((response_size + 15) // 16) * 16` — AES-256 still uses 16-byte blocks, so the ciphertext-length formula is unchanged.

## Risks / Trade-offs

- **Risk**: AES-256 performance overhead. → Negligible for BLE traffic volumes; no mitigation needed.
- **Risk**: Some unit tests for `ShareSession`/`cipher.py` may hard-code 16-byte test keys and need updating. → Caught at test-run time; fix as part of the task.

## Open Questions

(none — the APK source is unambiguous)
