## Context

Bluetti devices with ESP32-based IoT modules expose a register block at `IOT_BASE_INFO` (11000) containing the module's model, serial, firmware version, WiFi/Ethernet/4G connection status, IP/MAC addresses, and SIM identifiers. A companion register at `IOT_ENABLE_INFO` (12161) provides enabled/disabled flags for each network interface.

Hardware probing on an EL100V2 (FW SW#3) confirmed:
- Register 11000 responds with 140 bytes (70 registers) — valid, parseable data
- The IoT module identifies as model "IOT", serial 2542016273527, firmware 802411
- WiFi MAC is present and valid, confirming ESP32 hardware
- WiFi STA mode is enabled but not connected (IPs all zero)
- BLE status bit shows `1` when our connection is active
- The APK's static `hasIot = false` flag is unreliable — hardware overrides it

Our current code has no awareness of these registers. The V2Base parse dispatch ends at register 3035 with no handler for 11000+.

## Goals / Non-Goals

**Goals:**
- Parse `IOT_BASE_INFO` (11000) into a structured dict with IoT model, serial, firmware, connection status, and networking info
- Include IoT reads in EL100V2 `control_commands` (hardware-probed to work)
- Display IoT info in `voltkeeper status` when present
- Include `IOT_BASE_INFO` as a block in verify tier 1, capturing firmware version
- Handle the APK's non-standard register encoding (swapped byte pairs, backwards SNs, register-half-swapped u32s)

**Non-Goals:**
- Add IoT reads to regular polling (only control_commands — on-demand, not every poll cycle)
- Parse `IOT_ENABLE_INFO` (12161) — the connection status word at offset 36-37 of `IOT_BASE_INFO` already tells us what's active
- Parse WiFi settings (SSID, password) or Matter info — out of scope for MVP
- Add IoT support to non-V2 devices (V1 protocol devices don't have this register block)
- Auto-detect IoT presence dynamically (always include in control_commands for probed devices, never for unprobed ones)

## Decisions

### Decision 1: Custom parsing method instead of struct field types

**Choice**: Parse IoT fields in a dedicated `_parse_iot_info(raw: bytes) -> dict` method in V2Base, bypassing the `DeviceStruct`/`DeviceField` system.

**Why**: The IoT register block uses non-standard field encodings that don't fit existing struct field types:
- Swapped-byte-pair ASCII strings (`getASCIIStr(data, true)`) 
- Backwards-hex device serials (`getDeviceSN`)
- Register-half-swapped u32 values (`bit32RegByteToNumber`)
- Pair-swapped IP addresses (`parseDeviceIp`)
- Pair-swapped MAC addresses (`parseDeviceMac`)
- Signed-byte RSSI (`parseShort('FF' + byte)`)
- Bit-packed status words (multiple bitfields in one register)

Adding 5+ new field types (MacField, IpField, DeviceSnField, Bit32SwapField, SignedRssiField) for a single register block is overkill. A custom method is simpler and matches the APK's approach.

**Alternative**: Add new field types to struct.py. Rejected — most of these formats appear only in the IoT block; no other register range uses them. Refactor into struct types later if needed for other device models.

### Decision 2: IoT struct lives in V2Base

**Choice**: Add `_build_iot_struct()` and `_parse_iot_info()` to V2Base.

**Why**: All V2 devices share the same IoT register layout and protocol. Individual device subclasses (EL100V2, eventually others) override `control_commands` to include the IoT read. The IoT module either exists and responds, or it doesn't — the parse path is the same.

### Decision 3: IoT read in control_commands only, not polling

**Choice**: Include `ReadHoldingRegisters(IOT_BASE_INFO, 70)` in EL100V2's `control_commands`, not in `polling_commands` or `_tlv_sections()`.

**Why**: 
- The APK only reads IoT info when the user views the IoT/WiFi settings screen (TimerScene.IOT_INFO), not during normal polling
- IoT info changes infrequently (firmware is static, IPs change only on WiFi reconnect)
- Reading 140 bytes every poll cycle adds unnecessary BLE traffic
- `control_commands` are read once at connect time (status command) or during verify — sufficient frequency

### Decision 4: EL100V2 only for MVP

**Choice**: Scope IoT reads to EL100V2 only. Add `IOT_BASE_INFO` constant and parsing to V2Base for reuse, but only include the read in EL100V2's `control_commands`.

**Why**: EL100V2 is hardware-probed to work. Other EL/AC devices may or may not have IoT modules. Don't add reads to unverified devices. When we verify other models, enabling IoT is a one-line override.

## Risks / Trade-offs

- **Risk**: `Read(11000, 70)` adds ~140 bytes per BLE round-trip on connect. **Mitigation**: This is comparable to existing INV_PV_INFO reads (140 bytes). Status/verify already read 6+ blocks; adding one more is acceptable overhead.
- **Risk**: Some devices may not respond to register 11000, causing timeout delay. **Mitigation**: Hardware-probed on EL100V2 — works. For unprobed devices, the read simply won't be in their control_commands. Add conditionally to other models only after hardware verification.
- **Risk**: The parse assumes register count 70 (covering bytes 0-139). If a device returns fewer registers, fields beyond the response length will be missing (graceful — just fewer keys in dict). **Mitigation**: parse method handles variable-length responses naturally (checks `len(data)` before reading each field).
