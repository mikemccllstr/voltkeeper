# Firmware Updates

This page documents the complete firmware update flow for Bluetti devices: version checking, download (encrypted and unencrypted), BLE local OTA transfer, cloud/remote MQTT-triggered upgrades, broadcast upgrades to multiple sub-devices, upgrade ordering strategies, and server-side upgrade record reporting.

## Firmware Update Flow

Source files: `DeviceUpgradeBaseActivity.java`, `DeviceVersionModel.java`, `DeviceVersionRepository.java`, `FirmwareDownloadViewModel.java`, `FirmwareDownloadRepository.java`, `FirmwareUpgradeConfig.java`, `FirmwareUpgradeOrder.java`, `FmUpgradeStrategy.java`, `DeviceFmVer.java`, `DeviceSoftwareVerResp.java`, `FirmwareVerReq.java`, `FirmwareVerItemBean.java`, `DeviceFirmware.java`, `ProtocolParse.java`, `ConnectManager.java`, `OTAGroup.java`, `UpgradeStatus.java`, `SmartProductService.java`, `DeviceConnUtilKt.java`, `OtaUtil.java` (both `lib_ble` and app copy), `DeviceUpgradeBroadcastBean.java`, `BootUpgradeSupport.java`, `DeviceNodeOTAStatusItem.java`, `FirmwareDetection.java`.

Two primary upgrade paths exist: **BLE local** (app downloads firmware, sends it over BLE to the device) and **Cloud/Remote** (app triggers server, server sends MQTT command to device, device fetches firmware over Wi-Fi). The app can also do **broadcast upgrades** to push firmware to multiple sub-devices simultaneously (e.g., parallel battery packs).

### Step 1 — Version Check

The app sends the device's current firmware state to the server, which responds with available updates. Five API versions exist, growing in capability. In v3.0.9, the batch endpoint was bumped from v2 to v3 (the old v2 endpoint is deprecated). All are defined in `SmartProductService.java`:

| Endpoint                                                                 | Return Type                                 | Purpose                |
| ------------------------------------------------------------------------ | ------------------------------------------- | ---------------------- |
| `POST /api/blusmartprod/device/firmware/v1/latest/firmwareVerList`       | `BaseResponse<List<DeviceFmVer>>`           | Single device (legacy) |
| `POST /api/blusmartprod/device/firmware/v1/latest/firmwareVerList/batch` | `BaseResponse<List<DeviceSoftwareVerResp>>` | Multi-device batch v1  |
| `POST /api/blusmartprod/device/firmware/v2/latest/firmwareVerList/batch` | `BaseResponse<List<DeviceSoftwareVerResp>>` | Multi-device batch v2  |
| `POST /api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch` | `BaseResponse<List<DeviceSoftwareVerResp>>` | Multi-device batch v3  |
| `POST /api/blusmartprod/device/firmware/v3/latest/firmwareVerList`       | `BaseResponse<DeviceSoftwareVerResp>`       | Single device v3       |

Each endpoint uses a **different `gwcredentials` query parameter** — these are hardcoded static strings in `SmartProductService.java`:

- `firmwareVerList`: `"46qdFOnnZBoUxpEDVl/MSP0RDCe0PJGdAedIYCokg793SQddlu++dMJoaFLrexKdB6Y9Tk24XbWes5rcDHasgzZGEmQ+9f2FZqH0Jrm8Ltc="`
- `firmwareVerListV3`: `"Jlm47JC5ddystdOYeOTR/8aCmnE3m55fDg5lKJQhp7GaBgiKPr9hiYpKqrsqpmurlBZKHyX5p3WfIQ2ekJQZaXTe99qUY0d8rIgKyOXb0nw="`
- `firmwareVerListBatch / firmwareVerListBatchV2`: `"osUZ8ygqt1s/awsURLTwupGKN/CH8sRRODw/lZLlrv49jdBtu7UuRqxUkYHH6jWswlLPybPJ2WShH/r928K10amSgY0pWE2+eeijxYovV9DIcRgwZhBbSQ=="`

These are Base64-encoded authentication/authorization tokens for the API gateway.

