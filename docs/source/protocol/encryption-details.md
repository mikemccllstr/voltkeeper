# Encryption Details

This page documents the complete cryptographic material found in the Bluetti APK, including all hardcoded keys, AES-128-CBC cipher parameters, IV chaining behavior, and key derivation formulas.

## 15.8 Complete Crypto Material

All keys are hardcoded in the APK and identical across all installations.

| Key              | Value                                                                                                                                                                                    | Source File               |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `LOCAL_AES_KEY`  | `459FC535808941F17091E0993EE3E93D`                                                                                                                                                       | `ConnConstantsV2.java:98` |
| `PRIVATE_KEY_L1` | `4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337`                                                                                                                       | `SignatureCrypt.java:34`  |
| `PUBLIC_KEY_K2`  | `3059301306072a8648ce3d020106082a8648ce3d03010703420004A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594` | `SignatureCrypt.java:35`  |

**Key derivation formulas:**

```
# Legacy challenge-response:
random_bytes = data[4:8]                           # from device hello packet
randomMd5 = MD5(reverse(random_bytes))              # 32 hex chars
bleConnAESKey = XOR(randomMd5, LOCAL_AES_KEY)       # 32 hex chars → 16 bytes

# ECDH (protocol v2+):
ecdh_shared_secret = ECDH_secp256r1(app_ephemeral_privkey, device_iot_pubkey)
bleConnShareKey = ecdh_shared_secret                # 32 hex chars → 16 bytes
```

**Cipher:** AES-128-CBC, IV chained from MD5(randomMd5), 16-byte blocks, no padding.
