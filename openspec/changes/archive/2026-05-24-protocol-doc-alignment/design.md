## Context

The voltkeeper Python implementation was built against reverse-engineered findings from the Bluetti Android APK v3.0.8. The `apk-309` branch contains updated protocol documentation based on APK v3.0.9, which adds 5 device models, a TLV sub-protocol for multi-device systems, expanded register maps (V1 grows from ~50 to ~100 documented registers, V2 grows from ~7 blocks to 214 documented constants), and corrected protocol behavior details.

The source code implements BLE GATT-based Modbus communication with Bluetti power stations. It supports 10 device models across two protocol generations (V1: protocolVer < 2000, V2: >= 2000). The core architecture is: `BluetoothClient` handles BLE connections and Modbus framing, `DeviceStruct` parses register blocks into typed fields, per-device classes define field layouts and writable controls, and `probe.py` discovers device capabilities.

## Goals / Non-Goals

**Goals:**
- Fix bugs where source code makes incorrect assumptions contradicted by 3.0.9 docs
- Add missing control registers that matter for currently-supported BLE devices
- Implement TLV protocol parsing for multi-sub-device topology
- Add battery pack register support for cell-level monitoring
- Add device definitions for 5 new v3.0.9 models
- Update stale version references in comments

**Non-Goals:**
- OTA/firmware upgrade functionality
- Backend cloud API client
- Grid certification register support (40+ registers for regulatory compliance)
- Wi-Fi-only or cloud-only device categories (COMBOX, SMART_PLUG, etc.)
- Full 120-model catalog — only the 5 new v3.0.9 models + models with clear BLE paths
- Registers for peripheral categories without BLE access (ATS, AT1, EPAD, EV chargers, DCDC converters accessed through internal bus)

## Decisions

### Decision 1: V1 protocol version detection — hardcode protocol_version on subclasses

**Chosen**: Override `protocol_version` on each V1 device subclass with the correct value from `DeviceConnUtil.getDeviceFunc()` in the APK (EB3A=1019, AC200L=1022, AC200M=1016, AC200PL=1022, AC300=0, AC500=0, EP500=1016).

**Rationale**: The current registry shortcut path in `_detect_protocol` reads `device.protocol_version` which is always 0 for V1 devices (inherited from `BluettiDevice`). This selects minimum block sizes (53/10/36 registers), silently truncating data for newer V1 devices that negotiate higher protocol versions. The alternatives:

- **Always run the dynamic probe (read register 16)**: Fixes truncation but adds an extra BLE round-trip during discovery and means the same device gets different block sizes in `probe` vs. `annotate` mode (which relies on the registry shortcut).
- **Hardcode correct versions**: Single source of truth, no extra round-trip, consistent behavior. But requires getting the values right — which the 3.0.9 APK provides.

For the EP500 and EP600, where we lack hardware verification, we use the APK's `minProtocolVer` as a safe lower bound. The probe's dynamic fallback path remains as a safety net if the registry lookup fails.

### Decision 2: Regex harmonization — use a single source pattern, relax scrub.py

**Chosen**: Define a single `_DEVICE_NAME_SN_RE` in `bluetooth/__init__.py` that covers all 10+ existing models, the 5 new models, and any alphanumeric-prefixed model. Import it in `scrub.py` instead of maintaining a separate regex. Relax scrub.py's `\d{6,}` to `\d+` (same as bluetooth.py) plus add alphanumeric suffix support (`[A-Z0-9]+`).

**Rationale**: Two regexes with different strictness is brittle. The scrub.py pattern (`\d{6,}`) is unnecessarily strict — some devices have shorter serial suffixes. A single authoritative regex avoids drift. For the alphanumeric suffix case (e.g., `HB500S`), we extend the pattern rather than add a separate regex, keeping one path.

### Decision 3: Register constant organization — keep them in device class files, add constants in device base classes

**Chosen**: Add register address constants to `v1_base.py` (for V1-wide constants) and `v2_base.py` (for V2-wide constants). Add device-specific control field definitions to individual device class files (`ac2a.py`, `ac60.py`). New V1 settable constants go in `v1_base.py` alongside existing ones. New V2 control constants go in `v2_base.py` for shared ones, or `ac2a.py` for AC2A-specific fields.