**Request body** (`FirmwareVerReq` in `FirmwareVerReq.java`):

```json
{
  "sn": "<device serial number>",
  "model": "<model code, e.g. AC2A>",
  "iotVer": 0,
  "armVer": 0,
  "dspVer": 0,
  "bmsVer": 0,
  "mobileId": "<phone ID>",
  "firmwareVers": [
    { "firmwareId": 0, "ver": 1234 }
  ]
}
```

For **batch requests**, the body is a `List<Map<String, Object>>` where each map has `"sn"`, `"model"`, `"firmwareVers"` (list of `{"firmwareId", "ver"}` maps), and for battery packs: `"masterDeviceModel"`. The `firmwareId` integers map to the `DeviceFirmware` enum (see Firmware Component Types, below).

**Response** — batch endpoints return `List<DeviceSoftwareVerResp>` where each item contains `model` (String), `sn` (String), and `versions` (List<DeviceFmVer>). The V2 single-device endpoint returns `List<DeviceFmVer>` directly.

The app determines if a new version is available via `DeviceConnUtilKt.deviceFmNewVersionAvailable(oldVer, newVer)` which compares version strings numerically, ensuring the part number prefix matches.

**HTTP call chain:** `Activity` → `DeviceVersionModel.kt` (ViewModel/LiveData) → `DeviceVersionRepository.kt` → `SmartProductService.kt` (Retrofit).

### Firmware Component Types (`DeviceFirmware` enum)

Defined in `DeviceFirmware.java` / `ConnectConstants.kt`. The `firmwareId` is the integer value.

| ID  | Name              | Description               | ID  | Name                                                                    | Description            |
| --- | ----------------- | ------------------------- | --- | ----------------------------------------------------------------------- | ---------------------- |
| 0   | IOT               | IoT/WiFi module           | 13  | RF                                                                      | RF module              |
| 1   | ARM               | Main ARM processor        | 14  | DC_HUB                                                                  | DC hub                 |
| 2   | DSP               | DSP chip                  | 15  | AC_HUB                                                                  | AC hub                 |
| 3   | BMS               | Battery management system | 16  | DC_DC                                                                   | DC-DC converter        |
| 4   | BA                | Battery array             | 17  | ATS                                                                     | Auto transfer switch   |
| 5   | PACK_BCU          | Battery pack BCU          | 18  | PANEL                                                                   | Solar panel controller |
| 6   | PACK_BMU          | Battery pack BMU          | 19  | PARALLEL_BOX                                                            | Parallel box           |
| 7   | PACK_BMS          | Battery pack BMS          | 20  | INV_DSP2                                                                | Second inverter DSP    |
| 8   | PACK_M1           | Pack M1                   | 11  | HMI1 / HMI_BOOT / HMI_KERNEL / HMI_FILE_SYS / HMI_APP_UI / HMI_APP_BASE | Display sub-components |
| 9   | PACK_SAFETY       | Pack safety               | 253 | PPS                                                                     | PPS                    |
| 10  | PACK_HIGH_VOLTAGE | Pack high voltage         | 254 | BOOT                                                                    | Bootloader             |
| 12  | HMI2              | Second display            | 255 | SYSTEM                                                                  | System                 |

**HMI sub-components** (all share firmwareId 11): HMI_BOOT, HMI_KERNEL, HMI_FILE_SYS, HMI_APP_UI, HMI_APP_BASE. These represent different partitions of the display firmware.

**Boot firmware detection:** `DeviceFmVer.isBootVer()` returns true if the version string length > 6 and characters at positions 5–6 are `"00"`, indicating the firmware targets the bootloader.

### Step 2 — Server Response (`DeviceFmVer`)

The server returns one `DeviceFmVer` object per firmware component. Key fields (from `DeviceFmVer.java`):

