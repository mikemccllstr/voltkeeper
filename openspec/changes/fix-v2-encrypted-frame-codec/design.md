## Context

`fix-v2-handshake-stage2` got a live Elite 100 V2 (`DC:B4:D9:46:73:96`) through the status-ack
into stage 2, but the ECDH block still fails with `Ciphertext length must be a multiple of 16`.
A raw capture plus the APK (`ConnectManager.bleEncryptedHandle`, `ProtocolParse.buildAESCBCCmd` /
`parseAESCBCData`) pin down the remaining framing. All three decisions below are confirmed against
captured bytes, not inferred.

**Captured ECDH notification (146 bytes):**

```
00 86 | <144 bytes AES-CBC ciphertext>
^^^^^   0x0086 = 134 = plaintext length (2A2A0480 + 64B pubkey + 64B sig + 2B checksum)
```

Decrypting `block[2:]` with key = `randomMd5 XOR LOCAL_AES_KEY`, IV = `bytes.fromhex(randomMd5)`
yields plaintext `2a2a0480 <64B pubkey> <64B sig> <2B checksum=3e3e> <pad>`. The checksum matches
the BE sum over `[2:132]`, the pubkey is a valid SECP256R1 point, and `[4:68]`/`[68:132]` (the
offsets `fix-v2-handshake-stage2` already set) are correct *after* the prefix is stripped.

## Goals / Non-Goals

**Goals:**
- Strip the 2-byte length prefix before decrypt and prepend it on every outbound encrypted frame.
- Verify the device ECDSA signature and produce ours over the hex-decoded `randomMd5` message.
- Complete ECDH through the `2A2A06` confirmation and derive `bleConnShareKey`.
- Decode/encode post-handshake Modbus frames with their embedded per-frame IV.
- End-to-end on hardware: full handshake + a real Modbus read (`voltkeeper status` → SOC).
- Make the state-machine simulator byte-accurate so the framing is unit-tested.

**Non-Goals:**
- Any change to stage-1 framing or the status-ack (done and hardware-confirmed).
- Plaintext-device (AC2A) behavior.
- The per-SN key-binding question (`client.py:80`) — still a separate follow-up, only assessable
  once a Modbus read is attempted.

## Decisions

### Decision 1: 2-byte plaintext-length prefix on every encrypted frame

`parseAESCBCData` reads `substring(0,4)` as a `%04X` plaintext byte-count `i2`, decrypts the
remainder (from offset 4 when an explicit IV is supplied), then returns `result[0 : i2*2]` —
trimming the zero-padding to exactly `i2` plaintext bytes. `buildAESCBCCmd` mirrors this: it emits
`String.format("%04X", plaintextLen)` followed by the ciphertext.

Implementation: the inbound collector reads the 2-byte prefix, collects exactly `ceil(len/16)*16`
ciphertext bytes, decrypts, and trims to `len`. The outbound builder prepends `len.to_bytes(2,"big")`.
This replaces the current `_collect(144)` fixed-size read, which is what swallowed the prefix.

**Alternative considered:** keep `_collect(144)` and special-case the ECDH block. Rejected — the
prefix is universal (confirmed in both `buildAESCBCCmd` and `parseAESCBCData`), so the codec must
handle it generally for the `2A2A05`/`2A2A06`/Modbus frames too.

### Decision 2: Signature message hex-decodes randomMd5 (80 bytes)

APK: `verifyForECDSA256WithCachedKey(hexStringToBytes(iotPkHexStr + randomMd5), ...)` and, for our
reply, `sign(hexStringToBytes(pkHexStr + randomMd5))`. Both hex-decode the concatenated hex strings:
64-byte pubkey + 16-byte digest = 80 bytes. Confirmed against the captured device signature:

```
ascii_md5  (current, 96 bytes) -> verify FAIL
hexdecode_md5 (apk,    80 bytes) -> VERIFY OK against PUBLIC_KEY_K2
```

Fix `verify_device_pubkey` and `sign_app_pubkey` to use `bytes.fromhex(random_md5_hex)` instead of
`random_md5_hex.encode("ascii")`. This supersedes `fix-v2-handshake-stage2` design D3.

**Alternative considered:** uppercase ASCII. Rejected — also fails verification against the captured
signature; only the 80-byte hex-decoded form verifies.

### Decision 3: Post-handshake frames embed a per-frame IV seed

When `bleConnShareKey` is set and `iv == null`, `parseAESCBCData` treats the frame as
`[2-byte len][4-byte random][ciphertext]` and derives `IV = MD5(the 4 random bytes)` (it advances
the read offset to 12 hex chars = 6 bytes). `buildAESCBCCmd` builds outbound frames the same way:
4 fresh random bytes, IV = their MD5, then `%04X` length + 4-byte random + ciphertext.

So the post-handshake codec is distinct from the handshake-stage codec:

| Stage          | Key               | Frame layout                          | IV source                  |
|----------------|-------------------|---------------------------------------|----------------------------|
| Handshake      | `bleConnAESKey`   | `[2B len][ciphertext]`                | `bytes.fromhex(randomMd5)`, CBC-chained |
| Post-handshake | `bleConnShareKey` | `[2B len][4B random][ciphertext]`     | `MD5(4B random)` per frame  |

This supersedes `fix-v2-handshake-stage2` design D4 (reset-vs-chained was the wrong framing of the
question).

**Alternative considered:** reuse `CbcSession` chaining for post-handshake traffic. Rejected — each
frame carries its own IV seed, so chaining state from the previous frame would mis-decrypt.

### Decision 4: Byte-accurate state-machine simulator

Update the device-side simulator to (a) prepend the `%04X` length prefix on encrypted frames,
(b) sign with the hex-decoded message, and (c) for any post-handshake frame, emit the
`[len][4B random][ciphertext]` layout. The existing `verify_device_pubkey` mock in the full-handshake
test can be dropped once the real signature verifies, but keep a dedicated invalid-signature test.

## Risks / Trade-offs

- **Two frame layouts increase codec surface.** → Encapsulate each in a small, separately-tested
  codec; the table above is the contract.
- **Per-frame random IV is hard to unit-test deterministically.** → Inject the random source (or the
  4 IV-seed bytes) in tests so encrypt/decrypt round-trips are reproducible; let it default to
  `os.urandom` in production.
- **First Modbus read may still fail for a non-framing reason** (per-SN key binding). → If a clean
  `2A2A06` is followed by a Modbus timeout/exception rather than a decrypt error, that points at the
  `client.py:80` follow-up, not this change.

## Migration Plan

No data/API migration. Stage 2 has never completed; rollback is reverting the commit. The handshake
and post-handshake codecs are new code paths exercised only by encrypted V2 devices; plaintext
devices are untouched.

## Open Questions

- Does any device coalesce the post-handshake IV-seed and ciphertext differently across BLE
  notifications? (Capture shows single-notification frames; verify on the first multi-frame Modbus
  response.)
- Is there a per-SN key-binding step gating Modbus after a clean `2A2A06`? (Out of scope; watch for
  its signature during hardware validation.)
