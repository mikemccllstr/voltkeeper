# Device Models

This page covers the protocol version thresholds that define device model generations, the device model catalog (120 models as of APK v3.0.9), and AC2A-specific details as the reference implementation model.

## Protocol Version Thresholds

| Version   | Changes                                                                                              |
| --------- | ---------------------------------------------------------------------------------------------------- |
| 1016      | Original protocol                                                                                    |
| 1017      | MCU status fields changed; `EB3A`/`AC200M` exceptions                                                |
| 1018      | Added `mcuBusyStatus` field                                                                          |
| 1019      | Data field extensions                                                                                |
| 1020–1023 | Incremental additions                                                                                |
| **2000**  | **V2 protocol** — `ProtocolAddrV2` register addressing                                               |
| 2001      | `SYSTEM_TIME` register                                                                               |
| 2003      | Extended phase data                                                                                  |
| 2004      | `SYSTEM_TIME_ZONE` register (unverified: APK does not parse this register in `parseInvBaseSettings`) |
| 2005      | `WORKING_MODE` register, `CTRL_EVENT`                                                                |
| 2006–2008 | Extended control registers                                                                           |

**Key threshold:** `protocolVer < 2000` → V1 protocol (`ProtocolAddr`), `>= 2000` → V2 (`ProtocolAddrV2`).

For the AC2A, the minimum protocol version is defined in `DeviceConnUtil.getDeviceFunc()` and can be overridden by the device's actual reported version from the base config.

## AC2A-Specific Notes

- **Model code:** `"AC2A"`, number 20 in `DeviceModel` enum
- **Device category:** `POWER_STATION` (portable power station)
- **Protocol:** V2 (≥2000), uses `ProtocolAddrV2` register addresses
- **Key registers for AC2A:**
  - Read: 1100 (base info), 1200 (PV), 1300 (grid), 1400 (load), 1500 (inverter)
  - Write/control: 2011 (AC switch), 2012 (DC switch), 2020 (charging mode), 2022 (sys_low_power), 2023 (sys_high_power), 2075 (soc_holding_low), 2083 (soc_holding_high), 2210 (frequency)
  - Some advanced registers (2209 inv_voltage, 2211-2216 charge/grid/feed limits) are hidden in the official app's Expert Mode for AC2A (`InvAdvancedParamsConfig` flags are `false`)
- **Firmware upgrade order:** IOT(0) → ARM(1) → DSP(2) → BMS(3) → DC_DC(16)
- **Has battery:** Yes (built-in)
- **Supports:** AC output, DC output, PV input, grid charging, ECO mode, UPS mode, power lifting
- **Device function flags:** Defined in `DeviceConnUtil.getDeviceFunc("AC2A", protocolVer, ...)` which returns a `DeviceFunction` with ~135 boolean capability flags

## EL100V2-Specific Notes

- **Model code:** `"EL100V2"`, number 31 in `DeviceModel` enum
- **Protocol:** V2 (≥2000)
- **Charging modes:** register 2020 — `STANDARD` (0), `SILENT` (1), `TURBO` (2), `CUSTOM` (4). Mapping confirmed against APK v3.0.10 `DeviceSettingsChgModeActivity` and hardware bench test (writing 1 put the device in Silent mode on its own display, 2026-07-03). **(breaking: releases through v2026.05 had the labels swapped)**
- **Pack voltage:** `DEFAULT_PACK_VOLTAGE_SCALE = 2` (÷100) — raw register × 0.01 = physical volts. Matches a 56 V-class LiFePO4 pack (53.50 V at 100% SoC per 2026-07-03 capture). The inherited ÷10 default would report a physically impossible ~530 V.
- **Removed fields:** `sys_low_power` (2022), `sys_high_power` (2023), `led_color` (2078) — APK v3.0.10 sets `sysPowerConditions(null)` and does not opt into `ledColor` for EL100V2; hardware verification confirms these registers are not honored on this device. **(breaking)**
- **grid_max_current:** UintField at 2214, whole amps, range `(0, 15)` — 0 means Pro Mode disabled, 1–15 available within custom charging mode. Bench-confirmed (verify-EL100V2-ac-2026-07-03): device accepts raw 0–15 and rejects 16+.
- **ECO ranges (bench-confirmed):** `dc_eco_power` 5–20 W, `ac_eco_power` 10–40 W, `dc_eco_auto_off_time` 1–4 h, `ac_eco_auto_off_time` 1–4 h
- **Firmware versions (IOT/ARM/DSP/BMS):** app displays raw register / 100 (e.g., 218614 → v2186.14) — INV_BASE_INFO bytes 26–61
- **IoT:** EL100V2 responds on block 11000; firmware version array in INV_BASE_INFO reports ARM, DSP, BMS, and IOT versions
- **Has battery:** Yes (built-in 56V LiFePO4)
- **Supports:** AC output, DC output, grid charging, feed-in, ECO mode, Online UPS, working mode selection