| Field                     | Type              | Meaning                                                                                                         |
| ------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------- |
| `firmwareType`            | int               | Component ID (from DeviceFirmware enum)                                                                         |
| `version`                 | String            | Target version string                                                                                           |
| `currVersion`             | long              | Device's current version (echoed back)                                                                          |
| `hasNewVersion`           | bool              | `true` if an update is available                                                                                |
| `downloadUrl`             | String            | Direct URL to download the binary (for unencrypted firmware)                                                    |
| `fileMd5`                 | String            | MD5 checksum for post-download integrity check                                                                  |
| `fileSize`                | int               | File size in bytes                                                                                              |
| `encrypted`               | bool              | Whether the firmware file is encrypted                                                                          |
| `signature`               | String            | Firmware signature — sent as final OTA packet                                                                   |
| `checkSum`                | String            | Additional checksum field                                                                                       |
| `shardSize`               | int               | Chunk size in bytes for BLE transfer (from `X-Shard-Size` header for encrypted firmware, else defaults to 1024) |
| `supportBroadcastUpgrade` | bool              | Can be pushed to multiple sub-devices at once via broadcast OTA                                                 |
| `needToReconnect`         | bool              | Device requires BLE reconnect after flashing                                                                    |
| `versionList`             | List<DeviceFmVer> | Sub-components (e.g. HMI has BOOT/KERNEL/APP parts with individual version info)                                |
| `upgradeStrategy`         | String            | Upgrade strategy identifier (e.g., `"ARM_LAST"`)                                                                |
| `firmwareId`              | String            | Firmware identifier string                                                                                      |
| `sn`                      | String            | Target device serial                                                                                            |
| `model`                   | String            | Target device model                                                                                             |

### Step 3 — Firmware Download

#### Download URL Construction

**Unencrypted firmware:** Uses `downloadUrl` from the API response directly. This is a fully-qualified or relative URL pointing to the firmware binary.

**Encrypted firmware:** Uses a URL constructed in `DeviceUpgradeBaseActivity.java:741-743` with a **hardcoded `gwcredentials` token**:

```
/api/blusmartprod/device/firmware/encrypted/v1/download
    ?sn=<deviceSn>
    &fm=<firmwareId>
    &gwcredentials=7plHLMKU7rc92SATG1brZp2WOKG/MVcwDP0jDucHdG9fYoM1ZNjGlCpCtENCnlYuCJWRZ0wiwB0E5hg4W525F5mBTDiZKrCBqjg6L5vLmeM=
```

This credential is stored as constant `FIRMWARE_DOWNLOAD_GWCREDENTIALS` in `SmartProductService.java:69`. The full URL is appended to `EnvManager.getBaseUrl()` (e.g., `https://gw.bluettipower.com`).

The encrypted download response contains firmware metadata in **HTTP response headers** (not in the body):

- `X-Shard-Size` → stored as `firmware.shardSize` (chunk size for BLE OTA transfer)
- `X-Signature` → stored as `firmware.signature` (sent as the final packet in OTA transfer)
- `X-Checksum` → stored as `firmware.fileMd5` (MD5 checksum for validation)

#### Download Execution

The download is managed through `FirmwareDownloadViewModel` → `FirmwareDownloadRepository`, using Kotlin coroutines and `Flow<DownloadStatus>`. The download streams the firmware binary to a cache file and returns progress updates.

**Flow:**

1. `DeviceUpgradeBaseActivity.firmwareDownload(firmware, showSuccessTips, showLoading)` is called
1. A new file is created via `FirmwareDownloadViewModel.newFirmwareFile()`
1. The download URL is constructed (if encrypted, using the hardcoded endpoint)
1. A coroutine launches that calls `downloadVM.download(url, IDownloadBuild)`, collecting a `Flow<DownloadStatus>`
1. On `DownloadSuccess`, response headers are parsed for encrypted firmware metadata
1. `firmware.setDownload(true)` triggers the callback

#### File Naming and Storage

**File location:** App's cache directory (`context.getCacheDir()`).

**File naming convention** (`FirmwareDownloadViewModel.java:59-69`):

```
{modelCode}_{firmwareTypeName}_{version}_{firmwareId}
```

Example: `AC200L_IOT_v9001.00_abc123`

The `firmwareTypeName` is resolved from `ConnectConstantsKt.getFirmwareTypeName(firmwareType)`.

