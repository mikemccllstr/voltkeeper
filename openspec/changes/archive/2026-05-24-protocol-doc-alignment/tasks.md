## 1. Protocol Bug Fixes

- [x] 1.1 Override `protocol_version` on each V1 device subclass (EB3A=1019, AC200L=1022, AC200M=1016, AC200PL=1022, AC300=0, AC500=0, EP500=1016)
- [x] 1.2 Write test confirming V1 probe uses subclass protocol_version instead of default 0
- [x] 1.3 Update `v1_base.py` comment from "APK 3.0.8" to "APK 3.0.9"
- [x] 1.4 Harmonize device name regex: extend `_DEVICE_NAME_SN_RE` in `bluetooth/__init__.py` to support `[A-Z][A-Z0-9]+` prefix pattern with `\d+` suffix (supporting both digit-only and alphanumeric-suffix models like HB500S)
- [x] 1.5 Replace `scrub.py`'s standalone `_NAME_SN_RE` with import of `_DEVICE_NAME_SN_RE` from `bluetooth/__init__.py`
- [x] 1.6 Write test confirming regex matches all current model prefixes, new model prefixes (AORA100_MINI, HB500S, etc.), and short serials
- [x] 1.7 Run `mise run check` to confirm no regressions

## 2. V1 Settable Control Registers

- [x] 2.1 Add missing register constants to `v1_base.py`: `MACHINE_MODE=3004`, `MACHINE_ADDRESS=3005`, `MAX_PV_CHARGE_CURRENT=3014`, `LOW_POWER_SETTINGS=3015`, `HIGH_POWER_SETTINGS=3016`, `MAX_DISCHARGING_CURRENT=3018`, `MAX_CHARGING_CURRENT_OF_GRID=3019`, `SYSTEM_TIME=3031`, `WORKING_TIME=3039`, `MAX_CHARGING_POWER=3057`, `MAX_DISCHARGE_POWER=3058`, `ECO_AUTO_OFF=3064`
- [x] 2.2 Add `FAULT_HISTORY_START=2000` to `probe.py` V1_BLOCKS
- [x] 2.3 Add new V1 settable fields to `AC200L` and `AC200PL` control struct (these models support the most controls per APK `DeviceFunction.flags`)
- [x] 2.4 Add applicable new V1 settable fields to `AC200M`, `AC300`, `AC500` control structs (subset based on APK flags)
- [x] 2.5 Write test confirming new register constants exist and have correct values
- [x] 2.6 Write test confirming AC200L control struct includes `SYSTEM_TIME`, `MAX_CHARGING_POWER`, `MAX_DISCHARGE_POWER`
- [x] 2.7 Run `mise run check` to confirm no regressions

## 3. V2 Control Registers