## V2 Array Parsing

All V2 devices inherit array-shaped payload parsing from `V2Base.parse()`. This is protocol-generic behavior (matching APK v3.0.10 `ProtocolParserV2`) available to every V2 model:

- **Firmware versions:** INV_BASE_INFO bytes 26–61 — up to 6 MCU firmware entries producing `*_version` keys
- **PV strings:** INV_PV_INFO bytes 20+ — per-string working status, type, power, voltage (÷10), current (÷10)
- **Grid phases:** INV_GRID_INFO bytes 26+ — per-phase power, voltage (÷10), current (÷10)
- **Load phases:** INV_LOAD_INFO bytes 60+ — per-phase power, voltage (÷10), current (÷10)
- **Inverter phases:** INV_INV_INFO bytes 18+ — per-phase work status, power, voltage (÷10), current (÷10)

Keys appear only when the device reports non-zero counts and the entry data is non-zero.

## Device Model Changes in v3.0.9

APK v3.0.8 had 115 device models; v3.0.9 adds 5 new models for a total of 120.

### New Models in v3.0.9

| Ordinal | Model Code     | Model Number | Notes            |
| ------- | -------------- | ------------ | ---------------- |
| 54      | `AORA100_MINI` | 66           | AORA mini series |
| 55      | `AORA30_MINI`  | 67           | AORA mini series |
| 56      | `AORA200_MINI` | 68           | AORA mini series |
| 98      | `HB500S`       | 4025         | Battery pack     |
| 99      | `BH500E`       | 4026         | Battery pack     |

### Notable Enum Changes

- **EB55** (model 14) was repositioned from ordinal 113 (near end of enum) to ordinal 20 (immediately after EB3A). This caused **all ordinals 20–113 to shift by +1 to +6 positions**, since EB55 insertion alone shifts +1, then the 3 MINI and 2 battery insertions add +3 and +2 respectively. Ordinal numbers are internal enum positions, not protocol identifiers — this is only relevant for mapping enum ordinals to model numbers.
- **FPS** model number changed from 0 to -1 (PES_BASE reserved).
- **AP200** model number changed from -1 to 69 (now has an assigned number).
- **DeviceCategory** now actively used in dispatch routing: `PORTABLE_POWER`, `HOME_POWER`, `MICRO_INV`, `BALCONY_SOLAR_V2`, `COMBOX`, `FRIDGE`, `SMART_PLUG`, `CHARGER`, `DC_HUB`, `DCDC`, `BATTERY`, `RV5`, `AT1`, `AECC`, `PANEL`, `METER`, `SCREEN`.
- **DeviceSeries** values: `PLP024`, `RV`, `AP300`, `NPP`, `HS`.

## Voltkeeper-Supported Device Models

The following device models are currently supported in voltkeeper, with model numbers and nominal voltages confirmed from the APK v3.0.9 `device_model_voltage.json`:

### Portable Power Stations (V2 Protocol)