#### Cache Validation

`FirmwareDownloadViewModel.isFirmwareFileExits()` checks:

- The file exists on disk
- If `fileMd5` is present, verifies the file's MD5 hash matches
  If both pass, the cached file is reused without re-downloading.

### Step 4A — Delivery to Device via BLE (Local OTA)

This is the primary path when the phone is connected to the device via Bluetooth.

#### OTA Start Command

`ProtocolParse.otaStartCmd(firmware, deviceModel, protVer, otaType, idOfGroup, fmCount, modbusSlave)` builds the hex command string to initiate OTA.

**For protocol ≥ 2000 (V2):** Uses register address `700` (`0x02BC`):

```
{modbusSlave} 10 02BC 0006 0C {otaType} {fmType} {version_le32} {fileSizeKb} {otaGroup} {idOfGroup} CRC
```

- `modbusSlave`: 1 normally, 0 for 2nd-gen IoT
- `otaType`: 1 (normal), 3 (broadcast)
- `version`: 4 bytes little-endian
- `fileSizeKb`: `ceil(fileSize / 1024)`
- `otaGroup`: from `DeviceConnUtilKt.deviceFmOtaGroup(fmType, model)`
- `idOfGroup`: 255 for broadcast, null for normal

**For protocol < 2000 (V1):** Uses register address `1080` (`0x0438`, `OTA_START` in `ProtocolAddr`):

```
01 10 0438 <dataLen> <params> CRC
```

Where `<params>` varies by device model — e.g., for AC240/AC240P/AC200L/AC200PL:

```
00 05 0A {fmType} 0000 {idOfGroup} 0000 {fileSizeKb}
```

And for other models: `0002 04 {fmType} 0000`.

#### OTA Initiation

In `ConnectManager.otaRequest(firmwareBean, callback, isRemote)`:

1. Sets `isOTA = true`, stores firmwareBean
1. For BLE mode: Sends the OTA start command via `addTaskItem()` as a `BleTaskItem`
1. For remote mode: Returns immediately (server triggers upgrade via MQTT)
1. Up to 3 retries (`otaRequestCount`) on OTA start failure

#### OTA Data Transfer

Once the device acknowledges the OTA start (response `"43"`), data transfer begins. `ConnectManager.getOTAFileData(index)`:

1. **First call:** Reads the entire firmware file into memory via `OtaUtil.fileToByteArray()`
1. **Total packs calculation:**
   - Encrypted: `ceil(fileSize / shardSize) + 1` (the +1 is the signature packet)
   - Non-encrypted: `ceil(fileSize / 1024)`
1. **Per-packet construction:** Each packet is wrapped as:
   ```
   {type}{index}{checkIndex}{hexData}{CRC16_XMODEM}
   ```
   - `type`: `"A1"` for encrypted data packets, `"A2"` for signature packet (last), constant for non-encrypted
   - `index`: packet index (0–255, wrapped)
   - `checkIndex`: `255 - index`
   - `hexData`: the chunk of firmware bytes
   - `CRC16_XMODEM`: checksum of the frame
1. **ESP32 encrypted devices:** The entire wrapped packet is additionally AES-CBC encrypted with `bleConnShareKey` before BLE transmission.

#### OTA Response Handling

Device responses over BLE (`ConnectManager.otaDataChange(result)`):

- `"43"` — OTA start acknowledged → begin data transfer (`otaPackIndex = 1`)
- `"06"` — Packet acknowledged → increment index, write next packet
- `"15"` — NAK (negative acknowledge) → retry up to 10 times with 200ms delay
- `"18"` or `"1818"` or `"01 81 01 81 90"` — OTA write complete
  - For portable/charger/hub devices (non-cloud, non-IOT): starts polling timer for OTA status
  - Otherwise: immediately notifies `onUpgradeComplete()`

**Progress reporting:** `updateProgress(default, currentPack, totalPacks)` reports percentage. Reaches 100% when all packs are sent.

