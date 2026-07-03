# Encryption Details

This page documents the complete cryptographic material found in the Bluetti APK, including all hardcoded keys, AES-CBC cipher parameters, IV chaining behavior, and key derivation formulas.

## Crypto Material

All keys are hardcoded in the APK and identical across all installations.

| Key              | Value                                                                                                                                                                                    | Source File               |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `LOCAL_AES_KEY`  | `459FC535808941F17091E0993EE3E93D`                                                                                                                                                       | `ConnConstantsV2.java:98` |
| `PRIVATE_KEY_L1` | `4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337`                                                                                                                       | `SignatureCrypt.java:34`  |
| `PUBLIC_KEY_K2`  | `3059301306072a8648ce3d020106082a8648ce3d03010703420004A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594` | `SignatureCrypt.java:35`  |

**Key derivation formulas:**

```
# Legacy challenge-response:
random_bytes = challenge[4:8]                       # 4 bytes after the 0x04 length field
randomMd5 = MD5(reverse(random_bytes))              # 32 LOWERCASE hex chars
bleConnAESKey = decode(randomMd5) XOR LOCAL_AES_KEY  # byte-wise XOR of two 16-byte values
IV           = decode(randomMd5)                    # the raw 16-byte digest (NOT MD5(randomMd5))

# ECDH (protocol v2+):
ecdh_shared_secret = ECDH_secp256r1(app_ephemeral_privkey, device_iot_pubkey)
bleConnShareKey = ecdh_shared_secret                # full 32-byte shared point X
```

`decode(x)` means hex-decode the string to bytes. `randomMd5` is the lowercase MD5
hex digest; `bleConnAESKey` and the IV are derived from its **decoded** 16 bytes —
not from XOR-ing the ASCII characters of the hex string, and not from a second MD5.

**Cipher:** zero-padding (no PKCS). Every encrypted frame is prefixed with a 2-byte big-endian plaintext length. Handshake-stage frames (`bleConnAESKey`, 16-byte key) use AES-128-CBC: `[2B len][ciphertext]`, IV = `decode(randomMd5)`, CBC-chained. Post-handshake frames (`bleConnShareKey`, 32-byte key) use AES-256-CBC: `[2B len][4B seed][ciphertext]`, IV = `MD5(seed)` per frame.

**ECDSA signature message** (both device→app verify and app→device sign): `devicePubKey(64) || decode(randomMd5)(16)` — 80 bytes. The ASCII hex form of `randomMd5` (96 bytes) is NOT used.

The device enforces the app-pubkey signature; a substitute key causes the ECDH
confirmation frame to return status `0x01` (app-pubkey signature rejected) and
the handshake aborts. This was confirmed on an Elite 100 V2 (2026-07-03) and
is documented in {doc}`security`.

## Legacy challenge-response frame format

The legacy handshake (`ConnectManager.bleEncryptedHandle`) exchanges symmetric
**10-byte frames**. Both the device's challenge and the app's reply share one layout:

```
2A 2A | TT | LL | <payload: LL bytes> | <CC CC>
└ hdr ┘ type len                        big-endian sum
```

- `2A 2A` — fixed frame header.
- `TT` — type: `01` device challenge, `02` app reply (later stages use `04`/`05`/`06`).
- `LL` — length of the payload in bytes (`04` for the 4-byte challenge/reply payload).
- `CC CC` — 2-byte **big-endian** sum of every byte after the header, i.e. `TT + LL + payload`.

The reply payload is the **4 bytes obtained by hex-decoding** `randomMd5[16:24]` — not the
8 ASCII characters of that hex substring. The `LL = 04` length field confirms 4 bytes.

**Worked example** (captured from a real Elite 100 V2, `DC:B4:D9:46:73:96`):

```
challenge : 2A 2A 01 04 3D 96 87 E0 02 3F
            random = 3D 96 87 E0                       (challenge[4:8])
            checksum 02 3F = BE sum of 01 04 3D 96 87 E0
randomMd5 : a0ce9adc2c5341f1d271d0518c4e7773            (MD5 of E0 87 96 3D)
token     : randomMd5[16:24] = "d271d051" -> D2 71 D0 51
reply     : 2A 2A 02 04 D2 71 D0 51 02 6A
            checksum 02 6A = BE sum of 02 04 D2 71 D0 51
```

The device rejects any reply that does not match and re-issues its challenge, then
disconnects after ~5 s. See {doc}`security` for the full handshake sequence.
