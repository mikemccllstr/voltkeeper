# APK Comparison: v3.0.9 → v3.0.10

**Compared with:** `mise run diff-apk 3.0.9 3.0.10`
**Artifacts:** `bluetti-files/diff/3.0.9-vs-3.0.10/` (gitignored; regenerable)

| Property    | v3.0.9                       | v3.0.10                     |
| ----------- | ---------------------------- | --------------------------- |
| versionName | 3.0.9                        | 3.0.10                      |
| versionCode | 1415                         | 1475                        |
| Package     | `net.poweroak.bluetticloud`  | `net.poweroak.bluetticloud` |
| Decompiled  | jadx (latest), apktool 2.7.0 | same toolchain              |

______________________________________________________________________

## Protocol Impact (Code Anchors)

### BLE Protocol

**No changes.** All three UUIDs used by voltkeeper are unchanged:

| UUID                                   | Purpose                    |
| -------------------------------------- | -------------------------- |
| `0000ff00-0000-1000-8000-00805f9b34fb` | GATT service               |
| `0000ff01-0000-1000-8000-00805f9b34fb` | Notify/Read characteristic |
| `0000ff02-0000-1000-8000-00805f9b34fb` | Write characteristic       |

### Modbus Register Changes

Genuinely new register constants in 3.0.10 (filtered from the raw diff to exclude `LAYOUT_*` R.java IDs, which shifted by one due to an inserted resource entry):

| Constant                 | Value | Context                            |
| ------------------------ | ----- | ---------------------------------- |
| `AC_INPUT_GEN_SOC_START` | 2247  | Generator SOC threshold to start   |
| `AC_INPUT_GEN_SOC_STOP`  | 2248  | Generator SOC threshold to stop    |
| `AC_INPUT_SET`           | 2306  | AC input mode write register       |
| `CTRL_MODE_HYBRID`       | 1     | Generator control mode: hybrid     |
| `CTRL_MODE_TIMING`       | 2     | Generator control mode: timing     |
| `CTRL_MODE_MANUAL`       | 3     | Generator control mode: manual     |
| `WIRING_TYPE_COM_NO`     | 1     | Dry-contact relay: normally-open   |
| `WIRING_TYPE_COM_NC`     | 2     | Dry-contact relay: normally-closed |
| `MODE_GENERATOR`         | 2     | AC input source: generator         |
| `MODE_GRID`              | 1     | AC input source: grid              |

Also notable: register **2093** appears as the multi-AC-port control register in `DevicePortSettingsActivity`, associated with four AC output ports (AC1–AC4). This is a new multi-port inverter configuration not in 3.0.9.

> **Note on extractor noise:** The `LAYOUT_*` constants in `protocol_anchors.txt` are Android resource IDs from R.java. They appear as ADDED/REMOVED because a new layout file was inserted in 3.0.10, shifting all subsequent IDs by one. They are not Modbus protocol constants.

### Device Model Identifiers

Added to `DeviceModel` enum in 3.0.10:

- `HB500E` (number 4026) — home battery, variant of the HB500/HB500S family (4018/4025)
- `HS1` (number –1) — smart plug/socket (HS family: HS1, HS2, HS3, HS5)
- `EM330` — appears in the 3.0.10 enum (confirmed in full enum list)

Not present in 3.0.10:

- `BH500E` — this was a false-positive match in v3.0.9's string resources, not a genuine
  DeviceModel enum entry; `HB500E` is the correct spelling added in 3.0.10.

> **Note on AC1/AC2/AC3/AC4:** These appear in both diff artifacts as new device models but are
> actually **AC output port labels** in `DevicePortSettingsActivity` for a multi-port inverter, not
> device model identifiers. The extractor does not distinguish port labels from model strings.

______________________________________________________________________

## Release Intent (Resource/UI Surface)

The dominant new feature is **smart generator (智能发电机) integration**: extensive UI strings for
generator self-check, SOC-based start/stop thresholds, dry-contact relay wiring type selection
(COM+NO vs. COM+NC), and manual/timing/hybrid control modes. This is a major new capability for
devices with an AC input that can accept a generator rather than grid power.

A second new feature is **AI Mode (AI会员 / AI membership)**: the app can subscribe users to an
AI-driven power optimization service that analyzes usage patterns, PV forecast, and electricity
price time-of-use to automatically schedule charging and discharging. Two new cloud endpoints
support this: `checkUserAiVip` and `userJoinAiVip`.

Additional UI additions:

