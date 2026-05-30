## Context

The archived `fix-v2-encrypted-handshake` change corrected stage-1 framing; a live Elite 100 V2
(`DC:B4:D9:46:73:96`) trace confirms the device now accepts our reply and proceeds to stage 2:

```
our reply   : 2A 2A 02 04 B4 BE 4E 8F 02 55        (accepted)
device ack  : 2A 2A 03 01 00 00 04                 (status 00 = OK)
device      : <144-byte AES-CBC ECDH block>        (encrypted with bleConnAESKey)
our code    : Error: Ciphertext length must be a multiple of 16
```

`HandshakeSession.run` does `encrypted = await self._collect(144)` immediately after sending the
reply. `_collect` appends whole notifications until it has ≥144 bytes — so it grabs the 7-byte
plaintext ack first, then the 144-byte block (151 bytes total), and `CbcSession.decrypt` rejects
the non-multiple-of-16 length. The fix is to read and validate the `2A 2A 03` ack first, then
collect exactly the 144-byte ECDH block.

APK reference (authoritative): `ConnectManager.bleEncryptedHandle`. `i == 3` → `getTaskQueue().poll()`
(ack handled separately). For the ECDH message (`i == 4`) it reads `subList(4, 68)` for the device
pubkey and `subList(68, size-2)` for the signature — i.e. after the length byte at offset 3.

## Goals / Non-Goals

**Goals:**
- Consume the `2A 2A 03` status-ack so the ECDH block decrypts cleanly.
- Read the ECDH pubkey/signature at the APK offsets (`[4:68]` / `[68:132]`).
- Verify the device signature and complete the ECDH exchange through the `2A 2A 06` confirmation.
- Validate end to end on hardware: full handshake + a real Modbus read (`voltkeeper status` → SOC).
- Unit-test the ack-frame handling in the state-machine simulator.

**Non-Goals:**
- The per-SN key-binding question (`client.py:80`) — a separate follow-up, only assessable after a
  successful ECDH + first Modbus attempt.
- Any change to stage-1 framing (done and confirmed) or to plaintext devices.

## Decisions

### D1: Read the ack frame explicitly, then collect the ECDH block

Add a step between sending the reply and collecting the ECDH block: read one notification, validate
it is `2A 2A 03 01 <status>` with `status == 0x00`, and discard it (raise on non-zero status). Then
`_collect(144)`. This mirrors the APK's separate handling of `i == 3`.

**Alternative considered:** make `_collect` skip any leading `2A 2A 03` frame automatically. Rejected
— too implicit; an explicit read documents the protocol step and lets us surface a bad status.

**Risk to check on hardware:** whether the ack and the ECDH block ever arrive in a single BLE
notification. The trace shows them as separate notifications (the ack fires, then the block). If a
device coalesces them, the explicit-read approach needs to handle a combined buffer — verify against
the live trace and adjust only if observed.

### D2: ECDH offsets shift by one to match the length-framed message

Change `device_pub_raw = plaintext[3:67]` → `plaintext[4:68]` and `signature_rs = plaintext[67:131]`
→ `plaintext[68:132]`. The `2A 2A 04` header is followed by a length byte at offset 3 (`0x80` = 128 =
pubkey + signature), exactly like the stage-1 `0x04`. The existing code comment already flags this.

### D3: Keep randomMd5 lowercase in the signed message; verify on hardware

Stage 1 deliberately kept `randomMd5` lowercase to match `MD5.md5Encode`. The signed message is
`devicePubKey || randomMd5_ascii`. If ECDSA verification against `PUBLIC_KEY_K2` fails on the real
device, the case (or the message layout) is the first suspect. Decide empirically from the live trace
rather than guessing now.

### D4: Resolve the post-handshake IV empirically

`handshake.py` returns `CbcSession(shared_key, initial_iv)` with a CAVEAT about whether the IV resets
to `derive_iv(randomMd5)` or continues chaining from the last handshake ciphertext block. The decisive
test is whether the first encrypted Modbus response decrypts to a valid frame. Try the current
reset-to-`initial_iv`; if Modbus decrypts to garbage, switch to the chained IV (`enc_session._iv`).

## Risks / Trade-offs

- **More hidden stage-2 framing surprises.** → Validate incrementally on hardware after each fix; the
  live trace is the ground truth and the device is in range.
- **Signature verify fails for a subtle reason (case, byte order, message layout).** → Capture the
  decrypted ECDH message and the exact signed bytes from a trace and compare against the APK before
  changing the signing/verify path.
- **IV choice for Modbus is wrong.** → Binary decision with a clear test (valid vs garbage Modbus
  frame); both options are one line apart.
- **Per-SN key binding actually gates Modbus.** → If `status` still fails after a clean `2A 2A 06`
  confirmation with a Modbus-exception/timeout pattern, that points at the `client.py:80` follow-up,
  not this change.

## Migration Plan

No data/API migration. Stage 2 has never completed, so nothing to preserve or roll back; rollback is
reverting the commit. Plaintext devices are untouched.

## Open Questions

- Does the device coalesce the `2A 2A 03` ack and the ECDH block into one notification on any path?
- Does the ECDSA signed message use lowercase `randomMd5` ASCII exactly (D3)?
- Reset vs chained IV after the key handoff (D4)?
- Is there a per-SN key-binding step before Modbus is accepted (out of scope, but watch for its signature)?
