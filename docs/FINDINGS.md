# Bluetti Android APK — Reverse Engineering Findings

**Package:** `net.poweroak.bluetticloud`
**Latest version analyzed:** 3.0.9 (versionCode 1415)
**Min SDK:** 26 (Android 8.0 Oreo)
**Target SDK:** 35 (Android 15)
**Compiled SDK:** 35
**Decompiled with:** apktool 2.7.0, jadx 1.5.5 (44 of 23,012 classes failed to decompile)

### Automated Setup (mise tasks)

The APK download and decompilation is fully automated via [mise](https://mise.en.dev) tasks. One-time setup:

```
mise install          # installs java + jadx (also runs `mise install` for existing python/ruff/uv)
```

Each APK version is stored in its own subdirectory under `bluetti-files/`:

```
bluetti-files/
  BLUETTI-v3.0.9.apk/
    bluetti.apk       # the downloaded APK
    jadx_out/          # jadx-decompiled Java sources
    apktool_out/       # apktool-disassembled Smali + resources
```

Available tasks (all run under `bash`):

| Task | Command | Description |
|------|---------|-------------|
| `download-apk` | `mise run download-apk` | Fetches the APK URL from the download page's JavaScript (mimicking browser behavior) and downloads the latest APK to a versioned subdirectory. Idempotent — skips if that version is already downloaded. |
| `decompile-jadx` | `mise run decompile-jadx` | Decompiles all downloaded APK versions that haven't been decompiled yet with jadx. Self-heals jadx binary permissions if needed. |
| `decompile-apktool` | `mise run decompile-apktool` | Disassembles all downloaded APK versions that haven't been disassembled yet with apktool (Smali, resources, manifest). |
| `prepare-all` | `mise run prepare-all` | Downloads the latest APK, then runs both decompile tasks on all versions. |
| `cleanup` | `mise run cleanup` | Removes the entire `bluetti-files/` directory. |

Typical workflow: `mise run prepare-all` to download and decompile everything, then `mise run cleanup` when you want a fresh start. Multiple versions are kept and decompiled side-by-side for comparison.

The download script (`scripts/download-apk.mjs`) dynamically extracts the APK URL from the page's JavaScript, so it adapts if Bluetti changes their server URLs or credentials.

---

## 1. Permissions

The app declares 32 permissions (v3.0.9; was 34 in v3.0.8). Notable ones:

| Permission | Purpose / Risk |
|---|---|
| `BLUETOOTH`, `BLUETOOTH_ADMIN`, `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT` | BLE device discovery and communication |
| `NEARBY_WIFI_DEVICES` | Wi-Fi device pairing (declared `neverForLocation`) |
| `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` | Required for BLE scanning on older Android |
| `CAMERA` | QR code scanning (`QrCodeScanActivity`) |
| `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE` | Cloud connectivity |
| `FOREGROUND_SERVICE` | Background Bluetooth/MQTT service |
| `WAKE_LOCK`, `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, `SCHEDULE_EXACT_ALARM` | Keep IoT connection alive |
| `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO` | Media access for community posts **(removed in v3.0.9)** |
| `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE` | File access (legacy) |
| `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`, `VIBRATE` | Push notifications |
| `READ_LOGS` | **Sensitive** — reads system log buffer |
| `READ_PRIVILEGED_PHONE_STATE` | **Sensitive** — normally reserved for system/carrier apps |
| `KILL_BACKGROUND_PROCESSES` | Can terminate other apps |
| `FLASHLIGHT` | Torch during QR scan |
| `com.google.android.gms.permission.AD_ID` | Google advertising ID |
| `ACCESS_ADSERVICES_AD_ID`, `ACCESS_ADSERVICES_ATTRIBUTION` | Android Privacy Sandbox ad attribution |

**Component counts:** 387 Activities, 17 Services, 13 Broadcast Receivers, 5 Content Providers.

---

## 2. Backend Infrastructure

### 2.1 Environment Switching

The app contains a fully functional three-environment architecture controlled by `EnvManager` (`net.poweroak.bluetticloud.http.env.EnvManager`). The active environment defaults to **RELEASE** but can be toggled at runtime.

| Environment | Gateway URL |
|---|---|
| **RELEASE (default)** | `https://gw.bluettipower.com` |
| TEST | `https://test-gw.poweroak.ltd:18443` |
| DEV | `https://dev-gw.poweroak.ltd:18443` |

### 2.2 Production Service URLs

| Service | URL |
|---|---|
| API Gateway (primary) | `https://gw.bluettipower.com` |
| API Gateway (secondary/PRY) | `https://gwpry.bluettipower.com` |
| SSO / Auth | `https://sso.bluettipower.com` |
| H5 Frontend | `https://h5.bluettipower.com` |
| Community H5 | `https://h5.bluettipower.com/app/community/dist/index.html#/home` |
| After-Sales | `https://after-sales.bluettipower.com` |
| IoT/MQTT Broker | `ssl://iot.bluettipower.com:18760` |
| File (by ID) | `https://gw.bluettipower.com/api/midpfilec/file/v1/getFile?id=<id>` |
| App Download | `https://download.bluetti.app?sn=<sn>` |
| App Download (alternate) | `https://download.poweroak.ltd?sn=<sn>` |

### 2.3 Test / Dev Service URLs (also embedded in binary)

| Service | URL |
|---|---|
| Dev Gateway | `https://dev-gw.poweroak.ltd:18443` |
| Test Gateway | `https://test-gw.poweroak.ltd:18443` |
| Dev SSO | `http://dev-sso.poweroak.ltd:18888` (**HTTP — no TLS**) |
| Test SSO | `https://test-sso.poweroak.ltd:18443` |
| Dev H5 | `https://dev-app-h5.poweroak.ltd:18443` |
| Test H5 | `https://test-app-h5.poweroak.ltd:18443` |
| Dev IoT/MQTT | `ssl://dev-iot.poweroak.ltd:18760` |
| Test IoT/MQTT | `ssl://test-iot.poweroak.ltd:18760` |
| Dev After-Sales | `http://dev-after.poweroak.ltd:18888` (**HTTP — no TLS**) |
| Test After-Sales | `http://test-after.poweroak.ltd:18888` (**HTTP — no TLS**) |

---

## 3. API Endpoints (Retrofit Services)

The backend follows a microservice architecture. All endpoints are served under the gateway base URL. Each microservice has a `blu*` or `midp*` prefix.

### Authentication & User Accounts (`midpauthc`)
```
POST /api/midpauthc/user/mgt/register/v1
POST /api/midpauthc/user/mgt/forgotpwd/step1/v1
POST /api/midpauthc/user/mgt/forgotpwd/step2/v1
GET  /api/midpauthc/user/account/v1
POST /api/midpauthc/user/v1/update/password
POST /api/midpauthc/user/v1/update/mail/change
POST /api/midpauthc/user/v1/update/mail/verify
POST /api/midpauthc/user/v1/update/phone
POST /api/midpauthc/user/v1/update/phone/change
POST /api/midpauthc/user/v1/update/phone/verify
POST /api/midpauthc/user/v1/update/country
POST /api/midpauthc/user/v1/country/reset
POST /api/midpauthc/account/social/v1/bind
GET  /api/midpauthc/account/social/v1/list
POST /api/midpauthc/account/social/v1/unbind
POST /social/login
POST /api/logout
POST /accessToken
```

### Notifications & Captcha (`midpnc`)
```
POST /api/midpnc/captcha/send/v1
POST /api/midpnc/captcha/validate/v1
POST /api/midpnc/notify/push/device/v1/client-register
GET  /api/midpnc/notify/push/v1/user/unreadTotal
POST /api/midpnc/notify/push/v1/user/read
DELETE /api/midpnc/notify/push/v1/user/deleteNotify
GET  /api/midpnc/notify/push/message/v1/userNotify
GET  /api/midpnc/notify/push/v1/message/userNotify
```

### PKI / Certificates (`midppkic`)
```
POST /api/midppkic/cert/app/revoke
POST /api/midppkic/cert/app/v1/pfx
GET  /api/midppkic/cert/app/v2/now/utc-time
```

### File Management (`midpfilec`)
```
POST /api/midpfilec/file/pre/v1/apply
POST /api/midpfilec/file/pre/v1/upload
GET  /api/midpfilec/file/v1/getFile
POST /api/midpfilec/file/v1/upload
POST /api/midpfilec/file/v1/upload/multi
GET  /api/midpfilec/vod/v1/play-url
```

### Master Data / App Config (`midpmdata`)
```
GET  /api/midpmdata/app/version/v1/latest
GET  /api/midpmdata/app/attribute/v1/engineering-machine
GET  /api/midpmdata/dictionary/v1/app/lookup
GET  /api/midpmdata/master/v1/ver/checkLatest
GET  /api/midpmdata/iso/country/v1/localized/all-countries
GET  /api/midpmdata/iso/country/v1/localized/administrative-divisions
```

### Payment (`midppayc`)
```
GET  /api/midppayc/payment/v1/ability
POST /api/midppayc/payment/v1/create
GET  /api/midppayc/payment/v1/query
```

### Logistics / Geo / Weather (`midplifec`)
```
GET  /api/midplifec/api/logistics/v1/trackInfo
GET  /api/midplifec/express/v1/logisticsDetailList
GET  /api/midplifec/geo/v1/support-phone-registry
GET  /api/midplifec/meteo/v1/daily
POST /api/midplifec/meteo/v1/find
```

### IoT Device Management (`blusmartprod`)
```
POST /api/blusmartprod/device/basic/v2/bind
POST /api/blusmartprod/device/basic/v2/unbind
POST /api/blusmartprod/device/basic/v1/update
GET  /api/blusmartprod/device/basic/v1/findDeviceByBluetooth
GET  /api/blusmartprod/device/basic/v1/deviceRemoteSearch
POST /api/blusmartprod/device/basic/v1/updateUserDeviceInfo
POST /api/blusmartprod/device/basic/v1/updateEmissionRate
POST /api/blusmartprod/device/group/v1/updateDeviceSortData
GET  /api/blusmartprod/device/basic/v1/shareGroupMemberList
DELETE /api/blusmartprod/device/basic/v1/delShareMember
GET  /api/blusmartprod/device/basic/v1/getQrCodeEncrypt
GET  /api/blusmartprod/device/group/v1/homeDevices
GET  /api/blusmartprod/device/group/v1/findDevicePage (v1/v2/v3)
POST /api/blusmartprod/device/group/v1/deviceTop
GET  /api/blusmartprod/device/group/v1/findParallelDevice
POST /api/blusmartprod/device/group/v1/parallel/create
POST /api/blusmartprod/device/group/v1/parallel/sendParallelCmd
POST /api/blusmartprod/device/group/v1/parallel/unbind
GET  /api/blusmartprod/device/firmware/v1/latest/firmwareVerList/batch (v1/v2/v3)
POST /api/blusmartprod/device/firmware/v1/appSentDeviceRemoteUpgrade
POST /api/blusmartprod/device/firmware/v1/aeccSentDeviceRemoteUpgrade
GET  /api/blusmartprod/device/model/v1/detail (v1/v2)
GET  /api/blusmartprod/device/model/v1/category
GET  /api/blusmartprod/device/manual/v1/getManual
GET  /api/blusmartprod/device/deviceAlarm/v1/queryDeviceAlarm
POST /api/blusmartprod/device/deviceAlarm/v1/handlingAlarm
POST /api/blusmartprod/device/batteryAgingMaintenance/v1/handleAging
GET  /api/blusmartprod/device/scene/v1/getAeccBindDeviceList
POST /api/blusmartprod/device/scene/v2/createScene
POST /api/blusmartprod/device/scene/v1/sceneAddDevice
POST /api/blusmartprod/device/scene/v1/sceneUnbindDevice
POST /api/blusmartprod/device/upgrade/record/v1/save
POST /api/blusmartprod/user/space/v1/createSpace
GET  /api/blusmartprod/user/space/v1/getSpaceDeviceList
POST /api/blusmartprod/user/space/v1/spaceAddDevice
POST /api/blusmartprod/user/space/v1/shareSpace
GET  /api/blusmartprod/aecc/workMode/v1/getWorkMode
POST /api/blusmartprod/aecc/workMode/v1/setWorkMode
POST /api/blusmartprod/aecc/workMode/v1/addCustomPlan
GET  /api/blusmartprod/aecc/advancedSetting/v1/getSettings
POST /api/blusmartprod/aecc/advancedSetting/v1/saveSetting
POST /api/blusmartprod/aecc/advancedSetting/v1/resetToDefault
GET  /api/blusmartprod/aecc/command/v1/querySystemPowerData
GET  /api/blusmartprod/vpp/v1/programs
POST /api/blusmartprod/vpp/v1/enrollment
GET  /api/blusmartprod/vpp/v1/dispatches
POST /api/blusmartprod/vpp/site/v1/create
```

### IoT Telemetry Data (`bluiotdata`)
```
GET  /api/bluiotdata/aecc/v1/getDeviceRealTimeData
GET  /api/bluiotdata/aecc/v1/getDeviceBatteryDetailData
GET  /api/bluiotdata/aecc/v1/getDevicePvDetailData
GET  /api/bluiotdata/aecc/v1/getDeviceLoadDetailData
GET  /api/bluiotdata/aecc/v1/getDeviceGridDetailData
GET  /api/bluiotdata/aecc/v1/getDeviceAlarmList
GET  /api/bluiotdata/dashboard/v2/getDeviceEnergyStatistics
GET  /api/bluiotdata/dashboard/v2/getDevicePowerStatistics
GET  /api/bluiotdata/dashboard/v1/getElectricCostSaveStatistics
GET  /api/bluiotdata/dashboard/v1/getSocChangeList
POST /api/bluiotdata/dashboard/v1/exportDeviceEnergyStatistics
GET  /api/bluiotdata/realtime/v1/getDeviceLastAlive
GET  /api/bluiotdata/device/iotData/v1/blackout/stats
POST /api/bluiotdata/device/iotData/v1/blackout/clear
GET  /api/bluiotdata/device/openWeatherAlert/v1/queryDeviceWeatherNoticePage
GET  /api/bluiotdata/device/openWeatherAlert/v1/queryDisasterDeviceBackupPowerPage
```

### Dynamic Electricity Pricing / VPP (`bluiotvpp`)
```
GET  /api/bluiotvpp/dynamicElectricityPrice/user/v1/dyEpEnabled
GET  /api/bluiotvpp/dynamicElectricityPrice/user/v1/dyEpStatus
GET  /api/bluiotvpp/dynamicElectricityPrice/user/v1/costStatistics
GET  /api/bluiotvpp/dynamicElectricityPrice/user/v1/aiCostStatistics
GET  /api/bluiotvpp/dynamicElectricityPrice/user/v1/policyInformationDownApp
POST /api/bluiotvpp/dynamicElectricityPrice/user/v1/policyInformationUp
```

### User Center (`bluuc`)
```
GET  /api/bluuc/uc/v1/basic/get
POST /api/bluuc/uc/v1/basic/update/{userId}
POST /api/bluuc/uc/v1/basic/update/avatar/{userId}
POST /api/bluuc/uc/v1/basic/closing
POST /api/bluuc/uc/v1/basic/updateExtendInfo
GET  /api/bluuc/uc/v1/address/list/paged
POST /api/bluuc/uc/v1/address/add
DELETE /api/bluuc/uc/v1/address/delete
POST /api/bluuc/uc/v3/address/update
POST /api/bluuc/push/v1/devices
POST /api/bluuc/push/v1/subscribe
GET  /api/bluuc/push/v1/topic/list
POST /api/bluuc/uc/v1/merchant/apply/applyMerchant
GET  /api/bluuc/uc/functionGrayscale/v1/checkFunction
```

### Community / Social (`blucomm`)
```
GET  /api/blucomm/community/home/v1/findNews
POST /api/blucomm/community/home/v1/saveComment
DELETE /api/blucomm/community/home/v1/delComment
POST /api/blucomm/community/endorseManager/v1/endorse
POST /api/blucomm/community/attention/v1/attentionOrNot
POST /api/blucomm/community/postLifeManager/v1/addPostLifeApp
GET  /api/blucomm/community/postLifeManager/v1/lifeListApp
POST /api/blucomm/posts/v1/create
POST /api/blucomm/posts/v1/upload
DELETE /api/blucomm/posts/v1/delete/{id}/{force_destroy}
GET  /api/blucomm/topic/v1/latestTopicsPage
GET  /api/blucomm/disUser/v1/getUserHomeInfo
POST /api/blucomm/disUser/v1/update/avatar
```

### E-commerce / Shop (`blushopc`)
```
GET  /api/blushopc/app/goods/v1/goodsDetail
GET  /api/blushopc/app/goods/v1/search
POST /api/blushopc/app/shopping/cart/v1/add
GET  /api/blushopc/app/shopping/cart/v1/query
POST /api/blushopc/app/checkout/v2/create
POST /api/blushopc/app/checkout/v2/payment
GET  /api/blushopc/app/order/v1/page
GET  /api/blushopc/app/order/v1/detail
POST /api/blushopc/app/order/refund/v1/create
GET  /api/blushopc/app/coupon/v1/page
POST /api/blushopc/app/coupon/v1/exchange
GET  /api/blushopc/app/customer/v1/level
POST /api/blushopc/app/birthday/gift/v1/claim
```

### After-Sales (`bluas`)
```
POST /api/bluas/afterSaleOrder/v1/apply
GET  /api/bluas/afterSaleOrder/v1/detail
POST /api/bluas/afterSaleOrder/v1/evaluate
GET  /api/bluas/faq/v1/faqCategoryList
GET  /api/bluas/faq/v1/findByCategoryId
GET  /api/bluas/deviceModelFault/v1/getFaultsByModel/{deviceModel}
POST /api/bluas/contactUs/v2/add
POST /api/bluas/installation/v1/installationBegins
GET  /api/bluas/user/v1/installationOrder/page
POST /api/bluas/user/v1/repairOrder/page
```

### Marketing / Banners / Wiki (`blumktc`)
```
GET  /api/blumktc/banner/v2/listBanner
GET  /api/blumktc/v1/config?version=v1
GET  /api/blumktc/wiki/v1/home
GET  /api/blumktc/wiki/v1/search
GET  /api/blumktc/wiki/v1/article
GET  /api/blumktc/app/config/v1/queryOpenAppConfig
POST /api/blumktc/app/config/v1/rating/good
POST /api/blumktc/push/task/v1/read
DELETE /api/blumktc/push/task/v1/delete
POST /api/blumktc/referral/v1/checkCode
POST /api/blumktc/marketing/recovery/v1/createRecoveryOrder
GET  /api/blumktc/marketing/recovery/v1/getRecoveryCountry
POST /api/blumktc/subscribe/v1/customerSubscribe
```

### Loyalty / Bluetti Bucks (`blubucksc`)
```
GET  /api/blubucksc/bucksApi/query/v1/summary
GET  /api/blubucksc/bucksApi/query/v1/journal
POST /api/blubucksc/bucksApi/pointsEarn/v1/sign
GET  /api/blubucksc/bucksApi/query/v1/signInfo
```

### Distribution / Partners (`bludistc`)
```
POST /api/bludistc/app/order/v1/add
GET  /api/bludistc/app/order/v1/paged
POST /api/bludistc/app/orderReturn/v1/add
GET  /api/bludistc/app/pay/v1/allowedPayTransaction
POST /api/bludistc/app/pay/v1/thirdPartyPayment/order
GET  /api/bludistc/app/taxExempt/v1/paged
```

### Financial / Transactions (`blufic`)
```
GET  /api/blufic/fic/app/transaction/v1/page
POST /api/blufic/fic/app/withdrawal/v1/add
GET  /api/blufic/fic/app/bankCard/v1/info
GET  /api/blufic/fic/app/distributor/v1/accountStats
```

### Installation Services (`bluinstp`)
```
POST /api/bluinstp/app/order/v2/add
GET  /api/bluinstp/app/order/v2/page
GET  /api/bluinstp/app/device/v1/overview
```

### Learning / Video (`bluelearn`)
```
GET  /api/bluelearn/app/videoClassify/v1/classifications
GET  /api/bluelearn/app/videoClassify/v1/getAppVideos
GET  /api/bluelearn/app/videoClassify/v1/countrys
```

---

## 4. IoT Communication — MQTT over SSL/TLS

The app uses Eclipse Paho MQTT client (`org.eclipse.paho.client.mqttv3`) for real-time device communication.

- **Broker (prod):** `ssl://iot.bluettipower.com:18760`
- **Transport:** TLS with optional mutual TLS (mTLS) via client certificates
- **Certificate source:** Client certificates are fetched from `/api/midppkic/cert/app/v1/pfx` (PKCS#12) and stored locally; the `MqttManager` loads them via `SSLHelper` using BouncyCastle
- **`certPassword` field** is set dynamically at runtime (not hardcoded)
- **Reconnect logic:** Exponential backoff with `ScheduledExecutorService`

---

## 5. Bluetooth (BLE) Communication

- BLE is used for local device pairing, provisioning, and control (when not on Wi-Fi)
- Encrypted BLE channel: `ConnectManager.bleEncryptedHandle` uses AES-CFB/NoPadding (`net.poweroak.lib_base.utils.AesExtKt`)
- Keys are negotiated per-session (not hardcoded)
- Device discovery by Bluetooth uses `/api/blusmartprod/device/basic/v1/findDeviceByBluetooth`

---

## 6. Encryption Architecture

### AES Utility (`AesExtKt`)
- Default cipher: **AES/CFB/NoPadding**
- Also supports: AES/CBC, AES/CTR
- Used for: BLE payload encryption, firmware file encryption

### Request Encryption Interceptor (`RequestEncryptInterceptor`)
An OkHttp interceptor exists that intercepts all requests to the Bluetti gateway. The actual encryption logic contains **Chinese placeholder comments** ("这里调用加密的方法，自行修改" — "Call the encryption method here, modify yourself"), indicating the request-level encryption was scaffolded but may not be fully activated in this build, or the encryption is handled by a native library not visible in the Java layer.

### MQTT TLS
mTLS with PKCS#12 client certificates obtained from the PKI service.

---

## 7. Hardcoded Credentials and Keys

> **Note:** These were found statically in the decompiled source. Firebase/GCM API keys for Android apps are intentionally embedded and are restricted by `google-services.json` / SHA-1 signing. However, they are documented here for completeness and to support rotation decisions.

| Key | Value | Environment | Location |
|---|---|---|---|
| `APP_ID` | `1783AF460D4D0615365940C9D3A` | All | `Constants.APP_ID` |
| Firebase/GCM API Key (prod) | `AIzaSyAZd_opjmBNcqPuXY5PWiu8CsLbb01vSDw` | PROD | `Constants.FCM_API_PROD_KEY` / `strings.xml` |
| Firebase/GCM API Key (dev) | `AIzaSyBVDlr-hoog6rMLLuveArACgNAnMZc4czU` | DEV | `Constants.FCM_API_DEV_KEY` |
| Firebase/GCM API Key (test) | `AIzaSyABBVvk3oCIrQvzR3m-We0tVvhgOAQYFf4` | TEST | `Constants.FCM_API_TEST_KEY` |
| Google OAuth Client ID (prod) | `658750132944-ak7v9k2ppp6i46cl4mj5dn47glmp2e90.apps.googleusercontent.com` | PROD | `strings.xml` |
| Firebase App ID (prod) | `1:658750132944:android:fe2a1feff4199dbb3cc4d5` | PROD | `Constants.MOBILESDK_APP_ID_PROD` |
| Firebase App ID (dev) | `1:22050591023:android:f76f9d2e19ea13781091da` | DEV | `Constants.MOBILESDK_APP_ID_DEV` |
| Firebase App ID (test) | `1:386779864964:android:d2eaec6f887c70168c87d1` | TEST | `Constants.MOBILESDK_APP_ID_TEST` |
| Firebase Project ID | `bluettiapp` | PROD | `strings.xml` |
| Firebase Storage Bucket | `bluettiapp.appspot.com` | PROD | `strings.xml` |
| GCM Sender ID | `658750132944` | PROD | `strings.xml` |
| Facebook App ID | `6441153849337992` | PROD | `strings.xml` |
| Facebook Login Scheme | `fb6441153849337992` | PROD | `strings.xml` |

---

## 8. Notable Findings & Security Observations

### 8.1 Dev/Test Infrastructure Exposed
All three environment URLs (dev, test, production) are compiled into the release APK. The dev SSO and after-sales endpoints use **plain HTTP** (`http://dev-sso.poweroak.ltd:18888`), meaning credentials would be transmitted unencrypted if the dev environment were reachable.

Furthermore, the `network_security_config.xml` declares `cleartextTrafficPermitted="true"` globally on `<base-config>`. This means all traffic — not just dev/test — is permitted to use plain HTTP, widening the MITM attack surface if a network attacker forces an HTTPS downgrade.

### 8.2 `DevModeActivity` Present
`net.poweroak.bluetticloud.ui.common.DevModeActivity` is registered in the manifest. This activity likely exposes a developer/debug UI with environment switching and internal diagnostics. It should be verified that it is not accessible without appropriate authentication.
### 8.3 Unusual API Path — Device Location Update

The endpoint `PUT /api/blusmartprod/device/basic/v1/188a37b9033f791157564c2ed8a` is the `updateLocation()` method. It accepts `gwcredentials` as a query parameter and sends encrypted device location data.

### 8.4 `READ_LOGS` and `READ_PRIVILEGED_PHONE_STATE` Permissions
These are unusually privileged permissions for a consumer app. `READ_PRIVILEGED_PHONE_STATE` is typically only granted to system or carrier apps; it is unlikely to be granted on non-rooted devices but its presence is worth noting.

### 8.5 Request Encryption Incomplete
The `RequestEncryptInterceptor` contains placeholder stubs ("这里调用加密的方法，自行修改"). If API request body encryption is a security requirement, this layer is not functioning in this build. Traffic should be verified with a proxy to confirm whether encryption is applied at another layer (e.g., native `.so`).

### 8.6 Third-Party SDK Exposure
Keys for the following SDKs are embedded:
- **Firebase** (Auth, FCM, Analytics, Crashlytics)
- **Google Sign-In / OAuth**
- **Facebook** (App registration for OAuth)
- **Google Play Integrity** (app attestation)

### 8.7 Passwords Stored in SharedPreferences

When the user enables "Remember Password", the login credentials are stored as plaintext in Android SharedPreferences:
- Email login: `SP_LAST_LOGIN_PASSWORD`
- Phone login: `SP_LAST_LOGIN_PHONE_PASSWORD`

These are stored in the same `SharedPreferences` file as the auth token (`SP_USER_TOKEN`), making them accessible to any process with root access or via Android backup/restore extraction.

---

## 9. Third-Party Libraries (notable)

| Library | Purpose |
|---|---|
| Retrofit 2 + OkHttp 3 | HTTP networking |
| Eclipse Paho MQTT | IoT real-time messaging |
| BouncyCastle | TLS/crypto, PKCS#12 parsing |
| Firebase (Auth, FCM, Analytics, Crashlytics) | Push notifications, analytics, crash reporting |
| Google Play Integrity | Device/app attestation |
| RxJava 3 | Async programming |
| Glide | Image loading |
| Room | Local SQLite database |
| RetrofitUrlManager | Dynamic base URL switching |
| AndroidX WorkManager | Background tasks |
| gotev/android-upload-service | File upload |

---

## 10. App Architecture Summary

```
┌────────────────────────────────────────────────────────────┐
│  Android App (net.poweroak.bluetticloud)                   │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  BLE Layer   │  │  HTTP Layer  │  │  MQTT Layer      │ │
│  │  (AES-CFB)   │  │  (Retrofit + │  │  (SSL/mTLS       │ │
│  │              │  │   OkHttp)    │  │   port 18760)    │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
│         │                 │                   │           │
└─────────┼─────────────────┼───────────────────┼───────────┘
          │                 │                   │
     BLUETTI           API Gateway          MQTT Broker
     Device           gw.bluettipower.com   iot.bluettipower.com
     (Local BLE)      (20+ microservices)   :18760

Microservices: midpauthc, midpfilec, midpmdata, midpnc,
               midppayc, midppkic, midplifec,
               blusmartprod, bluiotdata, bluiotvpp,
               blucomm, blushopc, blubucksc, blumktc,
               bluas, bludistc, blufic, bluinstp,
               bluuc, bluelearn, bluomsfcc, bluwmsc
```

> **Note:** `bluomsfcc` (OMS — Order Management System) and `bluwmsc` (WMS — Warehouse Management System) are referenced in the app architecture but their Retrofit service interfaces were not identified among the decompiled sources. They likely support partner/distributor order fulfillment and warehouse inventory flows, respectively.

---

## 11. Firmware Update Flow — Complete Reference

Source files: `DeviceUpgradeBaseActivity.java`, `DeviceVersionModel.java`, `DeviceVersionRepository.java`, `FirmwareDownloadViewModel.java`, `FirmwareDownloadRepository.java`, `FirmwareUpgradeConfig.java`, `FirmwareUpgradeOrder.java`, `FmUpgradeStrategy.java`, `DeviceFmVer.java`, `DeviceSoftwareVerResp.java`, `FirmwareVerReq.java`, `FirmwareVerItemBean.java`, `DeviceFirmware.java`, `ProtocolParse.java`, `ConnectManager.java`, `OTAGroup.java`, `UpgradeStatus.java`, `SmartProductService.java`, `DeviceConnUtilKt.java`, `OtaUtil.java` (both `lib_ble` and app copy), `DeviceUpgradeBroadcastBean.java`, `BootUpgradeSupport.java`, `DeviceNodeOTAStatusItem.java`, `FirmwareDetection.java`.

Two primary upgrade paths exist: **BLE local** (app downloads firmware, sends it over BLE to the device) and **Cloud/Remote** (app triggers server, server sends MQTT command to device, device fetches firmware over Wi-Fi). The app can also do **broadcast upgrades** to push firmware to multiple sub-devices simultaneously (e.g., parallel battery packs).

### 11.1 Step 1 — Version Check

The app sends the device's current firmware state to the server, which responds with available updates. Four API versions exist, growing in capability. All are defined in `SmartProductService.java`:

| Endpoint | Return Type | Purpose |
|---|---|---|
| `POST /api/blusmartprod/device/firmware/v1/latest/firmwareVerList` | `BaseResponse<List<DeviceFmVer>>` | Single device (legacy) |
| `POST /api/blusmartprod/device/firmware/v1/latest/firmwareVerList/batch` | `BaseResponse<List<DeviceSoftwareVerResp>>` | Multi-device batch v1 |
| `POST /api/blusmartprod/device/firmware/v2/latest/firmwareVerList/batch` | `BaseResponse<List<DeviceSoftwareVerResp>>` | Multi-device batch v2 |
| `POST /api/blusmartprod/device/firmware/v3/latest/firmwareVerList` | `BaseResponse<DeviceSoftwareVerResp>` | Single device v3 |

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

For **batch requests**, the body is a `List<Map<String, Object>>` where each map has `"sn"`, `"model"`, `"firmwareVers"` (list of `{"firmwareId", "ver"}` maps), and for battery packs: `"masterDeviceModel"`. The `firmwareId` integers map to the `DeviceFirmware` enum (Section 11.2).

**Response** — batch endpoints return `List<DeviceSoftwareVerResp>` where each item contains `model` (String), `sn` (String), and `versions` (List<DeviceFmVer>). The V2 single-device endpoint returns `List<DeviceFmVer>` directly.

The app determines if a new version is available via `DeviceConnUtilKt.deviceFmNewVersionAvailable(oldVer, newVer)` which compares version strings numerically, ensuring the part number prefix matches.

**HTTP call chain:** `Activity` → `DeviceVersionModel.kt` (ViewModel/LiveData) → `DeviceVersionRepository.kt` → `SmartProductService.kt` (Retrofit).

### 11.2 Firmware Component Types (`DeviceFirmware` enum)

Defined in `DeviceFirmware.java` / `ConnectConstants.kt`. The `firmwareId` is the integer value.

| ID | Name | Description | ID | Name | Description |
|---|---|---|---|---|---|
| 0 | IOT | IoT/WiFi module | 13 | RF | RF module |
| 1 | ARM | Main ARM processor | 14 | DC_HUB | DC hub |
| 2 | DSP | DSP chip | 15 | AC_HUB | AC hub |
| 3 | BMS | Battery management system | 16 | DC_DC | DC-DC converter |
| 4 | BA | Battery array | 17 | ATS | Auto transfer switch |
| 5 | PACK_BCU | Battery pack BCU | 18 | PANEL | Solar panel controller |
| 6 | PACK_BMU | Battery pack BMU | 19 | PARALLEL_BOX | Parallel box |
| 7 | PACK_BMS | Battery pack BMS | 20 | INV_DSP2 | Second inverter DSP |
| 8 | PACK_M1 | Pack M1 | 11 | HMI1 / HMI_BOOT / HMI_KERNEL / HMI_FILE_SYS / HMI_APP_UI / HMI_APP_BASE | Display sub-components |
| 9 | PACK_SAFETY | Pack safety | 253 | PPS | PPS |
| 10 | PACK_HIGH_VOLTAGE | Pack high voltage | 254 | BOOT | Bootloader |
| 12 | HMI2 | Second display | 255 | SYSTEM | System |

**HMI sub-components** (all share firmwareId 11): HMI_BOOT, HMI_KERNEL, HMI_FILE_SYS, HMI_APP_UI, HMI_APP_BASE. These represent different partitions of the display firmware.

**Boot firmware detection:** `DeviceFmVer.isBootVer()` returns true if the version string length > 6 and characters at positions 5–6 are `"00"`, indicating the firmware targets the bootloader.

### 11.3 Step 2 — Server Response (`DeviceFmVer`)

The server returns one `DeviceFmVer` object per firmware component. Key fields (from `DeviceFmVer.java`):

| Field | Type | Meaning |
|---|---|---|
| `firmwareType` | int | Component ID (from DeviceFirmware enum) |
| `version` | String | Target version string |
| `currVersion` | long | Device's current version (echoed back) |
| `hasNewVersion` | bool | `true` if an update is available |
| `downloadUrl` | String | Direct URL to download the binary (for unencrypted firmware) |
| `fileMd5` | String | MD5 checksum for post-download integrity check |
| `fileSize` | int | File size in bytes |
| `encrypted` | bool | Whether the firmware file is encrypted |
| `signature` | String | Firmware signature — sent as final OTA packet |
| `checkSum` | String | Additional checksum field |
| `shardSize` | int | Chunk size in bytes for BLE transfer (from `X-Shard-Size` header for encrypted firmware, else defaults to 1024) |
| `supportBroadcastUpgrade` | bool | Can be pushed to multiple sub-devices at once via broadcast OTA |
| `needToReconnect` | bool | Device requires BLE reconnect after flashing |
| `versionList` | List<DeviceFmVer> | Sub-components (e.g. HMI has BOOT/KERNEL/APP parts with individual version info) |
| `upgradeStrategy` | String | Upgrade strategy identifier (e.g., `"ARM_LAST"`) |
| `firmwareId` | String | Firmware identifier string |
| `sn` | String | Target device serial |
| `model` | String | Target device model |

### 11.4 Step 3 — Firmware Download

#### 11.4.1 Download URL Construction

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

#### 11.4.2 Download Execution

The download is managed through `FirmwareDownloadViewModel` → `FirmwareDownloadRepository`, using Kotlin coroutines and `Flow<DownloadStatus>`. The download streams the firmware binary to a cache file and returns progress updates.

**Flow:**
1. `DeviceUpgradeBaseActivity.firmwareDownload(firmware, showSuccessTips, showLoading)` is called
2. A new file is created via `FirmwareDownloadViewModel.newFirmwareFile()`
3. The download URL is constructed (if encrypted, using the hardcoded endpoint)
4. A coroutine launches that calls `downloadVM.download(url, IDownloadBuild)`, collecting a `Flow<DownloadStatus>`
5. On `DownloadSuccess`, response headers are parsed for encrypted firmware metadata
6. `firmware.setDownload(true)` triggers the callback

#### 11.4.3 File Naming and Storage

**File location:** App's cache directory (`context.getCacheDir()`).

**File naming convention** (`FirmwareDownloadViewModel.java:59-69`):
```
{modelCode}_{firmwareTypeName}_{version}_{firmwareId}
```
Example: `AC200L_IOT_v9001.00_abc123`

The `firmwareTypeName` is resolved from `ConnectConstantsKt.getFirmwareTypeName(firmwareType)`.

#### 11.4.4 Cache Validation

`FirmwareDownloadViewModel.isFirmwareFileExits()` checks:
- The file exists on disk
- If `fileMd5` is present, verifies the file's MD5 hash matches
If both pass, the cached file is reused without re-downloading.

### 11.5 Step 4A — Delivery to Device via BLE (Local OTA)

This is the primary path when the phone is connected to the device via Bluetooth.

#### 11.5.1 OTA Start Command

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

#### 11.5.2 OTA Initiation

In `ConnectManager.otaRequest(firmwareBean, callback, isRemote)`:
1. Sets `isOTA = true`, stores firmwareBean
2. For BLE mode: Sends the OTA start command via `addTaskItem()` as a `BleTaskItem`
3. For remote mode: Returns immediately (server triggers upgrade via MQTT)
4. Up to 3 retries (`otaRequestCount`) on OTA start failure

#### 11.5.3 OTA Data Transfer

Once the device acknowledges the OTA start (response `"43"`), data transfer begins. `ConnectManager.getOTAFileData(index)`:

1. **First call:** Reads the entire firmware file into memory via `OtaUtil.fileToByteArray()`
2. **Total packs calculation:**
   - Encrypted: `ceil(fileSize / shardSize) + 1` (the +1 is the signature packet)
   - Non-encrypted: `ceil(fileSize / 1024)`
3. **Per-packet construction:** Each packet is wrapped as:
   ```
   {type}{index}{checkIndex}{hexData}{CRC16_XMODEM}
   ```
   - `type`: `"A1"` for encrypted data packets, `"A2"` for signature packet (last), constant for non-encrypted
   - `index`: packet index (0–255, wrapped)
   - `checkIndex`: `255 - index`
   - `hexData`: the chunk of firmware bytes
   - `CRC16_XMODEM`: checksum of the frame
4. **ESP32 encrypted devices:** The entire wrapped packet is additionally AES-CBC encrypted with `bleConnShareKey` before BLE transmission.

#### 11.5.4 OTA Response Handling

Device responses over BLE (`ConnectManager.otaDataChange(result)`):
- `"43"` — OTA start acknowledged → begin data transfer (`otaPackIndex = 1`)
- `"06"` — Packet acknowledged → increment index, write next packet
- `"15"` — NAK (negative acknowledge) → retry up to 10 times with 200ms delay
- `"18"` or `"1818"` or `"01 81 01 81 90"` — OTA write complete
  - For portable/charger/hub devices (non-cloud, non-IOT): starts polling timer for OTA status
  - Otherwise: immediately notifies `onUpgradeComplete()`

**Progress reporting:** `updateProgress(default, currentPack, totalPacks)` reports percentage. Reaches 100% when all packs are sent.

**Error handling:** `BleOtaCallback.onUpgradeFailed(error, errCode)` with error types: `FILE_TOO_LARGE`, `FILE_ERROR`, `CANCEL`, `TIMEOUT`, `OTHER`. A 15-second OTA status countdown timer retries up to 3× before declaring a timeout failure.

### 11.6 Step 4B — Cloud / Remote OTA (MQTT-Based)

Used when the device is connected to the internet via Wi-Fi and the app is not in local BLE range.

**API endpoint:** `POST /api/blusmartprod/device/firmware/v1/appSentDeviceRemoteUpgrade`

**Request body** (constructed in `DeviceUpgradeBaseActivity.callRemoteUpgrade()`):
```json
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
2. Delays 3000ms, then starts `otaStatusCountDown` timer
3. Polls OTA status via BLE/MQTT
4. Up to 3 retries

**AECC devices** use a separate endpoint:
```
POST /api/blusmartprod/device/firmware/v1/aeccSentDeviceRemoteUpgrade
```

### 11.7 Broadcast Upgrade

When `DeviceFmVer.supportBroadcastUpgrade` is `true`, a single OTA command can push firmware to multiple connected sub-devices simultaneously (e.g., parallel battery packs in a stack).

- **OTA type:** `3` (vs `1` for normal)
- **Group ID:** `255` (broadcast to all sub-devices in the group)
- **Record saving:** Uses `upgradeRecordBroadcastSave()` instead of `upgradeRecordSave()`, returning a `DeviceUpgradeBroadcastBean` with `recordId`
- **Per-node tracking:** `List<DeviceNodeOTAStatusItem>` tracks each sub-device's status (`otaStatus`, `errorCode`, `softwareVer`, `sn`, `modelNumber`)
- **UI:** `DeviceOTAStatusDialog` shows live progress with per-node status during multi-device upgrades

### 11.8 OTA Groups

`OTAGroup.java` enum maps firmware types to OTA groups, which determine the target device subsystem:

| Group | Value | Firmware Types |
|---|---|---|
| INV | 1 | ARM, DSP, INV_DSP2, AC_HUB, DC_HUB |
| PACK | 2 | PACK_BCU, PACK_BMU, PACK_BMS, PACK_M1, PACK_SAFETY, PACK_HIGH_VOLTAGE, DC_DC, BA |
| IOT | 3 | IOT, HMI1, HMI2, RF |
| LCD | 4 | EPAD HMI1 |
| ATS | 5 | ATS, AT1 IOT |
| PANEL | 6 | PANEL, EPANEL |
| DCDC_OR_CHARGER | 7 | D400S |
| WT | 8 | WT |
| S1 | 9 | S1 |

Group mapping is defined in `DeviceConnUtilKt.deviceFmOtaGroup(fmType, model)`.

### 11.9 Step 5 — Upgrade Order and Strategy

Multiple firmware components are flashed **sequentially** in a device-model-specific order.

#### Configuration Classes

- **`FirmwareUpgradeConfig.java`** — Singleton defining upgrade order per device model
- **`FirmwareUpgradeOrder.java`** — Data class with three fields:
  - `invOrder` (List<Integer>) — Order for inverter firmware types
  - `packOrder` (List<Integer>) — Order for battery pack firmware types
  - `delays` (Map<Integer, Long>) — Optional delays in ms between firmware upgrades
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

### 11.10 Boot Upgrade

**`BootUpgradeSupport.java`** contains flags for bootloader upgrade support:
- `isSupport` (int) — Whether boot upgrade is supported
- `softwareVerTotal` (int) — Number of software versions in the boot binary

**`DeviceUpgradeBootActivity.java`** is a minimal activity (`extends BaseConnActivity`) providing boot-specific upgrade UI. It extends the base connection activity but is essentially a shell — the actual boot upgrade logic reuses the standard firmware upgrade flow.

### 11.11 Step 6 — Upgrade Record (Server Reporting)

After each upgrade attempt, the app reports back to the server. The flow is handled in `DeviceUpgradeBaseActivity.callSaveUpgradeRecord()`.

#### API Endpoints

| Endpoint | gwcredentials? | Purpose |
|---|---|---|
| `POST /api/blusmartprod/device/upgrade/record/v1/save` | Yes (`"ZFKVIQwNyA4BKtXPEMlMJ..."`) | Standard upgrade record |
| `POST /api/blusmartprod/device/upgrade/record/v1/broadcastSave` | No | Broadcast upgrade record (returns `recordId`) |

#### UpgradeStatus Enum

| Status | Value |
|---|---|
| FAILURE | 0 |
| SUCCESS | 1 |
| UPGRADING | 2 |

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

### 11.12 Complete End-to-End Flows

#### BLE Local Upgrade Flow

```
1. VERSION CHECK
   Activity.getFirmwareVersion()
   → DeviceVersionModel.firmwareVerListBatchV2(requestMapList)
   → POST /api/blusmartprod/device/firmware/v2/latest/firmwareVerList/batch?gwcredentials=...
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
   → POST /api/blusmartprod/device/firmware/v1/appSentDeviceRemoteUpgrade
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

### 11.13 Firmware Version Formatting

`DeviceConnUtilKt.deviceFmVerFormat(fmVer)` formats raw version values for display:
- Versions with >6 characters: splits as `{first5}.{chars5-6}.{rest}` → e.g., `v90010.00.123`
- Versions with >4 characters (≤6): splits as `{first4}.{rest}` → e.g., `v9001.00`
- Otherwise: plain prefix → e.g., `v100`

---

## Section 12 — BLE Encryption Key Retrieval

### 12.1 Overview

The app uses two distinct BLE security protocols depending on device firmware generation. Neither protocol fetches a session key from the cloud at runtime — all cryptographic material is either hardcoded in the APK or derived on-device from a challenge-response exchange.

### 12.2 Path 1 — Legacy Challenge-Response (Protocol v1)

Applies to older devices where `protocolVer < 2000`.

**Flow:**

1. Device sends a BLE "hello" packet containing a 4-byte random value at bytes 4–7.
2. App reverses the 4 random bytes, computes MD5 → stores as `randomMd5`.
3. App responds with a challenge packet: `"2A2A0204" + randomMd5.substring(16, 24)` + 1-byte checksum.
4. Session AES key is derived as:

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
2. **Device sends ECDH public key + ECDSA signature** (encrypted with `bleConnAESKey`):
   - Response type `0x04`: payload contains `iotPkHexStr` (64-byte uncompressed SECP-256R1 public key) + `signature` (64-byte raw ECDSA-SHA256 signature over `iotPublicKey || randomMd5`).
3. **App verifies signature** using hardcoded ECDSA verification key `PUBLIC_KEY_K2`:

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
6. **Device responds** with response type `0x06` confirming acceptance.
7. **Session key derived** via ECDH:

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
2. Broadcasts the key via `LiveEventBus` event `"IOT_SERVER_KEY"`.
3. Passes it as Intent extra `"serverBLEKey"` to `DeviceBluetoothScanActivity` for the screen pairing flow.

This key is not fetched from a cloud REST API by the app at runtime; it is read directly from the device register over BLE.

**Related registers (not used for general BLE device control):**

| Register | Address | Name | Purpose |
|----------|---------|------|---------|
| 13603 | `IOT_BLE_SERVER_KEY` | Server BLE Key | FPS/screen accessory pairing key |
| 12185 | `IOT_BLE_SERVER_SET` | Server BLE Set | Write register for provisioning the server BLE key |
| 13776 | `BLE_CLIENT_PAIR_SN` | BLE Client Pair SN | Sub-device/accessory pairing serial number |

**Key source files:**
- `ConnectManager.java:2266–2267` — register 13603 → `ACTION_IOT_SERVER_KEY` event
- `DeviceFPSResetActivity.java:198–221` — subscribes to event, stores `serverBLEKey`
- `DeviceFPSResetActivity.java:161–170` — passes key as Intent extra to scan activity

### 12.5 Security Observations

| Issue | Detail |
|-------|--------|
| **Hardcoded local AES key** | `LOCAL_AES_KEY = 459FC535808941F17091E0993EE3E93D` is identical across all app installations. Any attacker who captures a BLE session can decrypt it given the `randomMd5` (derivable from the challenge packet). |
| **Hardcoded ECDSA private key** | `PRIVATE_KEY_L1` is embedded in the APK. An attacker can extract it, sign arbitrary ECDH public keys, and impersonate the official Bluetti app to any device. |
| **Hardcoded ECDSA verification key** | `PUBLIC_KEY_K2` is the only device-authenticity anchor. All Bluetti devices share the same IoT identity signing key. |
| **No cloud key fetch for sessions** | BLE session keys are fully self-contained; revocation or re-keying without an app update is not possible. |
| **getQrCodeEncrypt endpoint** | `GET /api/blusmartprod/device/basic/v1/getQrCodeEncrypt` exists in the API list but is not used in the BLE session key flow — it appears to be related to QR-code-based device pairing, not BLE encryption. |
| **BLE password checked client-side only** | The 6-digit PIN is read from the device over BLE, then compared against user input in the app. An attacker who completes the BLE handshake can read the register holding the PIN and bypass the check. |
| **BLE password stored on device, readable over BLE** | Once the encrypted session is established, the PIN value is transmitted in the clear (encrypted at the transport layer by the global session key). |

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

---

## Section 13 — Offline BLE Operations

### 13.1 Overview

The app supports a fully offline Bluetooth-direct mode that allows scanning for, connecting to, and reading data from Bluetti devices **without logging in and without internet connectivity**. Write access (device control) is gated behind a separate Guest/Visitor Mode flag (see Section 14).

### 13.2 Entry Points

Offline BLE mode can be entered from two locations:

1. **Start screen** (`StartActivity.java:235`): A button on the initial app screen directly launches `DeviceBluetoothScanActivity` with `PAGE_SCENE_CONN`, requiring no login.
2. **Home Fragment** (`HomeFragment.java:332, 414`): From the device list, a "Bluetooth Connect" action launches the BLE scan with `PAGE_SCENE_CONN`.

### 13.3 BLE Scan (Offline)

`DeviceBluetoothScanActivity` uses standard Android BLE APIs to scan for advertising devices. No cloud calls are made during scanning. When `BluettiUtils.isLogin()` returns `false`:

- The screen title changes to the localized string `R.string.device_offline_mode` ("Offline Mode")
- The search animation switches to `add_device_searching_offline` (`DeviceBluetoothScanActivity.java:547-550, 583`)
- Analytics tracks the screen as `"offline_mode"` (`DeviceBluetoothScanActivity.java:1579`)

### 13.4 BLE Connect (Offline)

After selecting a device from the scan list, `extractedConnect()` and `startConnect()` initiate the BLE GATT connection. The session key derivation (Section 12) is entirely self-contained — all cryptographic material is hardcoded or derived from the BLE handshake. No cloud API call is required to establish an encrypted BLE session.

Once connected, `startDeviceConnectionActivity()` (`DeviceBluetoothScanActivity.java:1546-1554`) navigates to the device home activity:
```java
setConnMode(ConnMode.BLUETOOTH);
startActivity(new Intent(this,
    DeviceConnUtil.getHomeActivityByModel(getConnMgr().getDeviceModel(), ...)));
```

### 13.5 Reading Device Data (Offline)

After connecting, the device home activity reads Modbus registers over BLE via `ConnectManager.getReadTask()`. All read operations — real-time power, battery SOC, temperatures, faults, etc. — work entirely over the local BLE link with no internet dependency.

### 13.6 Device Control (Offline) — Conditional

| Scenario | Read Data | Write/Control |
|----------|-----------|---------------|
| Not logged in, Guest Mode **disabled** | Yes | **No** — "only viewing access is allowed" |
| Not logged in, Guest Mode **enabled** | Yes | **Yes** — full control |

The app string at `R.string.device_guest_mode_msg1` states: *"In Offline/Bluetooth Mode, only viewing access is allowed. Log in, bind the device, and enable Visitor Access in settings to take control."*

### 13.7 Offline Options Dialog

When a cloud-connected device goes offline (MQTT disconnect), `DeviceOfflineOptionDialog` (`DeviceOfflineOptionDialog.java`) presents two options:
- **"Change Network"** — re-configure Wi-Fi settings (requires device ownership)
- **"Bluetooth Direct Connection"** — switch to local BLE control

This dialog is triggered from the device list when a device's MQTT connection drops and BLE is available as a fallback.

### 13.8 Security Implications

| Issue | Detail |
|-------|--------|
| **No auth gate for BLE scan/connect** | Anyone with the app can discover and connect to nearby Bluetti devices via BLE without any account or login. |
| **Read access without credentials** | Device telemetry (power, SOC, temperatures, fault codes) is readable without authentication. |
| **Write access gated by device-side flag only** | Guest mode enforcement relies solely on a flag stored on the device — there is no server-side authorization check. |
| **Offline bar displayed** | The `DeviceTopAdvertiseBar` (`device_offline_mode_advertise_bar.xml`) displays a banner when operating in offline mode, informing the user that data may not be synced. |

---

## Section 14 — Guest / Visitor Mode

### 14.1 Overview

Guest Mode (also labeled "Visitor Access") is a device-side flag that allows **unauthenticated users** to control a device over BLE without logging into the app, binding the device to an account, or having internet connectivity.

### 14.2 Flag Location

The flag is stored on the **device**, not in the cloud. It is a 2-bit field (`guestModeEnable`) embedded in the device's base configuration block.

### 14.3 Reading the Flag

When the device settings screen opens (`BaseConnSettingsActivityUI2`), the app sets `TimerScene.BASE_SETTINGS` which triggers a BLE read of the base config registers. The response is parsed in `ProtocolParse.parseBaseConfig()` at `ProtocolParse.java:82-116`:

```java
// ProtocolParse.java:97-99
List list = hexStrToBinaryList(dataRes.get(10) + dataRes.get(11));
// ...
deviceBaseConfigBean.setGuestModeEnable(
    Integer.parseInt(list.get(3) + list.get(2), 2));
```

The parsed value flows into `ConnectManager.guestMode` at `ConnectManager.java:776`:
```java
this.guestMode = value.getGuestModeEnable();
```

Multiple device home activities (`DeviceConnHomeActivityV2.java:1560`, `SmartPlugHomeActivity.java:758`, `PanelHomeActivity.java:168`, etc.) check `getConnMgr().getGuestMode() == 1` to determine if they should display a guest-mode-active warning dialog.

### 14.4 Writing the Flag

The device owner enables/disables Guest Mode from the device settings screen. The UI binds `itemGuestMode` in `DeviceConnSettingsUi2Binding`. Tapping the toggle triggers the write at `BaseConnSettingsActivityUI2.java:792-801`:

**Enable** (value `4` → register address `6`):
```java
addTaskItem(getConnMgr(),
    ConnectManager.getSetTask(connMgr, 6, 4, null), ...);
connMgr.setGuestMode(1);
```

**Disable** (value `8` → register address `6`):
```java
addTaskItem(getConnMgr(),
    ConnectManager.getSetTask(connMgr, 6, 8, null), ...);
connMgr.setGuestMode(2);
```

The BLE write task uses `ConnectManager.getSetTask(int regAddr, int value, Integer modbusSlave)` which constructs a standard Modbus write command over BLE GATT. See `ConnectManager.java:4150`.

### 14.5 UI Confirmation Dialog

Before the write commits, `DeviceGuestModeDialog` (`DeviceGuestModeDialog.java`) displays a confirmation with the Chinese-language warning:

> "Are you sure you want to authorize visitors to control this device? After confirmation, visitors can directly control this device through offline mode/Bluetooth direct connection without logging in to the app or binding the device. Please operate carefully!"

The dialog has Authorize/Confirm/Cancel buttons and a close icon. Source: `device_dialog_guest_mode.xml` layout, bound in `DeviceGuestModeDialog.java:32`.

### 14.6 Effect When Enabled

When `guestMode == 1` and the app is connected via BLE (`ConnMode.BLUETOOTH`) without a bound device (`deviceBean == null`):

1. The device home activities show a guest mode notification dialog
2. The "settings" gear icon remains accessible — the user can still open settings
3. Write operations (settings changes, switch toggles, mode changes) are allowed over BLE

### 14.7 Security Observations

| Issue | Detail |
|-------|--------|
| **No server-side enforcement** | Guest mode is purely a device-local flag. The cloud API is not consulted for authorization. |
| **Flag persists on device** | Once set, guest mode remains active until explicitly disabled — across app restarts and across different phones. |
| **Any nearby phone can control device** | If guest mode is enabled, any phone with the Bluetti app can connect via BLE and control the device without any authentication. |
| **Write is local BLE only** | The `guestModeEnable` flag can only be set by a device owner who has already authenticated and connected to the device (either via cloud or a prior BLE session with full credentials). |

---

## Section 15 — BLE Protocol Reference for Developers

> **Target device:** AC2A (model code `"AC2A"`, number 20 in `DeviceModel` enum). The AC2A is an inverter-class device using protocol V2 (≥2000).

### 15.1 BLE GATT Details

| Item | UUID |
|------|------|
| Service | `0000ff00-0000-1000-8000-00805f9b34fb` |
| Notify/Read characteristic | `0000ff01-0000-1000-8000-00805f9b34fb` |
| Write characteristic | `0000ff02-0000-1000-8000-00805f9b34fb` |
| CCC descriptor | `00002902-0000-1000-8000-00805f9b34fb` |

**Scan filter:** Service UUID `0000ff00-...` is used as the BLE scan filter.

**Scan record identification (manufacturer-specific data):**
| Hex prefix | Meaning |
|-----------|---------|
| `424c5545545449` ("BLUETTI") | ESP32 device, non-encrypted |
| `424c5545545445` ("BLUETTE") | ESP32 encrypted |
| `424c5545545446` ("BLUETTF") | ESP32 encrypted variant |

**Write characteristic:**
- MTU: 247 bytes (BLE 4.2 max) for ESP32/encrypted devices
- Write without response: `writeCharacteristic()` or `writeCharacteristicSplit()` with `supportMaxLength=244`

### 15.2 BLE Connection and Handshake Flow

#### Step 1: Scan & Connect

1. Start BLE scan filtered by service `0000ff00-...`
2. On device found, call `connectGatt()` with `transport=LE`
3. Wait for services discovery (500ms delay auto-triggered)
4. Find `BluetoothGattService` using service UUID from scanned device
5. Get write characteristic (`ff02`) and read/notify characteristic (`ff01`)
6. Enable notifications on `ff01` with descriptor `00002902-...` using `ENABLE_NOTIFICATION_VALUE` (`{0x01, 0x00}`)

#### Step 2: Read Device Snapshot

After connection, the app reads the base config to determine protocol version and capabilities:

1. Read protocol version from Modbus register 16 (v1: `0103 0010 0001 ...`) or V2 equivalent
2. Read base config from register 1
3. Read device SN from register 21
4. Read real-time data from register 10

#### Step 3: Encryption Handshake (for encrypted devices)

For devices where `isESP32Encrypted == true` or `isBLEEncrypted == true`:

**3a. Challenge-Response:**
1. Device sends: `2A 2A 01` followed by 4 random bytes (position 4-7)
2. App reverses the 4 random bytes, computes MD5 → `randomMd5`
3. App responds: `2A 2A 02 04` + `randomMd5.substring(16, 24)` + 2-byte checksum
4. App derives temporary key: `bleConnAESKey = XOR(randomMd5, LOCAL_AES_KEY)`

**3b. ECDH Key Exchange (protocol v2+):**
1. Device sends `2A 2A 04 ...` (AES-CBC encrypted with `bleConnAESKey`, IV=MD5(randomMd5))
   - Bytes 4-67: device's SECP-256R1 public key (64 bytes, raw X+Y, no 04 prefix)
   - Bytes 68 to (end-2): raw ECDSA signature (r||s, 64 bytes) over `(devicePublicKey || randomMd5)`
   - Last 2 bytes: checksum (little-endian sum of preceding bytes)
2. App verifies ECDSA signature using hardcoded `PUBLIC_KEY_K2`
3. App generates ephemeral SECP-256R1 keypair
4. App signs `(appPublicKey || randomMd5)` with hardcoded `PRIVATE_KEY_L1`
5. App sends `2A 2A 05 80 ...` with app public key + signature
6. Device responds `2A 2A 06 00 ...` confirming acceptance
7. App derives shared secret via ECDH: `bleConnShareKey = ECDH(appPrivKey, devicePubKey)`
8. `bleConnAESKey` discarded; all subsequent traffic encrypted with `bleConnShareKey`

**3c. Post-handshake encryption:**
All subsequent Modbus frames are AES-CBC encrypted using `bleConnShareKey` (or `bleConnAESKey` if ECDH not completed):
- Written via `buildAESCBCCmd(cmd, aesKey, iv)` 
- The IV for the first block is derived from MD5(randomMd5), then chained from previous ciphertext
- Each 16-byte block padded to exactly 16 bytes (no PKCS padding)

#### Step 4: Modbus Data Protocol (post-handshake)

Once encrypted channel is established, device communication uses standard Modbus RTU-style frames.

### 15.3 Modbus Frame Construction

All Modbus frames use **slave address 1** (`01`).

#### Read Single/Multiple Registers

```
<01> <03> <reg_addr_2bytes_big_endian> <reg_count_2bytes_big_endian> <CRC16_2bytes>
```

Example — read 11 registers starting at address 10 (base real data):
```
01 03 000A 000B xx xx
```

CRC16 uses standard Modbus CRC-16-IBM polynomial (`0xA001`).

#### Write Single Register (value fits in 1 register)

```
<01> <06> <reg_addr_2bytes_be> <value_2bytes_be> <CRC16_2bytes>
```

#### Write Multiple Registers

```
<01> <10> <reg_addr_2bytes_be> <reg_count_2bytes_be> <byte_count> <data> <CRC16_2bytes>
```

Where `byte_count = reg_count * 2`.

#### ASCII String Write

For register writes containing ASCII strings (e.g., WiFi password, BLE password), each pair of characters is byte-swapped: position `i+1` is written before position `i`. Maximum length controls determine register count.

### 15.4 Protocol Version Thresholds

| Version | Changes |
|---------|---------|
| 1016 | Original protocol |
| 1017 | MCU status fields changed; `EB3A`/`AC200M` exceptions |
| 1018 | Added `mcuBusyStatus` field |
| 1019 | Data field extensions |
| 1020–1023 | Incremental additions |
| **2000** | **V2 protocol** — `ProtocolAddrV2` register addressing |
| 2001 | `SYSTEM_TIME` register |
| 2003 | Extended phase data |
| 2004 | `SYSTEM_TIME_ZONE` register |
| 2005 | `WORKING_MODE` register, `CTRL_EVENT` |
| 2006–2008 | Extended control registers |

**Key threshold:** `protocolVer < 2000` → V1 protocol (`ProtocolAddr`), `>= 2000` → V2 (`ProtocolAddrV2`).

For the AC2A, the minimum protocol version is defined in `DeviceConnUtil.getDeviceFunc()` and can be overridden by the device's actual reported version from the base config.

### 15.5 Complete Modbus Register Map

#### V1 Protocol (`ProtocolAddr`) — protocolVer < 2000

| Address | Name | R/W | Description |
|---------|------|-----|-------------|
| 1 | `BASE_CONFIG` | R | 14-field base config (32 registers) |
| 7 | `BLUETOOTH_PASSWORD` | R/W | 6-char BLE PIN (12 bytes ASCII) |
| 10 | `BASE_REAL_DATA` | R | Real-time power/SOC/status (~110 registers) |
| 16 | `MODBUS_PROTOCOL_VER` | R | Protocol version |
| 21 | `DEVICE_SN` | R | Device serial number |
| 22 | `MCU_STATUS` | R | MCU status |
| 70 | `ADDITIONAL_DATA` | R | Additional fields |
| 91 | `BMS_PACK` | R | BMS battery pack data |
| 130 | `THREE_PHASE_DATA` | R | Three-phase data (if applicable) |
| 157 | `PV_CHARGE_DATA` | R | PV/solar data |
| 190 | `WIFI_SWITCH_STATUS` | R | WiFi status |
| 1080 | `OTA_START` | W | Start OTA upgrade |
| 2000 | `FAULT_HISTORY_START` | R | Fault history |
| 3000 | `SETTABLE_DATA` / `MAIN_SWITCH` | R/W | Main power switch |
| 3001 | `WORKING_MODE` | R/W | Working mode |
| 3002 | `GRID_PLUS_MODE` | R/W | Grid+ mode |
| 3003 | `INVERTER_FREQUENCY` | R/W | Output frequency (50/60Hz) |
| 3004 | `MACHINE_MODE` | R/W | Machine mode |
| 3005 | `MACHINE_ADDRESS` | R/W | Modbus address |
| 3007 | `AC_SWITCH` | R/W | AC output switch |
| 3008 | `DC_SWITCH` | R/W | DC output switch |
| 3009 | `PV_CONTROL` | R/W | PV/solar control |
| 3010 | `FEED_SWITCH` | R/W | Grid feedback switch |
| 3011 | `GRID_CHARGING_SWITCH` | R/W | Grid charging switch |
| 3014 | `MAX_PV_CHARGE_CURRENT` | R/W | Max PV charge current |
| 3015 | `LOW_POWER_SETTINGS` | R/W | Low power threshold |
| 3016 | `HIGH_POWER_SETTINGS` | R/W | High power threshold |
| 3018 | `MAX_DISCHARGING_CURRENT` | R/W | Max discharge current |
| 3019 | `MAX_CHARGING_CURRENT_OF_GRID` | R/W | Max grid charge current |
| 3031 | `SYSTEM_TIME` | R/W | System time |
| 3034 | `LED_CONTROL` | R/W | LED control |
| 3035 | `UPS_MODE` | R/W | UPS mode |
| 3039 | `WORKING_TIME` | R/W | Working time config |
| 3057 | `MAX_CHARGING_POWER` | R/W | Max charge power |
| 3058 | `MAX_DISCHARGE_POWER` | R/W | Max discharge power |
| 3060 | `SYSTEM_POWER_OFF` | W | System power off |
| 3061 | `LCD_SCREEN_TIME` | R/W | LCD timeout |
| 3062 | `SET_SYSTEM_FACTORY_RESET` | W | Factory reset |
| 3063 | `ECO_CONTROL` | R/W | DC ECO mode |
| 3064 | `ECO_AUTO_OFF` | R/W | ECO auto-off time |
| 3065 | `CHARGING_MODE` / `SILENT_MODE` | R/W | Charging mode / silent |
| 3066 | `POWER_LIFTING_MODE` | R/W | Power lifting mode |
| 3067 | `CTRL_AC_ECO_MODE` | R/W | AC ECO mode |
| 3069 | `DC_ECO_POWER` | R/W | DC ECO power threshold |
| 3070 | `AC_ECO_POWER` | R/W | AC ECO power threshold |
| 3079 | `OUTPUT_VOLTAGE` | R/W | Output voltage setting |
| 3090 | `SYS_SWITCH_RECOVERY` | R/W | Switch state recovery |
| 4997 | `BLE_MAC` | R | BLE MAC address |
| 5000 | `IOT_DATA` | R/W | IoT/WiFi data |
| 5002 | `UPGRADE_PROGRESS` | R | OTA progress |
| 5003 | `UPGRADE_MODULE` | W | OTA module select |
| 5017 | `INTERNET_SETTING` | R/W | WiFi settings |
| 5049 | `NETWORK_RSSI` | R | WiFi RSSI |
| 12205 | `IOT_DISPLAY_SET` | R/W | IoT display settings |
| 13603 | `IOT_BLE_SERVER_KEY` | R | Server BLE key (FPS pairing) |

#### V2 Protocol (`ProtocolAddrV2`) — protocolVer ≥ 2000 (AC2A uses this)

**Device Core (read operations):**

| Address | Name | Description |
|---------|------|-------------|
| 100 | `APP_HOME_DATA` | Home page data snapshot |
| 700 | `OTA_START` | OTA start command |
| 720 | `OTA_STATUS` | OTA progress status |
| 1100 | `INV_BASE_INFO` | Inverter base info |
| 1200 | `INV_PV_INFO` | PV/solar info |
| 1300 | `INV_GRID_INFO` | Grid input/output info |
| 1400 | `INV_LOAD_INFO` | Load info |
| 1500 | `INV_INV_INFO` | Inverter status info |
| 1700 | `INV_METER_INFO` | Meter data |
| 1900 | `INV_METER_SETTINGS` | Meter settings |
| 3500 | `INV_TOTAL_ENERGY_INFO` | Lifetime energy totals |
| 3600 | `INV_CURR_YEAR_ENERGY_INFO` | Current year energy |

**Device Control (write operations):**

| Address | Name | R/W | Description |
|---------|------|-----|-------------|
| 2000 | `INV_BASE_SETTINGS` | R/W | Base settings |
| 2001 | `SYSTEM_TIME` | R/W | System clock |
| 2005 | `WORKING_MODE` | R/W | Working mode |
| 2006 | `CTRL_EVENT` | W | Control events |
| 2007 | `CTRL_LED` | R/W | LED control |
| 2008 | `CTRL_METER` | R/W | Meter control |
| 2010 | `CTRL_INVERTER` | R/W | Inverter control |
| 2011 | `AC_SWITCH` | R/W | AC output |
| 2012 | `DC_SWITCH` | R/W | DC output |
| 2013 | `SYSTEM_POWER_OFF` | W | Power off |
| 2014 | `CTRL_DC_ECO_MODE` | R/W | DC ECO mode |
| 2015 | `DC_ECO_AUTO_OFF_TIME` | R/W | ECO auto-off time |
| 2016 | `DC_ECO_POWER` | R/W | ECO power threshold |
| 2017 | `CTRL_AC_ECO_MODE` | R/W | AC ECO mode |
| 2018 | `AC_ECO_AUTO_OFF_TIME` | R/W | AC ECO auto-off |
| 2019 | `AC_ECO_POWER` | R/W | AC ECO power |
| 2020 | `CHARGING_MODE` | R/W | Charging mode (Standard/Turbo/Silent) |
| 2021 | `CTRL_SUPER_POWER_MODE` | R/W | Power lifting mode |
| 2022 | `SYS_SOC_LOW_CAPACITY` | R/W | Low SOC threshold |
| 2023 | `SYS_SOC_HIGH_CAPACITY` | R/W | High SOC threshold |
| 2026 | `SET_HISTORY_ENERGY_TYPE` | W | History energy type |
| 2027 | `SET_CURR_ENERGY_TYPE` | W | Current energy type |
| 2028 | `SET_LOG_HISTORY_PAGE` | W | Log history page |
| 2029 | `CTRL_CHG_DSG_TIME` | W | Charge/discharge time control |
| 2030 | `WORKING_TIME_START` | R/W | Working time start |
| 2060 | `PV_TYPE_SET` | R/W | PV type setting |
| 2066 | `CTRL_ALARM_SOUND` | R/W | Alarm sound |
| 2067 | `LCD_SCREEN_TIME` | R/W | LCD timeout |
| 2075 | `SOC_SET_LOW` | R/W | SOC low setting |
| 2078 | `LED_COLOR_SET` | R/W | LED color |
| 2083 | `SOC_SET_HIGH` | R/W | SOC high setting |
| 2084 | `PV_ADV_SET` | R/W | PV advanced settings |
| 2086 | `JA12_ENABLE` | R/W | 12V output enable |
| 2200 | `INV_ADVANCE_SETTINGS` | R/W | Advanced settings |
| 2206 | `SYSTEM_FACTORY_RESET` | W | Factory reset |
| 2207 | `CTRL_GRID` | R/W | Grid control |
| 2208 | `CTRL_FEED` | R/W | Feed-in control |
| 2209 | `INV_VOLTAGE` | R/W | Output voltage (120/220/230/240V) |
| 2210 | `INV_FREQ` | R/W | Output frequency (50/60Hz) |
| 2211 | `CHG_MAX_VOLTAGE` | R/W | Max charge voltage |
| 2212 | `CHG_MAX_CURRENT` | R/W | Max charge current |
| 2213 | `GRID_MAX_POWER` | R/W | Max grid power |
| 2214 | `GRID_MAX_CURRENT` | R/W | Max grid current |
| 2225 | `CTRL_GRID_PLUS_MODE` | R/W | Grid+ mode toggle |
| 2241 | `EMS_CTRL_MODE_SET` | R/W | EMS control mode |
| 2269 | `ADV_PV_SET` | R/W | PV advanced settings |
| 2271 | `DC_OUTPUT_VOLT_LEVEL` | R/W | DC output voltage level |

**IoT / Network:**

| Address | Name | Description |
|---------|------|-------------|
| 11000 | `IOT_BASE_INFO` | IoT module info |
| 11106 | `WIFI_MULT_INFO` | WiFi multi-info |
| 11127 | `IOT_SERVER_BLE_SN` | Server BLE serial |
| 12002 | `WIFI_SETTING` | WiFi settings |
| 12161 | `IOT_ENABLE_INFO` | IoT enable info |
| 12163 | `DISASTER_WARNING_MODE` | Disaster warning |
| 13500 | `IOT_WIFI_MESH` | WiFi mesh settings |
| 13600 | `IOT_EXTENSION_SETTINGS` | Extension settings |

**Battery Pack:**

| Address | Name | Description |
|---------|------|-------------|
| 6000 | `PACK_MAIN_INFO` | Pack main info |
| 6100 | `PACK_ITEM_INFO` | Pack item info |
| 6300 | `PACK_SUB_PACK_INFO` | Sub-pack info |
| 7000 | `PACK_SETTINGS_INFO` | Pack settings |
| 7200 | `PACK_BMU_INFO` | BMU info |

### 15.6 Real-Time Data Parsing (Register 10 / `BASE_REAL_DATA`)

Response format (`ProtocolParse.getDeviceRealtimeData()`): a `List<String>` of hex bytes (2-char strings each). Index is 0-based.

| Index | Field | Type | Parsing |
|-------|-------|------|---------|
| 0–11 | `deviceModel` | String | ASCII chars from non-zero hex values |
| 12–13 | `protocolVer` | int | `parseInt(dataRes[12]+dataRes[13], 16)` |
| 14–21 | `deviceSN` | ULong | Reverse-endian pairs, base-16 |
| 22–25 | (reserved) | — | Skipped |
| 24–25 | `mcuBusyStatus` | int | Only if proto ≥ 1018; binary from hex |
| 26–29 | `mcu1SoftwareVer` | String | Endian `[2][3][0][1]` |
| 30–33 | `mcu2SoftwareVer` | String | Same |
| 34–37 | `mcu3SoftwareVer` | String | Same |
| 38–41 | `mcu4SoftwareVer` | String | Same |
| 42–45 | `hmi1Ver` | String | Same |
| 46–49 | `hmi2Ver` | String | Same |
| 50–51 | (padding) | — | Skipped |
| 52–53 | `pvChargingPower` | int | `parseInt(hex, 16)` |
| 54–55 | `gridChargingPower` | int | Same |
| 56–57 | `acLoadPower` | int | Same |
| 58–59 | `dcLoadPower` | int | Same |
| 60–61 | `feedBackPower` | int | Same |
| 62–65 | `totalPVPower` | float | Endian `[2][3][0][1]`, divided by 10.0 |
| 66–67 | `batterySOC` | int | Battery state of charge % |
| 68–69 | `pvIconDisplay` | int | PV icon flag |
| 70–71 | `gridIconDisplay` | int | Grid icon flag |
| 72–73 | `pv2BatteryEnergyLine` | int | PV→Battery flow |
| 74–75 | `grid2BatteryEnergyLine` | int | Grid→Battery flow |
| 76–77 | `battery2ACEnergyLine` | int | Battery→AC flow |
| 78–79 | `battery2DCEnergyLine` | int | Battery→DC flow |
| 80–81 | `battery2GridEnergyLine` | int | Battery→Grid flow |
| 82–83 | `grid2LoadEnergyLine` | int | Grid→Load flow |
| 84–85 | `pv2GridEnergyLine` | int | PV→Grid flow |
| 86–87 | `batteryDischargingStatus` | int | Discharge status flag |
| 88–95 | `alarmInfo` | bitmask | 4× 16-bit alarm flags (V1 reg 54–57) |
| 96–109 | `faultInfo` | bitmask | 7× 16-bit fault flags (V1 reg 58–64) |
| 106–107 | `chgFullTime` | int | Minutes until full (if present) |
| 108–109 | `dsgEmptyTime` | int | Minutes until empty (if present) |
| 111 | `sysIsHighVolt` | int | High voltage system flag |
| 112 | `maxGridChgCurrentEnable` | int | Max grid charge current enable |
| 113 | `gridPlusModeEnable` | int | Grid+ mode enable |
| 114–115 | `rateVoltage` | int | Rated voltage (if present) |
| 116–117 | `rateFrequency` | int | Rated frequency (if present) |

The alarm/fault bitmasks decode against different name maps depending on the
protocol path and the model's `DeviceFunction.isLowPower` flag.

**V1 path (`ProtocolParse.getDeviceRealtimeData`, protocolVer < 2000):**

```java
zIsLowPower ? ConnConstantsV2.lowPowerWarnNames  : ConnectConstants.alarmInfoNames
zIsLowPower ? ConnConstantsV2.lowPowerFaultNames : ConnectConstants.faultInfoNames
```

- `isLowPower == false` (default — EB3A, AC200M, AC300, AC500, etc.):
  `ConnectConstants.alarmInfoNames` (1 word, 9 bits — grid voltage/frequency/
  oscillation, meter comm, PV voltage, generator voltage) and
  `ConnectConstants.faultInfoNames` (5 words: inverter/AC charger/battery pack/
  generic fault4/fault5).
- `isLowPower == true` (AC240/AC200L/AC200PL, plus PES_BASE-derived models):
  `ConnConstantsV2.lowPowerWarnNames` (2 words) and
  `ConnConstantsV2.lowPowerFaultNames` (5 words).

**V2 path (`ProtocolParserV2.parseDeviceData`, protocolVer ≥ 2000):**

- Inverter type 3 (high-power): `ConnConstantsV2.highPowerWarnNames` /
  `highPowerFaultNames`.
- Micro-inverter type: `ConnConstantsV2.microInvWarnNames` / `microInvFaultNames`.
- Otherwise: `ConnConstantsV2.lowPowerWarnNames` / `lowPowerFaultNames`.

**BMS_PACK (V2 only, address 6000/6100/7200) is a separate path** that uses
`ConnConstantsV2.packHighVoltAlarmNames`, `packHighVoltErrorNames`, and
`bmuWarnNames`. It does **not** decode the BASE_REAL_DATA alarm/fault region.

### 15.7 Base Config Parsing (`parseBaseConfig()`)

From V1 protocol register 1. Fields parsed in order:

| Field | Source | Width |
|-------|--------|-------|
| `specs` | `dataRes[0]` | 1 byte |
| `voltageType` | `dataRes[1]` | 1 byte |
| `lcdBroadcastEnable` | `dataRes[5]` bit 0 | 1 bit |
| `isSupportMeter` | `dataRes[5]` bit 1 | 1 bit |
| `isSupportPlug` | `dataRes[5]` bit 2 | 1 bit |
| `emsCtrlMode` | `dataRes[7]` low nibble | 4 bits |
| `comboxScene` | `dataRes[9]` | 1 byte |
| `isInitializedConfig` | `dataRes[9]` (same byte) | 1 byte |
| `projectType` | `dataRes[8]` low nibble | 4 bits |
| `btPswEnable` | binary bits `[1][0]` of `dataRes[10]+dataRes[11]` | 2 bits |
| `guestModeEnable` | binary bits `[3][2]` of `dataRes[10]+dataRes[11]` | 2 bits |
| `btLoginPsw` | `dataRes[12..17]` ASCII (only if btPswEnable==1) | 6 bytes |
| `iotModbusVer` | `dataRes[28]+dataRes[29]` | 2 bytes |
| `protocolVer` | `dataRes[30]+dataRes[31]` | 2 bytes |

For V2 protocol devices like the AC2A, base settings are read from `INV_BASE_SETTINGS` (address 2000).

### 15.8 Complete Crypto Material

All keys are hardcoded in the APK and identical across all installations.

| Key | Value | Source File |
|-----|-------|-------------|
| `LOCAL_AES_KEY` | `459FC535808941F17091E0993EE3E93D` | `ConnConstantsV2.java:98` |
| `PRIVATE_KEY_L1` | `4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337` | `SignatureCrypt.java:34` |
| `PUBLIC_KEY_K2` | `3059301306072a8648ce3d020106082a8648ce3d03010703420004A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594` | `SignatureCrypt.java:35` |

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

### 15.9 High-Level Interaction Flows

#### Read Real-Time Data

1. BLE scan → connect → GATT setup (Section 15.2 Step 1)
2. Encryption handshake (Section 15.2 Step 3) — derive `bleConnShareKey`
3. Build Modbus read command: `01 03 <addr_2bytes> <count_2bytes> <CRC16>`
4. Encrypt with `buildAESCBCCmd(modbus_frame, bleConnShareKey, iv)`
5. Write to `ff02` characteristic
6. Receive notification on `ff01`
7. AES-CBC decrypt response with `parseAESCBCData()`
8. Parse hex byte list via `getDeviceRealtimeData()` (Section 15.6)

#### Set Device Option (e.g., AC output on/off)

1. Build Modbus write command: `01 06 <addr_2bytes> <value_2bytes> <CRC16>`
2. Encrypt with `buildAESCBCCmd(modbus_frame, bleConnShareKey, iv)`
3. Write to `ff02` characteristic
4. Read confirmation: read the same register to verify

### 15.10 AC2A-Specific Notes

- **Model code:** `"AC2A"`, number 20 in `DeviceModel` enum
- **Device category:** `POWER_STATION` (portable power station)
- **Protocol:** V2 (≥2000), uses `ProtocolAddrV2` register addresses
- **Key registers for AC2A:**
  - Read: 1100 (base info), 1200 (PV), 1300 (grid), 1400 (load), 1500 (inverter)
  - Write/control: 2011 (AC switch), 2012 (DC switch), 2020 (charging mode), 2209 (output voltage), 2210 (frequency)
- **Firmware upgrade order:** IOT(0) → ARM(1) → DSP(2) → BMS(3) → DC_DC(16)
- **Has battery:** Yes (built-in)
- **Supports:** AC output, DC output, PV input, grid charging, ECO mode, UPS mode, power lifting
- **Device function flags:** Defined in `DeviceConnUtil.getDeviceFunc("AC2A", protocolVer, ...)` which returns a `DeviceFunction` with ~135 boolean capability flags
