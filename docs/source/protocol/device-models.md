# Device Models

This page covers the protocol version thresholds that define device model generations, the device model catalog (120 models as of APK v3.0.9), and AC2A-specific details as the reference implementation model.

<!-- Extracted from FINDINGS.md §15.4 and §15.10 -->

## 15.4 Protocol Version Thresholds

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

## 15.10 AC2A-Specific Notes

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

## 15.11 Device Model Changes in v3.0.9

APK v3.0.8 had 115 device models; v3.0.9 adds 5 new models for a total of 120.

### New Models in v3.0.9

| Ordinal | Model Code | Model Number | Notes |
|---------|-----------|-------------|-------|
| 54 | `AORA100_MINI` | 66 | AORA mini series |
| 55 | `AORA30_MINI` | 67 | AORA mini series |
| 56 | `AORA200_MINI` | 68 | AORA mini series |
| 98 | `HB500S` | 4025 | Battery pack |
| 99 | `BH500E` | 4026 | Battery pack |

### Notable Enum Changes

- **EB55** (model 14) was repositioned from ordinal 113 (near end of enum) to ordinal 20 (immediately after EB3A). This caused **all ordinals 20–113 to shift by +1 to +6 positions**, since EB55 insertion alone shifts +1, then the 3 MINI and 2 battery insertions add +3 and +2 respectively. Ordinal numbers are internal enum positions, not protocol identifiers — this is only relevant for mapping enum ordinals to model numbers.
- **FPS** model number changed from 0 to -1 (PES_BASE reserved).
- **AP200** model number changed from -1 to 69 (now has an assigned number).
- **DeviceCategory** now actively used in dispatch routing: `PORTABLE_POWER`, `HOME_POWER`, `MICRO_INV`, `BALCONY_SOLAR_V2`, `COMBOX`, `FRIDGE`, `SMART_PLUG`, `CHARGER`, `DC_HUB`, `DCDC`, `BATTERY`, `RV5`, `AT1`, `AECC`, `PANEL`, `METER`, `SCREEN`.
- **DeviceSeries** values: `PLP024`, `RV`, `AP300`, `NPP`, `HS`.