- **Space device accessories** (配件) — third-party accessories (smart meters, smart sockets)
  that can be attached to a space
- **VPP / energy statistics** — space-level energy and power statistics, PV forecasted energy
- **Order/logistics messaging** — in-app order messages and duty-free file uploads (shop)
- **Community/social features** — video guides, co-create, vote options (existing community tab
  enhancements)
- **Generator self-check flow** — multiple screens for wiring verification, step-by-step test,
  pass/fail reporting

______________________________________________________________________

## Cloud API Surface

### Endpoints Added (19)

| Endpoint                                                                 | Purpose                                  |
| ------------------------------------------------------------------------ | ---------------------------------------- |
| `/api/blusmartprod/user/space/v1/addShareSpace`                          | Share a space with another user          |
| `/api/blusmartprod/user/space/v1/delShareSpaceMember`                    | Remove a space sharing member            |
| `/api/blusmartprod/user/space/v1/shareSpaceMemberList`                   | List members sharing a space             |
| `/api/blusmartprod/user/space/v1/getSpaceQrCodeEncrypt`                  | QR code for space sharing                |
| `/api/blusmartprod/user/space/v1/getUserSpaceList`                       | List user's spaces                       |
| `/api/blusmartprod/user/space/v1/getSpaceInfoBySpaceId`                  | Space details by ID                      |
| `/api/blusmartprod/user/space/v1/setSpaceMeter`                          | Assign a meter to a space                |
| `/api/blusmartprod/user/space/v1/getSupportJoinSpaceModelList`           | Device models that support space joining |
| `/api/blusmartprod/user/space/v1/getSupportJoinBalcotransModelList`      | Balco-trans models for space             |
| `/api/blusmartprod/device/basic/v1/deviceRestoreFactorySettings`         | Factory reset via cloud                  |
| `/api/blusmartprod/device/accessories/v1/checkDeviceAllowedToBeAdded`    | Accessory eligibility check              |
| `/api/bluiotvpp/user/ai/vip/v1/checkUserAiVip`                           | Check AI VIP membership status           |
| `/api/bluiotvpp/user/ai/vip/v1/userJoinAiVip`                            | Enroll in AI VIP membership              |
| `/api/bluiotvpp/dynamicElectricityPrice/user/v1/queryPvForecastedEnergy` | PV forecast query                        |
| `/api/bluiotdata/dashboard/v1/getSpaceDeviceEnergyStatistics`            | Space energy statistics                  |
| `/api/bluiotdata/dashboard/v1/getSpaceDevicePowerStatistics`             | Space power statistics                   |
| `/api/blushopc/app/order/v1/message/add`                                 | Add an order message                     |
| `/api/blushopc/app/order/v1/message/list`                                | List order messages                      |
| `/api/blushopc/app/order/v1/pendingSigning/getDutyFreeFile`              | Get duty-free file                       |
| `/api/blushopc/app/order/v1/submit/dutyFreeFile`                         | Submit duty-free file                    |
| `/file/v1/getFile`                                                       | File retrieval (path variant)            |

### Endpoints Removed (1)

| Endpoint                                     | Notes                                            |
| -------------------------------------------- | ------------------------------------------------ |
| `/api/blusmartprod/user/space/v1/shareSpace` | Replaced by `addShareSpace` (renamed/refactored) |

### Hosts / Base URLs

**No changes.** All production, test, and dev environment URLs are identical between versions.

______________________________________________________________________

## Impact on `src/voltkeeper`

**Immediate impact: none.** The BLE protocol surface (service UUID, write/notify characteristics,
Modbus RTU framing, encryption handshake) is unchanged. No register addresses that voltkeeper
currently uses have moved or been removed.

**Potential follow-on work** (not in scope for this change; record for future planning):

| Item                                           | Priority | Notes                                                                          |
| ---------------------------------------------- | -------- | ------------------------------------------------------------------------------ |
| Generator control registers (2247, 2248, 2306) | Low      | Only relevant if supporting devices with an AC input that accepts a generator  |
| Multi-AC-port register (2093)                  | Low      | For future multi-port inverter device support                                  |
| New device models: HB500E, HS1, EM330          | Low      | Home batteries and smart plug — different product segment from current targets |

The existing protocol docs (`ble-communication.md`, `modbus-registers.md`, `encryption-details.md`,
`device-models.md`, `backend-services.md`) describe the 3.0.9 surface and remain accurate for the
aspects voltkeeper uses. The backend-services endpoint list is now missing the 3.0.10 additions;
update that doc if cloud API documentation completeness matters.
