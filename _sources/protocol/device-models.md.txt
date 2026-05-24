# Device Models

This page covers the protocol version thresholds that define device model generations, and provides AC2A-specific details as the reference implementation model.

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