**Error handling:** `BleOtaCallback.onUpgradeFailed(error, errCode)` with error types: `FILE_TOO_LARGE`, `FILE_ERROR`, `CANCEL`, `TIMEOUT`, `OTHER`. A 15-second OTA status countdown timer retries up to 3× before declaring a timeout failure.

### Step 4B — Cloud / Remote OTA (MQTT-Based)

Used when the device is connected to the internet via Wi-Fi and the app is not in local BLE range.

**API endpoint:** `POST /api/blusmartprod/device/firmware/v2/appSentDeviceRemoteUpgrade`

**Request body** (constructed in `DeviceUpgradeBaseActivity.callRemoteUpgrade()`):

```text
{
  "masterSn": "<master device serial>",
  "model": "<master device model>",
  "request": [{
    "sn": "<target device sn>",
    "model": "<target device model>",
    "firmwareVers": [{
      "firmwareId": <firmwareType>,
      "ver": <currentVersion>
    }]
  }]
}
```

The cloud receives this request and sends an **MQTT command** to the device, instructing it to fetch and apply firmware autonomously over its own internet connection. The app then:

1. Calls `firmwareUpgrade(firmware, isRemote=true)` — skips local file path setup, does NOT build OTA start command
1. Delays 3000ms, then starts `otaStatusCountDown` timer
1. Polls OTA status via BLE/MQTT
1. Up to 3 retries

**AECC devices** use a separate endpoint:

```
POST /api/blusmartprod/device/firmware/v1/aeccSentDeviceRemoteUpgrade
```

### Broadcast Upgrade

When `DeviceFmVer.supportBroadcastUpgrade` is `true`, a single OTA command can push firmware to multiple connected sub-devices simultaneously (e.g., parallel battery packs in a stack).

- **OTA type:** `3` (vs `1` for normal)
- **Group ID:** `255` (broadcast to all sub-devices in the group)
- **Record saving:** Uses `upgradeRecordBroadcastSave()` instead of `upgradeRecordSave()`, returning a `DeviceUpgradeBroadcastBean` with `recordId`
- **Per-node tracking:** `List<DeviceNodeOTAStatusItem>` tracks each sub-device's status (`otaStatus`, `errorCode`, `softwareVer`, `sn`, `modelNumber`)
- **UI:** `DeviceOTAStatusDialog` shows live progress with per-node status during multi-device upgrades

### OTA Groups

`OTAGroup.java` enum maps firmware types to OTA groups, which determine the target device subsystem:

| Group           | Value | Firmware Types                                                                   |
| --------------- | ----- | -------------------------------------------------------------------------------- |
| INV             | 1     | ARM, DSP, INV_DSP2, AC_HUB, DC_HUB                                               |
| PACK            | 2     | PACK_BCU, PACK_BMU, PACK_BMS, PACK_M1, PACK_SAFETY, PACK_HIGH_VOLTAGE, DC_DC, BA |
| IOT             | 3     | IOT, HMI1, HMI2, RF                                                              |
| LCD             | 4     | EPAD HMI1                                                                        |
| ATS             | 5     | ATS, AT1 IOT                                                                     |
| PANEL           | 6     | PANEL, EPANEL                                                                    |
| DCDC_OR_CHARGER | 7     | D400S                                                                            |
| WT              | 8     | WT                                                                               |
| S1              | 9     | S1                                                                               |

Group mapping is defined in `DeviceConnUtilKt.deviceFmOtaGroup(fmType, model)`.

### Step 5 — Upgrade Order and Strategy

Multiple firmware components are flashed **sequentially** in a device-model-specific order.

#### Configuration Classes

- **`FirmwareUpgradeConfig.java`** — Singleton defining upgrade order per device model
- **`FirmwareUpgradeOrder.java`** — Data class with three fields:
  - `invOrder` (List<Integer>) — Order for inverter firmware types
  - `packOrder` (List<Integer>) — Order for battery pack firmware types
  - `delays` (Map\<Integer, Long>) — Optional delays in ms between firmware upgrades
- **`FmUpgradeStrategy.java`** — Enum with two strategies:
  - `DEFAULT` — Uses both `invOrder` and `packOrder` as defined below
  - `ARM_LAST` — Custom order: `IOT(0) → DSP(2) → BMS(3) → ARM(1)`

