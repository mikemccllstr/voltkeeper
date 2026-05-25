# Security

This page covers the Bluetti BLE encryption protocols: the legacy challenge-response handshake, ECDH+ECDSA mutual authentication (protocol v2), the Bluetooth password PIN mechanism, and the complete cryptographic material.

## Section 12 — BLE Encryption Key Retrieval

### 12.1 Overview

The app uses two distinct BLE security protocols depending on device firmware generation. Neither protocol fetches a session key from the cloud at runtime — all cryptographic material is either hardcoded in the APK or derived on-device from a challenge-response exchange.

### 12.2 Path 1 — Legacy Challenge-Response (Protocol v1)

Applies to older devices where `protocolVer < 2000`.

**Flow:**

1. Device sends a BLE "hello" packet containing a 4-byte random value at bytes 4–7.
1. App reverses the 4 random bytes, computes MD5 → stores as `randomMd5`.
1. App responds with a challenge packet: `"2A2A0204" + randomMd5.substring(16, 24)` + 1-byte checksum.
1. Session AES key is derived as:

```
bleConnAESKey = XOR(randomMd5, LOCAL_AES_KEY)
```

**Hardcoded key** (`ConnConstantsV2.LOCAL_AES_KEY`):

```
459FC535808941F17091E0993EE3E93D
```

5. All subsequent BLE data is encrypted/decrypted with `AES-CBC` using `bleConnAESKey`.

**Key source files:**

- `ConnectManager.java:1909–1925` — challenge-response derivation
- `ConnConstantsV2.java:98` — `LOCAL_AES_KEY` constant
- `ProtocolParse.java:1424` — `buildAESCBCCmd(cmd, aesKey, iv)`

### 12.3 Path 2 — ECDH + ECDSA Mutual Authentication (Protocol v2)

Applies to newer devices (protocol v2+, e.g., EPAD, PLP025, and other 2nd-gen IoT modules). This path adds ECDSA-based device identity verification and ECDH-based forward-secret session key derivation.

**Flow:**

1. **Challenge-response** (same as Path 1, establishes `bleConnAESKey` as a temporary transport key).
1. **Device sends ECDH public key + ECDSA signature** (encrypted with `bleConnAESKey`):
   - Response type `0x04`: payload contains `iotPkHexStr` (64-byte uncompressed SECP-256R1 public key) + `signature` (64-byte raw ECDSA-SHA256 signature over `iotPublicKey || randomMd5`).
1. **App verifies signature** using hardcoded ECDSA verification key `PUBLIC_KEY_K2`:

```
PUBLIC_KEY_K2 =
"3059301306072a8648ce3d020106082a8648ce3d03010703420004
 A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251
 EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594"
```

This is an X.509-encoded SECP-256R1 (P-256) public key.

4. **App generates ephemeral ECDH keypair** (SECP-256R1), then **signs** `(appPublicKey || randomMd5)` with hardcoded private key `PRIVATE_KEY_L1`:

```
PRIVATE_KEY_L1 = "4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337"
```

5. **App sends** its ephemeral public key + own ECDSA signature to the device (`0x2A2A0580` packet).
1. **Device responds** with response type `0x06` confirming acceptance.
1. **Session key derived** via ECDH:

```
bleConnShareKey = ECDH_SharedSecret(appEphemeralPrivKey, deviceIoTPublicKey)
```

`bleConnAESKey` is discarded; all subsequent BLE traffic is encrypted with `bleConnShareKey` using AES-CBC.

**Key source files:**

- `ConnectManager.java:1934–1961` — ECDH key exchange logic
- `ConnectManager$bleEncryptedHandle$2$1.java:67–154` — ECDSA verify + ECDH keypair generation
- `SignatureCrypt.java:32–33` — hardcoded `PUBLIC_KEY_K2` and `PRIVATE_KEY_L1`
- `ECDHUtils.java:29–33` — SECP-256R1 ASN.1 DER prefixes

### 12.4 "Server BLE Key" and Related Device Registers

A separate per-device key (`serverBLEKey`) is stored in the IoT module at **Modbus register 13603** (`ProtocolAddrV2.IOT_BLE_SERVER_KEY`). This is not a session key; it is a long-lived key provisioned into the device by the server during manufacturing or cloud registration.

**Usage:** When pairing a Fingerprint Screen (FPS) accessory to a main device, the app:

