# Modbus Registers

This page documents the complete Modbus register maps for both V1 and V2 protocols, including register addresses, field layout tables, real-time data parsing indices, and base config parsing.

<!-- Extracted from FINDINGS.md §15.3, §15.5, §15.6, and §15.7 -->

## 15.3 Modbus Frame Construction

All Modbus frames use **slave address 1** (`01`).

### Read Single/Multiple Registers

```
<01> <03> <reg_addr_2bytes_big_endian> <reg_count_2bytes_big_endian> <CRC16_2bytes>
```

Example — read 11 registers starting at address 10 (base real data):
```
01 03 000A 000B xx xx
```

CRC16 uses standard Modbus CRC-16-IBM polynomial (`0xA001`).

### Write Single Register (value fits in 1 register)

```
<01> <06> <reg_addr_2bytes_be> <value_2bytes_be> <CRC16_2bytes>
```

### Write Multiple Registers

```
<01> <10> <reg_addr_2bytes_be> <reg_count_2bytes_be> <byte_count> <data> <CRC16_2bytes>
```

Where `byte_count = reg_count * 2`.

### ASCII String Write

For register writes containing ASCII strings (e.g., WiFi password, BLE password), each pair of characters is byte-swapped: position `i+1` is written before position `i`. Maximum length controls determine register count.

## 15.5 Complete Modbus Register Map

### V1 Protocol (`ProtocolAddr`) — protocolVer < 2000

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

### V2 Protocol (`ProtocolAddrV2`) — protocolVer ≥ 2000 (AC2A uses this)

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

## 15.6 Real-Time Data Parsing (Register 10 / `BASE_REAL_DATA`)

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

## 15.7 Base Config Parsing (`parseBaseConfig()`)

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