#### Default Orders

**Inverter order** (including AC2A, AC200L, AC240, etc.):

```
IOT (0) → ARM (1) → DSP (2) → BMS (3) → DC_DC (16)
```

**Pack/battery order:**

```
PACK_SAFETY (9) → PACK_BMU (6) → PACK_HIGH_VOLTAGE (10) → DC_DC (16) → PACK_BCU (5) → PACK_BMS (7)
```

**POWER5 exception** (`ARM_LAST` strategy):

```
IOT (0) → DSP (2) → BMS (3) → ARM (1)
```

ARM is flashed last on the POWER5, presumably because other components must be stable before the main processor firmware is replaced. No other device model has a special strategy — `DeviceModel.POWER5` is the only one with a custom configuration (`FirmwareUpgradeConfig.java:33`).

### Boot Upgrade

**`BootUpgradeSupport.java`** contains flags for bootloader upgrade support:

- `isSupport` (int) — Whether boot upgrade is supported
- `softwareVerTotal` (int) — Number of software versions in the boot binary

**V2 Modbus registers** (new in v3.0.9):

| Register | Constant               | Description                 |
| -------- | ---------------------- | --------------------------- |
| 29770    | `BOOT_UPGRADE_SUPPORT` | Boot upgrade support status |
| 29772    | `BOOT_SOFTWARE_INFO`   | Boot software version info  |

**`DeviceUpgradeBootActivity.java`** is a minimal activity (`extends BaseConnActivity`) providing boot-specific upgrade UI. It extends the base connection activity but is essentially a shell — the actual boot upgrade logic reuses the standard firmware upgrade flow.

### Step 6 — Upgrade Record (Server Reporting)

After each upgrade attempt, the app reports back to the server. The flow is handled in `DeviceUpgradeBaseActivity.callSaveUpgradeRecord()`.

#### API Endpoints

| Endpoint                                                        | gwcredentials?                     | Purpose                                       |
| --------------------------------------------------------------- | ---------------------------------- | --------------------------------------------- |
| `POST /api/blusmartprod/device/upgrade/record/v1/save`          | Yes (`"ZFKVIQwNyA4BKtXPEMlMJ..."`) | Standard upgrade record                       |
| `POST /api/blusmartprod/device/upgrade/record/v1/broadcastSave` | No                                 | Broadcast upgrade record (returns `recordId`) |

#### UpgradeStatus Enum

| Status    | Value |
| --------- | ----- |
| FAILURE   | 0     |
| SUCCESS   | 1     |
| UPGRADING | 2     |

#### Record Save Flow (Two-Phase)

**Phase 1 — UPGRADING** (called before OTA begins):
The app sends a map with:

- `deviceSn`, `deviceModel`, `firmwareType`
- `oldVer` (current version, long), `upgradeVer` (target version)
- `appVer` (Android app version)
- `upgradeStatus`: `"upgrading"` (lowercased)
- `connMode`: 1 (BLE) or cloud mode
- `remark` (optional description)
- `soc` (battery state of charge at upgrade time, from home data)
- For broadcast: returns `recordId` from the response
- For standard: returns `recordId` directly

**Phase 2 — SUCCESS/FAILURE** (called after OTA completes):
The app sends a record update with:

- `recordId` (from Phase 1 response)
- `remark` (error description if failed, or empty string if success)
- `upgradeStatus`: `"success"` or `"failure"`
- `firmwareUpgradeProgressVoList`: optional list of `DeviceNodeOTAStatusItem` for multi-device upgrades

**Auto-included fields** (by the service layer, not in the request body map):

- `mobileModel`: `Build.BRAND + " " + Build.MODEL` (e.g., "Samsung SM-S908B")
- `os`: 2 (Android)
- `osVer`: `Build.VERSION.RELEASE` (e.g., "13")
- `upgradeType`: 1 (for broadcast save only)

#### Error Remark Mapping

`DeviceUpgradeBaseActivity.getRecordRemarkText(errCode)` maps OTA error codes to human-readable remark strings for the upgrade record.