1. Reads the main device's server BLE key over BLE (`getReadTask(13603)`).
1. Broadcasts the key via `LiveEventBus` event `"IOT_SERVER_KEY"`.
1. Passes it as Intent extra `"serverBLEKey"` to `DeviceBluetoothScanActivity` for the screen pairing flow.

This key is not fetched from a cloud REST API by the app at runtime; it is read directly from the device register over BLE.

**Related registers (not used for general BLE device control):**

| Register | Address              | Name               | Purpose                                            |
| -------- | -------------------- | ------------------ | -------------------------------------------------- |
| 13603    | `IOT_BLE_SERVER_KEY` | Server BLE Key     | FPS/screen accessory pairing key                   |
| 12185    | `IOT_BLE_SERVER_SET` | Server BLE Set     | Write register for provisioning the server BLE key |
| 13776    | `BLE_CLIENT_PAIR_SN` | BLE Client Pair SN | Sub-device/accessory pairing serial number         |

**Key source files:**

- `ConnectManager.java:2266–2267` — register 13603 → `ACTION_IOT_SERVER_KEY` event
- `DeviceFPSResetActivity.java:198–221` — subscribes to event, stores `serverBLEKey`
- `DeviceFPSResetActivity.java:161–170` — passes key as Intent extra to scan activity

### 12.5 Security Observations

| Issue                                                | Detail                                                                                                                                                                                                            |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hardcoded local AES key**                          | `LOCAL_AES_KEY = 459FC535808941F17091E0993EE3E93D` is identical across all app installations. Any attacker who captures a BLE session can decrypt it given the `randomMd5` (derivable from the challenge packet). |
| **Hardcoded ECDSA private key**                      | `PRIVATE_KEY_L1` is embedded in the APK. An attacker can extract it, sign arbitrary ECDH public keys, and impersonate the official Bluetti app to any device.                                                     |
| **Hardcoded ECDSA verification key**                 | `PUBLIC_KEY_K2` is the only device-authenticity anchor. All Bluetti devices share the same IoT identity signing key.                                                                                              |
| **No cloud key fetch for sessions**                  | BLE session keys are fully self-contained; revocation or re-keying without an app update is not possible.                                                                                                         |
| **getQrCodeEncrypt endpoint**                        | `GET /api/blusmartprod/device/basic/v1/getQrCodeEncrypt` exists in the API list but is not used in the BLE session key flow — it appears to be related to QR-code-based device pairing, not BLE encryption.       |
| **BLE password checked client-side only**            | The 6-digit PIN is read from the device over BLE, then compared against user input in the app. An attacker who completes the BLE handshake can read the register holding the PIN and bypass the check.            |
| **BLE password stored on device, readable over BLE** | Once the encrypted session is established, the PIN value is transmitted in the clear (encrypted at the transport layer by the global session key).                                                                |

### 12.6 Bluetooth Password — Per-Device PIN Authorization

Separate from session encryption, the app supports an **optional per-device 6-digit BLE password** that gates access after a successful BLE connection and handshake. This is not an encryption key — it is an authorization PIN.

**Config flags** (stored in `DeviceBaseConfigBean`):

- `btPswEnable` (int): Whether a BLE password is active on this device
- `btLoginPsw` (String): The 6-digit PIN value

**How the password is read:** Both fields are parsed from the base config response at `ProtocolParse.java:97-99`:

```java
// btPswEnable from bits 0-1 of hex positions 10+11
deviceBaseConfigBean.setBtPswEnable(Integer.parseInt(
    list.get(1) + list.get(0), 2));
// btLoginPsw from hex positions 12-17 (6 ASCII bytes)
deviceBaseConfigBean.setBtLoginPsw(
    getASCIIStr(dataRes.subList(12, 18), true));
```

**How the password is checked:** After BLE connect succeeds, `DeviceBluetoothScanActivity.java:961-986` checks `btPswEnable == 1`. If active, it shows `DeviceBluetoothPswCheckDialog` (`DeviceBluetoothPswCheckDialog.java`) — a 6-digit PIN entry popup. The check at line 96 is a simple string comparison:

```java
if (Intrinsics.areEqual(strUserInput, this.bluetoothPassword)) {
    successHandle();  // proceed to device home
} else {
    // show error toast, retry count, disconnect on timeout
}
```

If the user closes the dialog or fails the check, `ConnectManager.disconnectDevice()` is called — the BLE connection is terminated. The dialog has a 60-second countdown timer.

