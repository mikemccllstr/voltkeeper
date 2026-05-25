# Modbus Registers

This page documents the complete Modbus register maps for both V1 and V2 protocols, including register addresses, field layout tables, real-time data parsing indices, base config parsing, and the TLV protocol format introduced in APK v3.0.9.

<!-- Extracted from FINDINGS.md §15.3, §15.5, §15.6, §15.7, and §15.9; V2 register map from ProtocolAddrV2 in APK v3.0.9 -->

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

## 15.9 TLV Protocol and Slave Address Routing *(v3.0.9+)*

Starting with APK v3.0.9, the V2 protocol gains support for **TLV-encoded (Type-Length-Value) multi-device responses** and **sub-device slave address routing** via the `ModbusV2Dispatcher`.

### TLV Protocol Format

When the node info response (register 21000) begins with hex bytes `40004`, the data is TLV-encoded rather than a flat field layout. Each item is a `ModbusTLVItem`:

| Field | Type | Description |
|-------|------|-------------|
| `slaveAddr` | int | Sub-device modbus slave address |
| `regAddr` | int | Modbus register address |
| `len` | int | Length of value data |
| `value` | List\<String\> | Hex string values |

The `ModbusV2Dispatcher.tvlHandle()` iterates TLV items and dispatches each one through the same `dispatch(regAddr, slaveAddr, data)` method used for direct modbus reads. This means a single TLV response can carry data for multiple sub-devices and multiple register addresses simultaneously.

### Slave Address Routing

For multi-device systems (e.g., parallel inverters, multiple battery packs), the `dispatch()` method takes both a **register address** (`regAddr`) and a **slave address** (`slaveAddr`). The slave address identifies which physical sub-device produced the data.

**2nd Generation IoT devices** (`getIs2GenerationIoT() == true`) use separate modbus slave addresses for battery packs. For `HOME_POWER` category devices, pack slave addresses start at 41, with the pack ID calculated as `(slaveAddr - 41) % 8`.

### Data Frame Structure

The modbus response frame received by the dispatcher is:
```
[slaveAddr] [fnCode?] [regAddrHi?] [data_0] [data_1] ... [data_N] [crcLo] [crcHi]
```
- `modbusBytes.get(0)` — slave address (hex string, parsed as int)
- `modbusBytes.subList(3, size-2)` — payload data
- Last 2 bytes — CRC16

### V2 Protocol (`ProtocolAddrV2`) — protocolVer ≥ 2000

The complete register map from `ProtocolAddrV2` in APK v3.0.9 (214 constants), organized by device category. All addresses below are decimal unless noted otherwise.

**Supervisory / System (addresses < 1000):**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 1 | `BASE_CONFIG` | R | 14-field base config (32 registers) |
| 100 | `APP_HOME_DATA` | R | Home page data snapshot |
| 700 | `OTA_START` | W | OTA start command |
| 720 | `OTA_STATUS` | R | OTA progress status |

**Inverter — Read Registers:**

| Address | Constant | Description |
|---------|----------|-------------|
| 1100 | `INV_BASE_INFO` | Inverter base info (model, SN, voltage type, ratings) |
| 1200 | `INV_PV_INFO` | PV/solar input info |
| 1300 | `INV_GRID_INFO` | Grid input/output info |
| 1400 | `INV_LOAD_INFO` | Load info |
| 1500 | `INV_INV_INFO` | Inverter status info |
| 1700 | `INV_METER_INFO` | Meter data |
| 1900 | `INV_METER_SETTINGS` | Meter settings |
| 3500 | `INV_TOTAL_ENERGY_INFO` | Lifetime energy totals |
| 3600 | `INV_CURR_YEAR_ENERGY_INFO` | Current year energy |
| 5000 | `TIME_CTRL_INFO_START` | Time control weekly mode info |
| 2500 | `MICRO_INV_ADV_SETTINGS` | Micro inverter advanced settings |
| 4200 | `WT_INFO` | Wind turbine info |
| 4400 | `WT_SETTINGS` | Wind turbine settings |
| 3000 | `LOG_HISTORY_INFO` | Log/fault history |
| 30001 | `ACTIVE_INFO` | Activation info |

