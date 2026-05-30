## Why

Stage 1 of the V2 encrypted handshake now works on real hardware: the Elite 100 V2 accepts our legacy challenge reply and proceeds into stage 2 (ECDH). But our code can't parse stage 2 — `HandshakeSession.run` dies with `Ciphertext length must be a multiple of 16` because a 7-byte status-ack frame the device sends before the ECDH block gets swallowed into the ciphertext buffer. Until stage 2 completes, no encrypted device can run a single Modbus command. The device is in range now, so we can validate each step against a live trace.

## What Changes

- **Consume the `2A 2A 03` status-ack frame** the device sends after accepting the legacy reply, before collecting the encrypted ECDH block. Today `_collect(144)` greedily appends the 7-byte ack to the 144-byte block (151 bytes → misaligned → decrypt fails). The ack carries a status byte (`00` = OK); a non-OK status SHALL abort the handshake with a clear error.
- **Fix the ECDH message parse offsets** to match the APK: device public key at `plaintext[4:68]` and signature at `plaintext[68:132]` (after the `0x04`-style length field at offset 3), not the current `[3:67]`/`[67:131]`.
- **Confirm signature-message case consistency**: `verify_device_pubkey` / `sign_app_pubkey` ASCII-encode `randomMd5` (now lowercase) into the signed message. Validate the ECDSA verify against `PUBLIC_KEY_K2` succeeds with the real device; correct the case if not.
- **Resolve the post-handshake IV** when the session key switches from `bleConnAESKey` to `bleConnShareKey` (the existing CAVEAT in `handshake.py`), against a real transcript.
- **Tests**: extend `test_handshake_state_machine.py` so the simulated device injects the `2A 2A 03` ack between the reply and the ECDH block, and assert the handshake consumes it and still completes.
- **Docs**: document the status-ack frame and the corrected ECDH offsets in `docs/source/protocol/security.md` and `encryption-details.md`.

Out of scope (separate follow-up): the per-SN key-binding question in `client.py:80` — whether Modbus traffic is gated on a per-serial step. Only assessable once ECDH completes and the first Modbus read is attempted.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `ble-encrypted-handshake`: add requirements for the post-reply status-ack frame and the ECDH key-exchange stage (message parse offsets, signature verification, session-key/IV handoff). Stage-1 requirements are unchanged.

## Impact

- **Code**: `src/voltkeeper/bluetooth/handshake.py` (`HandshakeSession.run` ack handling + ECDH offsets; possibly `verify_device_pubkey`/`sign_app_pubkey` and the final IV).
- **Tests**: `tests/test_handshake_state_machine.py` (inject the ack frame), plus framing vectors as needed.
- **Docs**: `docs/source/protocol/security.md`, `docs/source/protocol/encryption-details.md`.
- **Behavior**: completes the encrypted handshake so encrypted devices can run Modbus commands (`status`, `verify`, `set`, daemon). Plaintext devices unaffected.
- **Success criterion**: a live Elite 100 V2 connect completes the full handshake (`2A 2A 06` confirmation) and `voltkeeper status` returns valid data (e.g. SOC).
- **No backward-compatibility concern**: stage 2 has never completed, so there is no working behavior to preserve.
