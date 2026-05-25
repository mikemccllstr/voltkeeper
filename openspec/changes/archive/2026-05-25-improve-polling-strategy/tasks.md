## 1. TLV Request Encoding

- [x] 1.1 Add `TlvReadHoldingRegisters` command class to `core/commands.py` that encodes multiple register address/length pairs into a TLV Modbus read frame
- [x] 1.2 Add `build_tlv_read_task()` helper that constructs a TLV command from a list of `(addr, len)` tuples, matching the APK's `ModbusTaskUtils.buildTLVReadTask()` format
- [x] 1.3 Write tests for TLV request encoding: single block, multiple blocks, CRC correctness

## 2. NODE_INFO Runtime Discovery

- [x] 2.1 Add `read_node_info()` method to `V2Base` that writes version=1 to register 21000 then reads the TLV response
- [x] 2.2 Add `_discovered_packs` and `_discovered_sub_devices` instance attributes to `V2Base`, populated from NODE_INFO TLV response
- [x] 2.3 Call `read_node_info()` from `DeviceHandler` during connect (before entering main polling loop), with try/except fallback
- [x] 2.4 Update `polling_commands` property to conditionally include PACK_MAIN_INFO/PACK_ITEM_INFO based on `_discovered_packs` (with `has_battery_packs` as fallback override)
- [x] 2.5 Write tests for: NODE_INFO success discovers packs, NODE_INFO failure falls back, NODE_INFO empty returns no packs

## 3. TLV-Bundled Polling

- [x] 3.1 Add `use_tlv_polling` property to `V2Base` (returns True for protocol >= 2000, overridable)
- [x] 3.2 Add `tlv_polling_commands` property that returns a single `TlvReadHoldingRegisters` command bundling all register blocks for the current cycle
- [x] 3.3 Update `V2Base.parse()` to handle TLV-bundled responses — parse TLV items and dispatch each to the appropriate struct parser
- [x] 3.4 Update `DeviceHandler._poll_once()` to use TLV-bundled polling when `use_tlv_polling` is True, falling back to individual commands otherwise
- [x] 3.5 Write tests for: TLV poll sends single command, TLV response dispatches to all structs, non-TLV devices still use individual commands

## 4. Time-Sliced Polling

- [x] 4.1 Add `_poll_counter` instance attribute to `V2Base`, incremented after each poll cycle, wrapping at 9999
- [x] 4.2 Add `_force_full_poll` flag set to True after any write operation
- [x] 4.3 Split register blocks into fast (HOME, CONTROLS, ADV_SETTINGS, PACK, NODE_INFO) and slow (INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO)
- [x] 4.4 Update `polling_commands` / `tlv_polling_commands` to exclude slow blocks when counter % 3 != 0 and `_force_full_poll` is False
- [x] 4.5 Write tests for: slow blocks excluded on counter % 1, included on counter % 3, forced full poll after write, counter wraps

## 5. Probe ctrl_event Capabilities

- [x] 5.1 After APP_HOME_DATA sweep in `probe_device()`, parse register 124 (ctrl_event) from the raw hex response
- [x] 5.2 Decode ctrl_event using the AC2A's `CTRL_EVENT_BITS` definition (moved to a shared location importable by both probe and device code)
- [x] 5.3 Add `capabilities` section to probe YAML output with `ctrl_event` raw value and `decoded` dict
- [x] 5.4 Write tests for: ctrl_event decoded in V2 probe, omitted when APP_HOME_DATA fails, omitted for V1 devices

## 6. Documentation

- [x] 6.1 Update `docs/source/protocol/polling-strategy.md` to reflect implementation decisions (TLV encoding format, NODE_INFO polling trigger, time-slicing counters)
- [x] 6.2 Update `docs/source/protocol/modbus-registers.md` to document the TLV read request encoding format