**Inverter — Write/Control Registers:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 2000 | `INV_BASE_SETTINGS` | R/W | Base settings |
| 2001 | `SYSTEM_TIME` | R/W | System clock |
| 2004 | `SYSTEM_TIME_ZONE` | R/W | System timezone |
| 2005 | `WORKING_MODE` | R/W | Working mode |
| 2006 | `CTRL_EVENT` | W | Control events |
| 2007 | `CTRL_LED` | R/W | LED control |
| 2008 | `CTRL_METER` | R/W | Meter control |
| 2010 | `CTRL_INVERTER` | R/W | Inverter power control |
| 2011 | `AC_SWITCH` | R/W | AC output switch |
| 2012 | `DC_SWITCH` | R/W | DC output switch |
| 2013 | `SYSTEM_POWER_OFF` | W | System power off |
| 2014 | `CTRL_DC_ECO_MODE` | R/W | DC ECO mode |
| 2015 | `DC_ECO_AUTO_OFF_TIME` | R/W | DC ECO auto-off time |
| 2016 | `DC_ECO_POWER` | R/W | DC ECO power threshold |
| 2017 | `CTRL_AC_ECO_MODE` | R/W | AC ECO mode |
| 2018 | `AC_ECO_AUTO_OFF_TIME` | R/W | AC ECO auto-off time |
| 2019 | `AC_ECO_POWER` | R/W | AC ECO power threshold |
| 2020 | `CHARGING_MODE` | R/W | Charging mode (Standard/Turbo/Silent) |
| 2021 | `CTRL_SUPER_POWER_MODE` | R/W | Power lifting mode |
| 2022 | `SYS_SOC_LOW_CAPACITY` | R/W | Low SOC threshold |
| 2023 | `SYS_SOC_HIGH_CAPACITY` | R/W | High SOC threshold |
| 2026 | `SET_HISTORY_ENERGY_TYPE` | W | History energy type selector |
| 2027 | `SET_CURR_ENERGY_TYPE` | W | Current energy type selector |
| 2028 | `SET_LOG_HISTORY_PAGE` | W | Log history page selector |
| 2029 | `CTRL_CHG_DSG_TIME` | W | Charge/discharge time control |
| 2030 | `WORKING_TIME_START` | R/W | Working time start |
| 2060 | `PV_TYPE_SET` | R/W | PV type setting |
| 2061 | `PV2_TYPE_SET` | R/W | PV2 type setting |
| 2066 | `CTRL_ALARM_SOUND` | R/W | Alarm sound toggle |
| 2067 | `LCD_SCREEN_TIME` | R/W | LCD screen timeout |
| 2075 | `SOC_SET_LOW` | R/W | SOC low setpoint |
| 2078 | `LED_COLOR_SET` | R/W | LED color selection |
| 2080 | `PACK_NUM_SET_SHOW` | R/W | Pack number display setting |
| 2081 | `INV_NUM_SET` | R/W | Inverter count setting |
| 2083 | `SOC_SET_HIGH` | R/W | SOC high setpoint |
| 2084 | `PV_ADV_SET` | R/W | PV advanced settings |
| 2086 | `JA12_ENABLE` | R/W | 12V output enable |
| 2200 | `INV_ADVANCE_SETTINGS` | R/W | Advanced settings (login password required) |
| 2206 | `SYSTEM_FACTORY_RESET` | W | Factory reset |
| 2207 | `CTRL_GRID` | R/W | Grid control |
| 2208 | `CTRL_FEED` | R/W | Grid feed-in control |
| 2209 | `INV_VOLTAGE` | R/W | Output voltage (120/220/230/240V) |
| 2210 | `INV_FREQ` | R/W | Output frequency (50/60Hz) |
| 2211 | `CHG_MAX_VOLTAGE` | R/W | Max charge voltage |
| 2212 | `CHG_MAX_CURRENT` | R/W | Max charge current |
| 2213 | `GRID_MAX_POWER` | R/W | Max grid input power |
| 2214 | `GRID_MAX_CURRENT` | R/W | Max grid input current |
| 2215 | `FEED_MAX_POWER` | R/W | Max feed-in power |
| 2216 | `FEED_MAX_CURRENT` | R/W | Max feed-in current |
| 2217 | `GRID_OFF_AC_PV_POWER` | R/W | Off-grid AC PV power limit |
| 2218 | `USER_REGION_SETTING` | R/W | User region setting |
| 2219 | `CTRL_PV1_PARALLEL` | R/W | PV1 parallel control |
| 2225 | `CTRL_GRID_PLUS_MODE` | R/W | Grid+ mode toggle |
| 2226 | `CTRL_POWER_OUTPUT_STATE_SAVE` | R/W | Power output state save |
| 2227 | `ADVANCED_SETTINGS_CTRL_METER` | R/W | Advanced meter control |
| 2228 | `ADVANCED_SETTINGS_METER_TYPE` | R/W | Meter type selection |
| 2229 | `ADV_SETTINGS_CTRL_INV` | R/W | Advanced inverter control |
| 2230 | `ADV_SETTINGS_INV_ADDR` | R/W | Inverter address setting |
| 2231 | `ADV_SETTINGS_CT_TEST` | R/W | CT sensor test |
| 2232 | `ADV_SETTINGS_OTHER` | R/W | Other advanced settings |
| 2233 | `ADV_BATTERY_AGING` | R/W | Battery aging mode |
| 2241 | `EMS_CTRL_MODE_SET` | R/W | EMS control mode |
| 2242 | `ADV_SETTINGS_OTHER_2` | R/W | Other advanced settings 2 |
| 2243 | `ADV_CHARGING_STATION_MODEL` | R/W | EV charging station model |
| 2244 | `ADV_CT_RATIO` | R/W | CT ratio setting |
| 2245 | `ADV_AC_CT_TEST` | R/W | AC CT sensor test |
| 2246 | `GEN_SET` | R/W | Generator settings |
| 2267 | `METER_CTRL_GRID` | R/W | Meter grid control |
| 2269 | `ADV_PV_SET` | R/W | PV advanced settings |
| 2271 | `DC_OUTPUT_VOLT_LEVEL` | R/W | DC output voltage level |
| 2275 | `ALT_DELAYS_SET` | R/W | Altitude delay settings |
| 2276 | `RV_ENABLE_SET` | R/W | RV mode enable |
| 2280 | `HEAT_PUMP_ENABLE` | R/W | Heat pump enable |
| 2304 | `MULTI_PEAK_ENABLE` | R/W | Multi-peak shaving enable |
| 30901 | `TEST_SETTINGS` | R/W | Factory test settings |

