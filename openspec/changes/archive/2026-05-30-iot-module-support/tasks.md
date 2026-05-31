## 1. Register Constants and Parsing

- [x] 1.1 Add `IOT_BASE_INFO = 11000` and `IOT_ENABLE_INFO = 12161` constants to `v2_base.py`
- [x] 1.2 Add `_parse_iot_info(raw: bytes) -> dict` method to `V2Base` with APK-matching parsing: swapped ASCII for model, backwards-hex for SN, register-half-swapped u32 for firmware, pair-swapped IPs and MACs, signed RSSI, bit-packed status word
- [x] 1.3 Add dispatch for `IOT_BASE_INFO <= address < IOT_BASE_INFO + 100` in `V2Base.parse()` to call `_parse_iot_info()`

## 2. Device Model Updates

- [x] 2.1 Add `ReadHoldingRegisters(IOT_BASE_INFO, 70)` to `El100V2.control_commands` (hardware-probed)

## 3. Reusable Utilities (optional)

- [x] 3.1 Move IOT_BASE_INFO parsing helpers (_mac, _ip, _signed_rssi, _ascii_swapped, _device_sn, _bit32) from test_iot_probe.py into a reusable module (e.g., `core/utils.py` or a new `core/iot_parse.py`)

## 4. Status Display

- [x] 4.1 Show IoT connection status in `voltkeeper status` when IoT data is present: active connection mode, firmware version, WiFi IP/SSID if connected, BLE status

## 5. Verify Integration

- [x] 5.1 Update `verify.py` `run_tier1` to parse IOT_BASE_INFO block when control_commands include it, recording it as block key `"11000"`

## 6. Tests

- [x] 6.1 Add `test_iot_parsing` to `test_voltkeeper.py`: parse known IoT response bytes, assert model/sn/firmware/status word values
- [x] 6.2 Add `test_el100v2_control_commands_includes_iot` to `test_voltkeeper.py`: assert 11000 present in control_commands with quantity 70
- [x] 6.3 Add `test_iot_no_response` to `test_voltkeeper.py`: assert empty dict returned on short/empty data

## 7. Quality Checks

- [x] 7.1 Run `mise run lint` and fix any issues
- [x] 7.2 Run `mise run typecheck` and fix any issues
- [x] 7.3 Run `mise run test` and confirm all tests pass

## 8. Hardware Verification

- [x] 8.1 Run `voltkeeper verify DC:B4:D9:46:73:96 --tier 3` and confirm block 11000 appears with status=pass
- [x] 8.2 Run `voltkeeper status DC:B4:D9:46:73:96 -v` and confirm IoT info is displayed
