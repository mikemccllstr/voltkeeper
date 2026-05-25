# Backend Services

This page documents the Bluetti cloud backend infrastructure: environment switching, production and dev/test service URLs, the complete Retrofit API endpoint catalog across all microservices, and the MQTT broker details.

## Backend Infrastructure

### Environment Switching

The app contains a fully functional three-environment architecture controlled by `EnvManager` (`net.poweroak.bluetticloud.http.env.EnvManager`). The active environment defaults to **RELEASE** but can be toggled at runtime.

| Environment           | Gateway URL                          |
| --------------------- | ------------------------------------ |
| **RELEASE (default)** | `https://gw.bluettipower.com`        |
| TEST                  | `https://test-gw.poweroak.ltd:18443` |
| DEV                   | `https://dev-gw.poweroak.ltd:18443`  |

### Production Service URLs

| Service                     | URL                                                                 |
| --------------------------- | ------------------------------------------------------------------- |
| API Gateway (primary)       | `https://gw.bluettipower.com`                                       |
| API Gateway (secondary/PRY) | `https://gwpry.bluettipower.com`                                    |
| SSO / Auth                  | `https://sso.bluettipower.com`                                      |
| H5 Frontend                 | `https://h5.bluettipower.com`                                       |
| Community H5                | `https://h5.bluettipower.com/app/community/dist/index.html#/home`   |
| After-Sales                 | `https://after-sales.bluettipower.com`                              |
| IoT/MQTT Broker             | `ssl://iot.bluettipower.com:18760`                                  |
| File (by ID)                | `https://gw.bluettipower.com/api/midpfilec/file/v1/getFile?id=<id>` |
| App Download                | `https://download.bluetti.app?sn=<sn>`                              |
| App Download (alternate)    | `https://download.poweroak.ltd?sn=<sn>`                             |

### Test / Dev Service URLs (also embedded in binary)

| Service          | URL                                                        |
| ---------------- | ---------------------------------------------------------- |
| Dev Gateway      | `https://dev-gw.poweroak.ltd:18443`                        |
| Test Gateway     | `https://test-gw.poweroak.ltd:18443`                       |
| Dev SSO          | `http://dev-sso.poweroak.ltd:18888` (**HTTP — no TLS**)    |
| Test SSO         | `https://test-sso.poweroak.ltd:18443`                      |
| Dev H5           | `https://dev-app-h5.poweroak.ltd:18443`                    |
| Test H5          | `https://test-app-h5.poweroak.ltd:18443`                   |
| Dev IoT/MQTT     | `ssl://dev-iot.poweroak.ltd:18760`                         |
| Test IoT/MQTT    | `ssl://test-iot.poweroak.ltd:18760`                        |
| Dev After-Sales  | `http://dev-after.poweroak.ltd:18888` (**HTTP — no TLS**)  |
| Test After-Sales | `http://test-after.poweroak.ltd:18888` (**HTTP — no TLS**) |

______________________________________________________________________

## API Endpoints (Retrofit Services)

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
POST /api/blusmartprod/device/firmware/v2/appSentDeviceRemoteUpgrade
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
POST /api/blusmartprod/device/accessories/v1/deviceAddAccessories
POST /api/blusmartprod/device/accessories/v1/removeDeviceAccessories
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
POST /api/bluiotdata/aecc/v1/getDeviceAlarmFlag
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
DELETE /api/bluinstp/app/order/v1/delete
GET  /api/bluinstp/app/device/v1/overview
```

### Learning / Video (`bluelearn`)

```
GET  /api/bluelearn/app/videoClassify/v1/classifications
GET  /api/bluelearn/app/videoClassify/v1/getAppVideos
GET  /api/bluelearn/app/videoClassify/v1/countrys
```

______________________________________________________________________

## IoT Communication — MQTT over SSL/TLS

The app uses Eclipse Paho MQTT client (`org.eclipse.paho.client.mqttv3`) for real-time device communication.

- **Broker (prod):** `ssl://iot.bluettipower.com:18760`
- **Transport:** TLS with optional mutual TLS (mTLS) via client certificates
- **Certificate source:** Client certificates are fetched from `/api/midppkic/cert/app/v1/pfx` (PKCS#12) and stored locally; the `MqttManager` loads them via `SSLHelper` using BouncyCastle
- **`certPassword` field** is set dynamically at runtime (not hardcoded)
- **Reconnect logic:** Exponential backoff with `ScheduledExecutorService`