**Grid Certification Settings:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 2400 | `CERT_SETTINGS_INFO` | R/W | Grid cert country/settings |
| 2401 | `GRID_CERT_COUNTRY` | R/W | Grid cert country code |
| 2402 | `GRID_UV1_VAL` | R/W | Under-voltage level 1 |
| 2403 | `GRID_UV1_TIME` | R/W | Under-voltage time 1 |
| 2404 | `GRID_UV2_VAL` | R/W | Under-voltage level 2 |
| 2405 | `GRID_UV2_TIME` | R/W | Under-voltage time 2 |
| 2406 | `POWER_FACTOR` | R/W | Power factor setting |
| 2407 | `CERT_DIVISION` | R/W | Cert division enable |
| 2408 | `CERT_SETTINGS_MODE_ENABLE` | R/W | Cert mode enable |
| 2409 | `POWER_RATE_LIMIT` | R/W | Power rate limit |
| 2410 | `GRID_AVG_OV_VAL` | R/W | Grid average over-voltage |
| 2411 | `GRID_OV1_VAL` | R/W | Over-voltage level 1 |
| 2412 | `GRID_OV1_TIME` | R/W | Over-voltage time 1 |
| 2413 | `GRID_OV2_VAL` | R/W | Over-voltage level 2 |
| 2414 | `GRID_OV2_TIME` | R/W | Over-voltage time 2 |
| 2415 | `POWER_REACTIVE_RATIO` | R/W | Reactive power ratio |
| 2416 | `VOLT_WATT1` | R/W | Volt-Watt point 1 |
| 2417 | `VOLT_WATT2` | R/W | Volt-Watt point 2 |
| 2419 | `GRID_UF_VAL` | R/W | Under-frequency level 1 |
| 2420 | `GRID_UF_TIME` | R/W | Under-frequency time 1 |
| 2421 | `GRID_UF2_VAL` | R/W | Under-frequency level 2 |
| 2422 | `GRID_UF2_TIME` | R/W | Under-frequency time 2 |
| 2423 | `V_VAR_VOLT_WATT1` | R/W | Volt-Var-Watt point 1 |
| 2424 | `V_VAR_VOLT_WATT2` | R/W | Volt-Var-Watt point 2 |
| 2425 | `V_VAR_VOLT_WATT3` | R/W | Volt-Var-Watt point 3 |
| 2426 | `V_VAR_VOLT_WATT4` | R/W | Volt-Var-Watt point 4 |
| 2427 | `GRID_OF_VAL` | R/W | Over-frequency level 1 |
| 2428 | `GRID_OF_TIME` | R/W | Over-frequency time 1 |
| 2429 | `GRID_OF2_VAL` | R/W | Over-frequency level 2 |
| 2430 | `GRID_OF2_TIME` | R/W | Over-frequency time 2 |
| 2435 | `GRID_VOLT_MIN_VAL` | R/W | Grid min voltage |
| 2436 | `GRID_VOLT_MAX_VAL` | R/W | Grid max voltage |
| 2437 | `GRID_FREQ_MIN_VAL` | R/W | Grid min frequency |
| 2438 | `GRID_FREQ_MAX_VAL` | R/W | Grid max frequency |
| 2439 | `GRID_RETRY_TIME` | R/W | Grid reconnection retry time |
| 40044 | `CERT_SETTINGS_EXT` | R/W | Cert settings extension |
| 40181 | `ANTI_BACKFLOW_CERTIFICATION` | R/W | Anti-backflow certification |
| 40187 | `CERT_SETTINGS_INFO_2` | R/W | Cert settings part 2 (also `GRID_UV3_VAL`) |
| 40188 | `GRID_UV3_TIME` | R/W | Under-voltage time 3 |
| 40189 | `GRID_UV4_VAL` | R/W | Under-voltage level 4 |
| 40190 | `GRID_UV4_TIME` | R/W | Under-voltage time 4 |
| 40191 | `GRID_UV5_VAL` | R/W | Under-voltage level 5 |
| 40192 | `GRID_UV5_TIME` | R/W | Under-voltage time 5 |
| 40199 | `GRID_OV3_VAL` | R/W | Over-voltage level 3 |
| 40200 | `GRID_OV3_TIME` | R/W | Over-voltage time 3 |
| 40201 | `GRID_OV4_VAL` | R/W | Over-voltage level 4 |
| 40202 | `GRID_OV4_TIME` | R/W | Over-voltage time 4 |
| 40203 | `GRID_OV5_VAL` | R/W | Over-voltage level 5 |
| 40204 | `GRID_OV5_TIME` | R/W | Over-voltage time 5 |