### Complete End-to-End Flows

#### BLE Local Upgrade Flow

```
1. VERSION CHECK
   Activity.getFirmwareVersion()
   → DeviceVersionModel.firmwareVerListBatchV2(requestMapList)
   → POST /api/blusmartprod/device/firmware/v3/latest/firmwareVerList/batch?gwcredentials=...
   ← List<DeviceSoftwareVerResp> (each with model, sn, List<DeviceFmVer>)

2. USER SELECTS FIRMWARE
   - UI displays DeviceFmVer list with hasNewVersion flags
   - User picks which component to upgrade

3. FIRMWARE DOWNLOAD
   DeviceUpgradeBaseActivity.firmwareDownload(firmware)
   → If encrypted: builds encrypted download URL with gwcredentials
   → FirmwareDownloadViewModel.download(url, build)
   → Saves to cache: {cacheDir}/{modelCode}_{type}_{version}_{firmwareId}
   → Reads X-Shard-Size, X-Signature, X-Checksum from response headers
   → MD5 validation pass → setDownload(true)

4. OTA INITIATION
   DeviceUpgradeBaseActivity.firmwareUpgrade(firmware, isRemote=false)
   → Sets localFilePath
   → Builds OTA start command: ProtocolParse.otaStartCmd(...)
   → callSaveUpgradeRecord(UPGRADING) — registers upgrade start on server
   → ConnectManager.otaRequest(firmware, callback, false)
     → Sends OTA start hex command over BLE

5. OTA DATA TRANSFER
   Device responds "43" = OTA ready
   → App reads entire firmware file into memory
   → For each packet (index 1..totalPack):
     - Extracts chunk: OtaUtil.getOtaPack(data, index, shardSize)
     - Wraps in: {type}{index}{checkIndex}{hexData}{CRC16_XMODEM}
     - If ESP32 encrypted: AES-CBC encrypt with bleConnShareKey
     - Sends over BLE write characteristic
     - Device responds "06" (ACK) → next packet
     - Device responds "15" (NAK) → retry up to 10× with 200ms delay
   → Progress: updateProgress(percent) via BleOtaCallback

6. OTA COMPLETION
   Device responds "18" / "1818" / "01 81 01 81 90"
   → For non-cloud devices: polls OTA status register for verification
   → For cloud/IOT devices: immediate notification
   → BleOtaCallback.onUpgradeComplete()
   → callSaveUpgradeRecord(SUCCESS) — reports result to server

7. ERROR HANDLING
   BleOtaCallback.onUpgradeFailed(error, errCode)
   → OTA start: up to 3 retries
   → Data packets: up to 10 retries per NAK
   → 15-second status countdown with 3 total retries
   → callSaveUpgradeRecord(FAILURE, errorDescription)
```

#### Cloud/Remote (MQTT) Upgrade Flow

```
1. REMOTE TRIGGER
   DeviceUpgradeBaseActivity.callRemoteUpgrade(firmware, masterSn, masterModel, snList)
   → DeviceVersionModel.remoteUpgrade(masterSn, model, request)
   → POST /api/blusmartprod/device/firmware/v2/appSentDeviceRemoteUpgrade
      Body: {masterSn, model, request: [{sn, model, firmwareVers: [{firmwareId, ver}]}]}

2. SERVER → DEVICE via MQTT
   Server sends MQTT command to the device
   Device downloads and flashes firmware autonomously over Wi-Fi

3. STATUS POLLING
   App starts otaStatusCountDown timer (15-second intervals)
   Delays 3000ms before calling connMgr.startTimer()
   Polls OTA status from device via BLE/MQTT
   Up to 3 retries on timeout
```

### Firmware Version Formatting

`DeviceConnUtilKt.deviceFmVerFormat(fmVer)` formats raw version values for display:

- Versions with >6 characters: splits as `{first5}.{chars5-6}.{rest}` → e.g., `v90010.00.123`
- Versions with >4 characters (≤6): splits as `{first4}.{rest}` → e.g., `v9001.00`
- Otherwise: plain prefix → e.g., `v100`