**How the password is set:** The device owner sets it from the device settings screen via `DeviceBluetoothPswSetupDialog` (`DeviceBluetoothPswSetupDialog.java`), which calls `ProtocolParse.bluetoothPswSetupData(password)` (`ProtocolParse.java:1164-1196`). This encodes a 6-character password as a 12-byte hex string and writes it to the `BLUETOOTH_PASSWORD` register (address 7 in `ProtocolAddr.java:16`).

**To remove the password:** The `negativeClick` handler in `DeviceBluetoothPswSetupDialog.java:242` sends the "no password" message and writes zeroes (6 × "00" bytes) to clear the stored PIN, setting `btPswEnable` back to 0.

**Key source files:**

- `ProtocolParse.java:97-99` — `btPswEnable` and `btLoginPsw` parsing from base config
- `ProtocolParse.java:1164-1196` — `bluetoothPswSetupData()` password encoding
- `ProtocolAddr.java:16` — `BLUETOOTH_PASSWORD` register address (7)
- `DeviceBluetoothScanActivity.java:961-986` — password check trigger after BLE connect
- `DeviceBluetoothPswCheckDialog.java:89-106` — PIN comparison and success/failure handling
- `DeviceBluetoothPswSetupDialog.java:46-58, 204-242` — password setup and clear dialogs

______________________________________________________________________

### 15.2 BLE Connection and Handshake Flow

#### Step 1: Scan & Connect

1. Start BLE scan filtered by service `0000ff00-...`
1. On device found, call `connectGatt()` with `transport=LE`
1. Wait for services discovery (500ms delay auto-triggered)
1. Find `BluetoothGattService` using service UUID from scanned device
1. Get write characteristic (`ff02`) and read/notify characteristic (`ff01`)
1. Enable notifications on `ff01` with descriptor `00002902-...` using `ENABLE_NOTIFICATION_VALUE` (`{0x01, 0x00}`)

#### Step 2: Read Device Snapshot

After connection, the app reads the base config to determine protocol version and capabilities:

1. Read protocol version from Modbus register 16 (v1: `0103 0010 0001 ...`) or V2 equivalent
1. Read base config from register 1
1. Read device SN from register 21
1. Read real-time data from register 10

#### Step 3: Encryption Handshake (for encrypted devices)

For devices where `isESP32Encrypted == true` or `isBLEEncrypted == true`:

**3a. Challenge-Response:**

1. Device sends: `2A 2A 01` followed by 4 random bytes (position 4-7)
1. App reverses the 4 random bytes, computes MD5 → `randomMd5`
1. App responds: `2A 2A 02 04` + `randomMd5.substring(16, 24)` + 2-byte checksum
1. App derives temporary key: `bleConnAESKey = XOR(randomMd5, LOCAL_AES_KEY)`

**3b. ECDH Key Exchange (protocol v2+):**

1. Device sends `2A 2A 04 ...` (AES-CBC encrypted with `bleConnAESKey`, IV=MD5(randomMd5))
   - Bytes 4-67: device's SECP-256R1 public key (64 bytes, raw X+Y, no 04 prefix)
   - Bytes 68 to (end-2): raw ECDSA signature (r||s, 64 bytes) over `(devicePublicKey || randomMd5)`
   - Last 2 bytes: checksum (little-endian sum of preceding bytes)
1. App verifies ECDSA signature using hardcoded `PUBLIC_KEY_K2`
1. App generates ephemeral SECP-256R1 keypair
1. App signs `(appPublicKey || randomMd5)` with hardcoded `PRIVATE_KEY_L1`
1. App sends `2A 2A 05 80 ...` with app public key + signature
1. Device responds `2A 2A 06 00 ...` confirming acceptance
1. App derives shared secret via ECDH: `bleConnShareKey = ECDH(appPrivKey, devicePubKey)`
1. `bleConnAESKey` discarded; all subsequent traffic encrypted with `bleConnShareKey`

**3c. Post-handshake encryption:**
All subsequent Modbus frames are AES-CBC encrypted using `bleConnShareKey` (or `bleConnAESKey` if ECDH not completed):

- Written via `buildAESCBCCmd(cmd, aesKey, iv)`
- The IV for the first block is derived from MD5(randomMd5), then chained from previous ciphertext
- Each 16-byte block padded to exactly 16 bytes (no PKCS padding)

#### Step 4: Modbus Data Protocol (post-handshake)

Once encrypted channel is established, device communication uses standard Modbus RTU-style frames.

______________________________________________________________________

### 15.8 Complete Crypto Material

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