**Battery Pack:**

| Address | Constant | Description |
|---------|----------|-------------|
| 6000 | `PACK_MAIN_INFO` | Pack main info |
| 6100 | `PACK_ITEM_INFO` | Pack item/cell info |
| 6300 | `PACK_SUB_PACK_INFO` | Sub-pack info |
| 6300–6999 | (range) | Pack cell voltage read tasks (one per cell) |
| 7000 | `PACK_SETTINGS_INFO` | Pack settings / pack ID config |
| 7200 | `PACK_BMU_INFO` | BMU info |

**IoT / Network:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 11000 | `IOT_BASE_INFO` | R | IoT module info |
| 11106 | `WIFI_MULT_INFO` | R | WiFi multi-info |
| 11127 | `IOT_SERVER_BLE_SN` | R | Server BLE serial number |
| 12002 | `IOT_SETTINGS_INFO` | R/W | IoT/WiFi settings |
| 12161 | `IOT_ENABLE_INFO` | R/W | IoT enable state info |
| 12162 | `IOT_ENABLE_HI` | R/W | IoT enable high |
| 12163 | `DISASTER_WARNING_MODE` | R/W | Disaster/natural disaster warning mode |
| 12170 | `IOT_ADDR_SORT` | R/W | IoT address sort |
| 12174 | `IOT_NETMASK_GATEWAY` | R/W | IoT subnet mask & gateway |
| 12185 | `IOT_BLE_SERVER_SET` | R/W | BLE server settings |
| 12195 | `IOT_BLE_CLIENT_SET` | R/W | BLE client settings |
| 12205 | `IOT_DISPLAY_SET` | R/W | IoT display settings |
| 13088 | `IOT_MATTER_INFO` | R/W | Matter protocol info |
| 13120 | `IOT_OTA_CTRL_ENABLE` | R/W | OTA control enable |
| 13500 | `IOT_WIFI_MESH` | R/W | WiFi mesh settings |
| 13506 | `WIFI_MESH_ENABLE` | R/W | WiFi mesh enable |
| 13509 | `WIFI_STATION_BSSID` | R/W | WiFi station BSSID |
| 13600 | `IOT_EXTENSION_SETTINGS` | R/W | IoT extension settings |
| 13603 | `IOT_BLE_SERVER_KEY` | R | Server BLE key (FPS pairing) |
| 13611 | `WIFI_STATION_MULT1` | R/W | WiFi station multi-info 1 |
| 13624 | `WIFI_STATION_MULT2` | R/W | WiFi station multi-info 2 |
| 13776 | `BLE_CLIENT_PAIR_SN` | R | BLE client pair serial number |

