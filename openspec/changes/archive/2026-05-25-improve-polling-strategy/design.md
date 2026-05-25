## Context

Currently, `DeviceHandler._poll_once()` iterates `device.polling_commands` — a fixed list of `ReadHoldingRegisters` — and executes each one as a separate BLE write-read cycle. For V2 devices, this is 6-8 commands. Each is a full round-trip over BLE: write to characteristic, wait for notify response. At 800-1000ms BLE latency per command, a single poll cycle takes 5-8 seconds.

Analysis of the APK v3.0.9 (`docs/source/protocol/polling-strategy.md`) reveals it uses three optimizations: TLV bundling (one request, one response with all blocks), runtime NODE_INFO discovery (write-then-read on register 21000 to get sub-device topology), and time-sliced polling (fast telemetry every cycle, slow blocks every few cycles).

Our `has_battery_packs` and `has_sub_devices` flags are hardcoded `False` on all device classes — no runtime discovery. Our probe tool emits raw hex blocks but doesn't decode ctrl_event capabilities.

## Goals / Non-Goals

**Goals:**
1. Implement TLV-bundled Modbus read requests so one BLE round-trip fetches all register blocks
2. Poll NODE_INFO at connect time, parse the TLV response, and use discovered topology to conditionally include pack/sub-device registers
3. Implement counter-based time-sliced polling for slow-changing registers
4. Decode ctrl_event capabilities in the probe tool's YAML output

**Non-Goals:**
- Full `DeviceFunction` lookup table (120+ device models) — we stay with per-device-class fields
- MQTT polling changes — time-slicing applies to BLE polling only
- V1 protocol changes — V1 has no NODE_INFO and only one poll command; time-slicing is irrelevant
- Write operations — polling only; write tasks remain single-register commands

## Decisions

### Decision 1: TLV Bundling via a New `TlvReadTask` Command

**Choice:** Create a new command class `TlvReadHoldingRegisters` that encodes multiple register block requests into one Modbus frame with TLV headers, matching the APK's `ModbusTaskUtils.buildTLVReadTask()`.

**Alternatives considered:**
- Extend existing `ReadHoldingRegisters` with TLV mode — mixes concerns, makes the simple case complex
- Compose commands client-side — this is what we need, a new command type is cleanest

The command packet structure is:
```
<slave_addr> 03 <0x40 0x00 0x04> <item_count>
  for each item: <addr_hi> <addr_lo> <len_hi> <len_lo>
<CRC>
```
Response is the existing TLV format already parsed by `TlvParser.parse()`.

### Decision 2: NODE_INFO Polled at Connect, Then Conditionally

**Choice:** Poll NODE_INFO once after BLE connect (during `DeviceHandler.run()`) before entering the main polling loop. Parse the response with `TlvParser`. Use discovered topology to dynamically include/exclude PACK_MAIN_INFO and PACK_ITEM_INFO from the subsequent poll cycles.

**Alternatives considered:**
- Poll every cycle — wasteful; topology doesn't change during a session
- Hardcode has_battery_packs per device — we already do this but it's wrong for new devices and multi-pack configs

The `readNodeInfo` call in the APK writes a version to register 21000 to trigger the response. We should do the same: write `version=1` to NODE_INFO, then read the response.

### Decision 3: Time-Slicing via Counter Modulo 3

**Choice:** Add a `_poll_counter` to `V2Base` (or `DeviceHandler`). On each poll cycle:
- Every cycle: HOME (100) + CONTROLS (2000) + ADV_SETTINGS (2200) + NODE_INFO/PACK (if discovered)
- Every 3rd cycle: additionally INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO

This matches the APK's `timerCounter % 3` pattern for slow registers.

**Alternatives considered:**
- Separate poll intervals per register block — over-engineered, APK doesn't do it
- Just reduce to 2 commands (HOME + everything else bundled) — loses the benefit of TLV bundling for slow registers
- Skip entirely — we'd still poll 6+ register ranges even with TLV bundling, wasting BLE bandwidth

### Decision 4: Probe ctrl_event from Existing Sweep Data

**Choice:** After the APP_HOME_DATA sweep in `probe_device()`, parse the ctrl_event register (offset 48 bytes into the 62-register response = register 124) and decode capabilities. Add a `capabilities` section to the YAML output. Use the AC2A's `CTRL_EVENT_BITS` as the capability bit definitions.

**Alternatives considered:**
- Additional probe read — wasteful, data is already in the sweep
- Separate probe command — unnecessary complexity

## Risks / Trade-offs

- **[TLV response size]** TLV responses can be large (hundreds of bytes). Risk: BLE MTU limits may fragment the response across notifications. → Mitigation: Our existing `_on_notification` already reassembles fragmented responses by expected size; this should handle multi-packet TLV responses.

- **[NODE_INFO write may fail on devices that don't support it]** Risk: Some V2 devices may not support the write-then-read pattern for NODE_INFO. → Mitigation: Wrap the NODE_INFO probe in a try/except; if it fails, fall back to current static polling (no packs, no sub-devices). This is strictly better than never trying.

- **[Time-slicing may miss write responses]** Risk: If a user writes a setting to a slow register (e.g., INV_BASE_SETTINGS), and the next poll doesn't read it for 3 cycles, the UI shows stale data. → Mitigation: After a write, force the next poll to include all registers regardless of counter.

- **[AC2A ctrl_event bits may not match other devices]** Risk: The AC2A's 11-bit definition may not be universal for all V2 devices. → Mitigation: The probe output includes both the raw ctrl_event hex value AND the decoded capabilities, so the raw data is preserved even if the decode is wrong for a new device.