- [x] 3.1 Add register constants to `v2_base.py` for shared V2 control registers: `SYSTEM_TIME=2001`, `SYSTEM_TIME_ZONE=2004`
- [x] 3.2 Add AC2A-specific control fields to `ac2a.py` control struct: `system_time`, `system_timezone`, `ctrl_led`, `dc_eco_auto_off_time`, `dc_eco_power`, `ac_eco_auto_off_time`, `ac_eco_power`, `pv_type_set`, `pv2_type_set`, `pv_adv_set`, `ja12_enable`, `ctrl_grid`, `ctrl_feed`, `chg_max_voltage`, `chg_max_current`, `grid_max_power`, `grid_max_current`, `feed_max_power`, `feed_max_current`, `ems_ctrl_mode_set`, `rv_enable_set`
- [x] 3.3 Update AC2A writable ranges to include new register addresses
- [x] 3.4 Add applicable V2 control fields to `ac60.py` control struct (subset matching AC60's `DeviceFunction.flags`)
- [x] 3.5 Add grid control and feed-in control fields to `mqtt_client.py` `NORMAL_DEVICE_FIELDS` for Home Assistant MQTT discovery
- [x] 3.6 Write test confirming AC2A control struct includes `ctrl_grid` at register 2207
- [x] 3.7 Write test confirming AC2A writable ranges cover 2001–2026 and 2207–2216
- [x] 3.8 Run `mise run check` to confirm no regressions

## 4. TLV Protocol

- [x] 4.1 Create `src/voltkeeper/core/tlv.py` with `TlvItem` named tuple (slave_addr, reg_addr, length, value) and `TlvParser` class
- [x] 4.2 Implement `TlvParser.parse(data: bytes) -> list[TlvItem]` — detect magic bytes `0x40 0x00 0x04`, iterate items by length
- [x] 4.3 Raise `ParseError` on malformed TLV (item length exceeds remaining bytes)
- [x] 4.4 Add `NODE_INFO = 21000` constant to `v2_base.py`
- [x] 4.5 Add optional NODE_INFO read to V2 polling loop (gated by `has_sub_devices` device class flag)
- [x] 4.6 Integrate TLV dispatch: after parsing TLV items, dispatch each item's value to the appropriate DeviceStruct parser by reg_addr, tagged with slave_addr
- [x] 4.7 Write test: TlvParser detects magic bytes and parses single item
- [x] 4.8 Write test: TlvParser parses multiple items in sequence
- [x] 4.9 Write test: TlvParser raises ParseError on malformed (truncated) TLV data
- [x] 4.10 Write test: non-TLV response (no magic bytes) returns empty item list
- [x] 4.11 Run `mise run check` to confirm no regressions

## 5. Battery Pack Data

- [x] 5.1 Add `PACK_MAIN_INFO=6000`, `PACK_ITEM_INFO=6100`, `PACK_BMU_INFO=7200` constants to `v2_base.py`
- [x] 5.2 Define `PACK_MAIN_INFO` struct in `v2_base.py`: pack voltage (DecimalField), pack current (SignedDecimalField), pack SOC (UintField), pack temperature (TemperatureField), pack serial (BcdSerialField), cycle count (UintField), cell count (UintField)
- [x] 5.3 Define `PACK_ITEM_INFO` struct in `v2_base.py`: per-cell voltages as sequential `UintField` entries (supporting up to 16 cells)
- [x] 5.4 Add `has_battery_packs` flag to `BluettiDevice` (default `False`), override to `False` on AC2A
- [x] 5.5 Conditionally include pack register commands in V2 polling command list based on `has_battery_packs`
- [x] 5.6 Add pack fields (`packVoltage`, `packCurrent`, `packSoc`, `packTemperature`) to `mqtt_client.py` `NORMAL_DEVICE_FIELDS`
- [x] 5.7 Write test: PACK_MAIN_INFO struct parses voltage, current, SOC, temperature correctly
- [x] 5.8 Write test: PACK_ITEM_INFO struct parses 8 cell voltages, cells 9-16 return None
- [x] 5.9 Write test: AC2A polling command list excludes pack registers by default
- [x] 5.10 Write test: V2 device with `has_battery_packs=True` includes pack registers in polling commands
- [x] 5.11 Run `mise run check` to confirm no regressions

## 6. Device Model Expansion

- [x] 6.1 Create `src/voltkeeper/core/devices/aora_mini.py` with `AoraMiniBase(BluettiDevice)` base class — protocol version and register layout from APK analysis, marked with `# TODO(hardware):` comments
- [x] 6.2 Create `Aora100Mini`, `Aora30Mini`, `Aora200Mini` subclasses inheriting from `AoraMiniBase` with model-specific `type` and model number overrides
- [x] 6.3 Create `src/voltkeeper/core/devices/battery_packs.py` with `BatteryPackBase(BluettiDevice)` base class — register layout using PACK_MAIN_INFO, PACK_ITEM_INFO, PACK_BMU_INFO blocks; no inverter blocks
- [x] 6.4 Create `HB500S` and `BH500E` subclasses inheriting from `BatteryPackBase` with model-specific `type` overrides
- [x] 6.5 Update `_DEVICE_NAME_SN_RE` in `bluetooth/__init__.py` to match AORA100_MINI, AORA30_MINI, AORA200_MINI, HB500S, BH500E prefixes
- [x] 6.6 Update `_device_registry()` in `bluetooth/__init__.py` to map new model prefixes to their device classes
- [x] 6.7 Write test: `build_device("AORA100_MINI12345")` returns `Aora100Mini` instance
- [x] 6.8 Write test: `build_device("HB500S1234567890123")` returns `HB500S` instance
- [x] 6.9 Write test: `BatteryPackBase` has no inverter block references (INV_PV_INFO, INV_GRID_INFO, etc.)
- [x] 6.10 Write test: regex matches all 5 new model prefixes
- [x] 6.11 Run `mise run check` to confirm no regressions