**HMI / Display:**

| Address | Constant | Description |
|---------|----------|-------------|
| 14000 | `HMI_INFO` | HMI/display info |

**Smart Plug:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 14500 | `SMART_PLUG_INFO` | R | Smart plug info |
| 14700 | `SMART_PLUG_SETTINGS` | R/W | Smart plug settings |
| 14701 | `SMART_PLUG_SET_ENABLE_1` | R/W | Smart plug enable 1 |

**Charging Pile / EV Charger:**

| Address | Constant | Description |
|---------|----------|-------------|
| 15000 | `CHARGING_PILE_INFO` | Charging pile info |

**DCDC:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 15500 | `DCDC_INFO` | R | DCDC converter info |
| 15600 | `DCDC_SETTINGS` | R/W | DCDC settings |
| 15603 | `DCDC_VOLT_SET_DC2` | R/W | DC2 voltage setting |
| 15606 | `DCDC_CURRENT_SET_DC3` | R/W | DC3 current setting |
| 15614 | `DCDC_CHG_MODE_1` | R/W | DC charge mode 1 |
| 15621 | `DCDC_POWER_DC3_SET` | R/W | DC3 power setting |
| 15625 | `DCDC_SET_4` | R/W | DCDC setting 4 |
| 15626 | `DCDC_SET_5` | R/W | DCDC setting 5 |
| 15627 | `DCDC_SET_POWER` | R/W | DCDC power setting |
| 15634 | `DCDC_IOT_PCS_MODE` | R/W | DCDC IoT/PCS mode |

**DC Hub:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 15700 | `DC_HUB_INFO` | R | DC hub info |
| 15750 | `DC_HUB_SETTINGS` | R/W | DC hub settings |

**Panel:**