| Model   | APK Enum  | Model # | Voltage | Support  | Notes                          |
| ------- | --------- | ------- | ------- | -------- | ------------------------------ |
| AC2A    | `AC2A`    | 20      | 25V     | Verified | Reference implementation       |
| AC60    | `AC60`    | 8       | 56V     | APK      | Compact portable               |
| AC180   | `AC180`   | 23      | 56V     | APK      | AC180/AC180P family base       |
| EL10V2  | `EL10V2`  | 62      | 25V     | APK      | Inherits PLP022/AC180 chain    |
| EL30V2  | `EL30V2`  | 32      | 25V     | APK      | Sibling of EL100V2             |
| EL100V2 | `EL100V2` | 31      | 56V     | Testing  | ELITE200_V2 family             |
| EL400   | `EL400`   | 29      | 56V     | APK      | Remote power ctrl + sleep mode |

### Portable Power Stations (V1 Protocol)

| Model   | APK Enum  | Model # | Voltage | Support | Notes                     |
| ------- | --------- | ------- | ------- | ------- | ------------------------- |
| EB3A    | `EB3A`    | 2       | 25V     | APK     | Compact, minimal writable |
| AC200M  | `AC200M`  | 3       | 56V     | APK     | Older mid-range           |
| AC200L  | `AC200L`  | 5       | 56V     | APK     | Mid-range portable        |
| AC200PL | `AC200PL` | 6       | 56V     | APK     | AC200L variant            |
| AC300   | `AC300`   | 9       | 56V     | APK     | Mid-large inverter        |
| AC500   | `AC500`   | 10      | 56V     | APK     | Large inverter            |

### Larger Systems (Mixed Protocol)

| Model | APK Enum | Model # | Voltage | Support | Notes       |
| ----- | -------- | ------- | ------- | ------- | ----------- |
| EP500 | `EP500`  | 35      | 56V     | APK     | Home backup |
| EP600 | `EP600`  | 36      | 56V     | APK     | Home backup |

### AORA Mini Series

| Model        | APK Enum       | Model # | Voltage | Support | Notes          |
| ------------ | -------------- | ------- | ------- | ------- | -------------- |
| AORA30_MINI  | `AORA30_MINI`  | 67      | —       | APK     | AORA mini base |
| AORA100_MINI | `AORA100_MINI` | 66      | —       | APK     | AORA mini base |
| AORA200_MINI | `AORA200_MINI` | 68      | —       | APK     | AORA mini base |

### Battery Packs

| Model  | APK Enum | Model # | Support | Notes        |
| ------ | -------- | ------- | ------- | ------------ |
| HB500S | `HB500S` | 4025    | APK     | Battery pack |
| BH500E | `BH500E` | 4026    | APK     | Battery pack |

### Key Features by Model

| Feature                     | AC2A | AC60 | AC180 | AC200L | AC200PL | AC300 | AC500 | EP500 | EL10V2 | EL30V2 | EL100V2 | EL400 | EP600 |
| --------------------------- | ---- | ---- | ----- | ------ | ------- | ----- | ----- | ----- | ------ | ------ | ------- | ----- | ----- |
| Working Mode (UPS strategy) | y    | —    | y     | y      | y       | y     | y     | —     | y      | y      | y       | y     | —     |
| Online UPS (`ups_mode`)     | —    | —    | —     | y      | y       | y     | y     | y     | y      | y      | y       | y     | y     |
| Child Lock                  | —    | —    | y     | —      | —       | —     | —     | —     | y      | —      | —       | —     | —     |
| Sleep Mode / Remote Power   | —    | —    | —     | —      | —       | —     | —     | —     | —      | —      | —       | y     | —     |
| Grid Control                | y    | —    | —     | —      | —       | —     | —     | —     | —      | y      | y       | y     | —     |
| Feed-in Control             | y    | —    | —     | —      | —       | —     | —     | —     | —      | y      | y       | y     | —     |
| Charge/Grid Limits          | y    | —    | —     | —      | —       | —     | —     | —     | —      | y      | y       | y     | —     |

All device classes marked with `# TODO(hardware): verify against physical device` are derived from APK data without hardware verification.