**Rationale**: Matches existing convention. `v1_base.py` already defines `SETTABLE_DATA=3000`, `WORKING_MODE=3001`, etc. as module-level constants. Adding new ones alongside them is natural. The alternative — a separate constants file — adds indirection without benefit since constants are only used in one or two call sites.

### Decision 4: TLV parsing — new module, dispatched from V2 base

**Chosen**: Create `src/voltkeeper/core/tlv.py` with `TlvParser` that interprets NODE_INFO responses starting with `0x40 0x00 0x04`. The parser produces `TlvItem` named tuples (slaveAddr, regAddr, data). Integrate into `v2_base.py`'s polling loop as an optional additional read command for devices that report multi-device topology.

**Rationale**: TLV is a response format, not a transport. It doesn't change the Modbus framing or BLE layer — it's a payload interpretation concern. A separate module keeps the parsing logic isolated and testable. The NODE_INFO read is optional because single-device systems (most portables) won't return TLV responses.

### Decision 5: Battery pack data — new block in V2 base, optional polling

**Chosen**: Add `PACK_MAIN_INFO=6000`, `PACK_ITEM_INFO=6100`, `PACK_BMU_INFO=7200` block constants to `v2_base.py` alongside existing blocks. Add struct definitions for these blocks. Make polling of battery pack registers optional — enabled by device class flag or config — since not all V2 devices have external battery packs.

**Rationale**: Battery packs are accessed through the main unit's Modbus bus via slave addressing, not as separate BLE peripherals. Integrating into `v2_base.py` reuses the existing polling infrastructure. The optional flag avoids unnecessary BLE traffic for devices with no battery packs.

### Decision 6: New device models — follow existing class hierarchy

**Chosen**: 
- AORA100_MINI, AORA30_MINI, AORA200_MINI: Create `AoraMiniBase` inheriting from `BluettiDevice` (protocol version TBD from APK). All three AORA mini models share the same category, so a shared base minimizes duplication.
- HB500S, BH500E: Create `BatteryPackBase` inheriting from `BluettiDevice`. These are battery pack devices, not power stations — their register layout and writable controls differ significantly.
- Register parsing uses existing `DeviceStruct` infrastructure — no new field types needed.

**Rationale**: Following the existing pattern (V1Base/V2Base → specific device) keeps the codebase consistent. The AORA mini models likely share register layouts, so a common base class avoids duplication. Battery packs are a new device category requiring their own base class since their register map doesn't match the inverter-centric V1Base/V2Base layout.

## Risks / Trade-offs

- **[V1 protocol_version values]**: The protocol_version values come from APK source analysis, not hardware testing. If a device negotiates a higher version at runtime than the APK's `minProtocolVer`, the hardcoded value could still cause truncation. **Mitigation**: The dynamic probe fallback path is preserved. If the registry shortcut returns wrong sizes, the probe will retry with the dynamic read. We should log a warning when the dynamic probe reports a version ≥ the hardcoded value.

- **[New device models — no hardware]**: AORA mini and battery pack device classes are defined from APK source only, without hardware testing. Register layouts and field types may be incorrect. **Mitigation**: Mark new device classes with `# TODO(hardware): verify against physical device` comments, matching existing convention for untested models.

- **[TLV response format assumption]**: The TLV format is documented from APK 3.0.9 source but we have no captured TLV responses from real multi-device systems. The parsing implementation may misinterpret the wire format. **Mitigation**: Implement TLV parsing defensively — validate magic bytes, length fields, and CRC — and fail gracefully with clear error messages rather than silently producing garbage.

- **[Regex relaxation may over-match]**: Relaxing scrub.py from `\d{6,}` to `\d+` could theoretically match non-device strings that happen to look like model+digits. **Mitigation**: The scrub pattern is only applied to BLE advertising names, which are already filtered by SERVICE_UUID. The risk of false matches on unrelated BLE peripherals is very low.