| Address | Constant | Description |
|---------|----------|-------------|
| 16000 | `PANEL_BASE_INFO` | Panel base info |
| 16100 | `PANEL_DC_INFO` | Panel DC info |
| 16200 | `PANEL_AC_INFO` | Panel AC info |
| 16300 | `PANEL_PROTECT_INFO` | Panel protection info |
| 16400 | `PANEL_SETTINGS_BASE` | Panel base settings |
| 16404 | `PANEL_SET_1` | Panel setting 1 |
| 16421 | `PANEL_SOC_SET_START_AC` | Panel SOC start AC |
| 16427 | `PANEL_SOC_SET_START_DC` | Panel SOC start DC |
| 16500 | `PANEL_SETTINGS_MAIN` | Panel main settings |

**ATS:**

| Address | Constant | Description |
|---------|----------|-------------|
| 17000 | `ATS_INFO` | Automatic transfer switch info |

**AT1:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 17100 | `AT1_BASE_INFO` | R | AT1 base info |
| 17400 | `AT1_SETTINGS_GRID_ENABLE` | R/W | AT1 grid enable settings |
| 17401 | `AT1_FORCE_ENABLE_2` | R/W | AT1 force enable 2 |
| 17402 | `AT1_FORCE_ENABLE_3` | R/W | AT1 force enable 3 |
| 17406 | `AT1_TIMER_ENABLE_1` | R/W | AT1 timer enable 1 |
| 17407 | `AT1_TIMER_ENABLE_2` | R/W | AT1 timer enable 2 |
| 17408 | `AT1_TIMER_ENABLE_3` | R/W | AT1 timer enable 3 |
| 17409 | `AT1_PORN_TYPE_SET_PCS` | R/W | AT1 port type PCS |
| 17410 | `AT1_PORN_TYPE_SET` | R/W | AT1 port type |
| 17411 | `AT1_INTERMITTENT_LINKAGE_SET` | R/W | AT1 intermittent linkage |
| 17412 | `AT1_PROTECT_SET_GRID_L1` | R/W | AT1 grid protection L1 |
| 17415 | `AT1_PROTECT_SET_SL1_L1` | R/W | AT1 SL1 protection L1 |
| 17418 | `AT1_PROTECT_SET_SL2_L1` | R/W | AT1 SL2 protection L1 |
| 17421 | `AT1_PROTECT_SET_SL3_L1` | R/W | AT1 SL3 protection L1 |
| 17424 | `AT1_PROTECT_SET_SL4_L1` | R/W | AT1 SL4 protection L1 |
| 17430 | `AT1_SOC_SET_SL1_L1` | R/W | AT1 SL1 SOC threshold |
| 17433 | `AT1_SOC_SET_SL2_L1` | R/W | AT1 SL2 SOC threshold |
| 17436 | `AT1_SOC_SET_SL3_L1` | R/W | AT1 SL3 SOC threshold |
| 17441 | `AT1_SOC_SET_SL4_L3` | R/W | AT1 SL4 SOC threshold L3 |
| 17442 | `AT1_MAX_CURRENT_GRID` | R/W | AT1 max grid current |
| 17443 | `AT1_MAX_CURRENT_SL1` | R/W | AT1 max SL1 current |
| 17444 | `AT1_MAX_CURRENT_SL2` | R/W | AT1 max SL2 current |
| 17445 | `AT1_MAX_CURRENT_SL3` | R/W | AT1 max SL3 current |
| 17446 | `AT1_MAX_CURRENT_SL4` | R/W | AT1 max SL4 current |
| 17447 | `AT1_MAX_CURRENT_PCS` | R/W | AT1 max PCS current |
| 17448 | `AT1_MAX_POWER_OPP_GRID_L1` | R/W | AT1 grid L1 max power (lower) |
| 17451 | `AT1_MAX_POWER_OPP_SL1_L1` | R/W | AT1 SL1 L1 max power (lower) |
| 17454 | `AT1_MAX_POWER_OPP_SL2_L1` | R/W | AT1 SL2 L1 max power (lower) |
| 17457 | `AT1_MAX_POWER_OPP_SL3_L1` | R/W | AT1 SL3 L1 max power (lower) |
| 17460 | `AT1_MAX_POWER_OPP_SL4_L1` | R/W | AT1 SL4 L1 max power (lower) |
| 17463 | `AT1_MAX_POWER_UPP_GRID_L1` | R/W | AT1 grid L1 max power (upper) |
| 17466 | `AT1_MAX_POWER_UPP_SL1_L1` | R/W | AT1 SL1 L1 max power (upper) |
| 17469 | `AT1_MAX_POWER_UPP_SL2_L1` | R/W | AT1 SL2 L1 max power (upper) |
| 17472 | `AT1_MAX_POWER_UPP_SL3_L1` | R/W | AT1 SL3 L1 max power (upper) |
| 17475 | `AT1_MAX_POWER_UPP_SL4_L1` | R/W | AT1 SL4 L1 max power (upper) |
| 17487 | `AT1_ENABLE_1` | R/W | AT1 enable 1 |
| 17488 | `AT1_ENABLE_2` | R/W | AT1 enable 2 |
| 17800 | `AT1_SETTINGS_DELAY` | R/W | AT1 settings delay |
| 19365 | `AT1_TIMER_SET_SL1_L1` | R/W | AT1 SL1 timer settings L1 |
| 19385 | `AT1_TIMER_SET_SL1_L2` | R/W | AT1 SL1 timer settings L2 |
| 19425 | `AT1_TIMER_SET_SL2_L1` | R/W | AT1 SL2 timer settings L1 |
| 19445 | `AT1_TIMER_SET_SL2_L2` | R/W | AT1 SL2 timer settings L2 |
| 19485 | `AT1_TIMER_SET_SL3_L1` | R/W | AT1 SL3 timer settings L1 |
| 19505 | `AT1_TIMER_SET_SL3_L2` | R/W | AT1 SL3 timer settings L2 |
| 19545 | `AT1_TIMER_SET_SL4_L1` | R/W | AT1 SL4 timer settings L1 |
| 19565 | `AT1_TIMER_SET_SL4_L2` | R/W | AT1 SL4 timer settings L2 |

**EPAD:**

| Address | Constant | Description |
|---------|----------|-------------|
| 18000 | `EPAD_BASE_INFO` | EPAD base info |
| 18300 | `EPAD_BASE_SETTINGS` | EPAD base settings |
| 18400 | `EPAD_BASE_LIQUID_POINT1` | EPAD liquid calibration point 1 |
| 18500 | `EPAD_BASE_LIQUID_POINT2` | EPAD liquid calibration point 2 |
| 18600 | `EPAD_BASE_LIQUID_POINT3` | EPAD liquid calibration point 3 |

**Common Settings (multi-device):**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 19000 | `COMM_SOC_SETTINGS` | R/W | Common SOC threshold settings |
| 19100 | `COMM_DELAY_SETTINGS` | R/W | Common delay settings |
| 19200 | `COMM_SCHEDULED_CHG_DSG` | R/W | Scheduled charge/discharge settings |
| 19300 | `COMM_TIMER_SETTINGS` | R/W | Common timer settings |
| 19305 | `COMM_TIMER_SETTINGS_1` | R/W | Common timer tasks (group 1) |
| 19425 | `COMM_TIMER_SETTINGS_2` | R/W | Common timer tasks (group 2) |

**Time of Use / Energy Management:**

| Address | Constant | R/W | Description |
|---------|----------|-----|-------------|
| 26000 | `TOU_CTRL_ENABLE` | R/W | TOU control enable |
| 26001 | `TOU_CTRL` | R/W | TOU time-of-use settings |

**Node Info / Multi-Device Topology:**

| Address | Constant | Description |
|---------|----------|-------------|
| 21000 | `NODE_INFO` | Multi-device node topology info (TLV or flat, depending on version) |
| 40000 | `COMM_DATA_OTHER` | Common data (home storage settings or host file log depending on device) |

**Boot Upgrade:**

| Address | Constant | Description |
|---------|----------|-------------|
| 29770 | `BOOT_UPGRADE_SUPPORT` | Boot upgrade support status |
| 29772 | `BOOT_SOFTWARE_INFO` | Boot software version info |

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
