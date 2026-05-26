## ADDED Requirements

### Requirement: TLV response format detection

The system SHALL detect TLV-encoded NODE_INFO responses by checking if the response data begins with the magic bytes `0x40 0x00 0x04`. If these bytes are present, the response SHALL be parsed as TLV items. If absent, the response SHALL be treated as a flat field layout (existing behavior).

#### Scenario: TLV magic bytes detected
- **WHEN** reading NODE_INFO (register 21000) and the response starts with bytes `40 00 04`
- **THEN** the TLV parser is invoked
- **THEN** each TLV item is extracted and dispatched

#### Scenario: Non-TLV response falls through
- **WHEN** reading NODE_INFO (register 21000) and the response does NOT start with `40 00 04`
- **THEN** the response is parsed as a flat register block using existing DeviceStruct mechanisms

### Requirement: TLV item parsing

Each TLV item SHALL be parsed into a `TlvItem` named tuple with fields: `slave_addr` (int), `reg_addr` (int), `length` (int), and `value` (bytes). The system SHALL iterate all TLV items in a response by reading each item's length and advancing the read position.

#### Scenario: Single TLV item parsed
- **WHEN** a TLV response contains one item with slaveAddr=41, regAddr=6000, len=32, value=<32 bytes>
- **THEN** a single `TlvItem(41, 6000, 32, <32 bytes>)` is returned

#### Scenario: Multiple TLV items parsed in sequence
- **WHEN** a TLV response contains three items
- **THEN** all three `TlvItem` instances are returned in order
- **THEN** the total bytes consumed matches the sum of all item lengths plus headers

#### Scenario: Malformed TLV response detected
- **WHEN** a TLV response has an item whose declared length exceeds remaining bytes
- **THEN** a `ParseError` is raised with a descriptive message including the expected vs. actual byte counts

### Requirement: NODE_INFO polling triggered by topology detection

The system SHALL poll NODE_INFO (register 21000) at connect time for every V2 device, regardless of whether multi-device topology is suspected. If NODE_INFO fails or returns empty, the system SHALL fall back to assuming a single-device configuration. During subsequent polling cycles, NODE_INFO SHALL be polled only when the discovered topology indicates sub-devices exist.

#### Scenario: NODE_INFO polled at connect time on all V2 devices
- **WHEN** a V2 device BLE connection is established
- **THEN** NODE_INFO (register 21000) is polled
- **THEN** the TLV response is parsed to discover sub-device topology

#### Scenario: NODE_INFO failure falls back to single-device
- **WHEN** the NODE_INFO poll at connect time fails or returns empty
- **THEN** the device is treated as having no sub-devices
- **THEN** PACK_MAIN_INFO and PACK_ITEM_INFO are not included in subsequent polls

#### Scenario: NODE_INFO re-polled only when sub-devices exist
- **WHEN** the initial NODE_INFO poll discovers sub-devices (packs, panels, inverters)
- **THEN** NODE_INFO is re-polled on each cycle to refresh sub-device data
- **WHEN** the initial NODE_INFO poll discovers no sub-devices
- **THEN** NODE_INFO is not re-polled in subsequent cycles

### Requirement: TLV dispatch to device parsers

Each parsed `TlvItem` SHALL be dispatched to the appropriate DeviceStruct parser based on `reg_addr`, using the same dispatch mechanism as direct Modbus reads. The `slave_addr` SHALL be passed alongside the register data for sub-device identification. This dispatch SHALL handle both NODE_INFO responses and TLV-bundled poll responses.

#### Scenario: PACK_MAIN_INFO dispatched from TLV item
- **WHEN** a TLV item has regAddr=6000 (PACK_MAIN_INFO) and slaveAddr=41
- **THEN** the PACK_MAIN_INFO struct parser is invoked with the item's value data
- **THEN** the resulting parsed data is tagged with slave_addr=41 (pack ID 0)

#### Scenario: Bundled poll TLV items dispatched to all structs
- **WHEN** a TLV-bundled poll response contains items for HOME (100), CONTROLS (2000), and INV_BASE_INFO (1100)
- **THEN** each item's value data is dispatched to the corresponding struct parser
- **THEN** all parsed results are merged into the response dict

### Requirement: TLV read request encoding

The system SHALL support building TLV-encoded Modbus read requests that bundle multiple register block reads into a single command. The request encoding SHALL match the APK's `ModbusTaskUtils.buildTLVReadTask()` format: `00105208 <total/2:2B> <total:1B> 9C450101 <00<slave> <addr:2B> <bytes:2B>>... <CRC>`.

#### Scenario: TLV read request for single register block
- **WHEN** a TLV read request is built with one register address and length
- **THEN** the command bytes begin with the TLV header and contain the section data

#### Scenario: TLV read request for multiple register blocks
- **WHEN** a TLV read request is built with three register address/length pairs
- **THEN** the command bytes contain all three pairs in order with correct CRC

### Requirement: TLV-bundled polling for V2 devices

For V2 devices with TLV support, the system SHALL send TLV-bundled read requests per poll cycle instead of individual `ReadHoldingRegisters` commands. The response of each bundle SHALL be parsed by the existing `TlvParser` and dispatched to device structs. See the "TLV bundles are built per slave address" requirement for how bundles are organized when multiple modbus slaves are involved (e.g., a stack with battery packs on slaves 41/42).

#### Scenario: TLV-bundled poll executed
- **WHEN** a V2 device with TLV support is polled
- **THEN** at least one TLV read request is sent containing the register blocks for the current cycle on the main slave
- **THEN** each TLV response is parsed and its items are dispatched to the appropriate struct

#### Scenario: TLV bundling skipped for non-TLV devices
- **WHEN** a V2 device does not support TLV (determined by protocol version or base config)
- **THEN** individual `ReadHoldingRegisters` commands are used as before

### Requirement: TLV bundles are built per slave address

`V2Base.tlv_polling_commands` SHALL return a list of `TlvReadHoldingRegisters` instances, one per modbus slave address that has register reads scheduled. The main inverter slave (`slave_addr=1`) SHALL receive a bundle containing `APP_HOME_DATA` plus, on slow ticks, the inverter info blocks (`INV_BASE_INFO`, `INV_PV_INFO`, `INV_GRID_INFO`, `INV_LOAD_INFO`, `INV_INV_INFO`), plus `NODE_INFO` when `has_sub_devices` is true. Each discovered pack slave SHALL receive its own bundle containing `PACK_MAIN_INFO` only, addressed to that slave.

When `_discovered_packs` is empty but `has_battery_packs` is true, a single `PACK_MAIN_INFO` SHALL be included in the main slave's bundle (pre-discovery behavior).

#### Scenario: AC2A produces a single-slave bundle
- **WHEN** an AC2A device with no discovered packs produces `tlv_polling_commands`
- **THEN** the returned list has length 1
- **THEN** the single bundle's `slave_addr` is `1`

#### Scenario: Stacked-pack device produces per-slave bundles
- **WHEN** an EP600 with `_discovered_packs = [41, 42]` produces `tlv_polling_commands`
- **THEN** the returned list has length 3
- **THEN** the slave addresses in order are `[1, 41, 42]`
- **THEN** bundle at index 1 contains only the `PACK_MAIN_INFO` section
- **THEN** bundle at index 2 contains only the `PACK_MAIN_INFO` section

#### Scenario: Pre-discovery fallback for battery-pack devices
- **WHEN** a device with `has_battery_packs=True` and `_discovered_packs=[]` produces `tlv_polling_commands`
- **THEN** the returned list has length 1
- **THEN** the bundle's sections include `(PACK_MAIN_INFO, 32)` on `slave_addr=1`

### Requirement: topology_discovered reflects actual NODE_INFO arrival

`V2Base.topology_discovered` SHALL return `True` only after `discover_topology()` has been called with a valid TLV-encoded NODE_INFO response. The property SHALL NOT short-circuit based on class-level `has_battery_packs` declarations.

#### Scenario: Battery-pack device before NODE_INFO
- **WHEN** a fresh EP600 instance is created with `has_battery_packs=True`
- **THEN** `topology_discovered` is `False`

#### Scenario: NODE_INFO arrives
- **WHEN** `discover_topology(<valid TLV bytes containing one PACK_MAIN_INFO item>)` is called
- **THEN** `_discovered_packs` contains the parsed pack slave address
- **THEN** `topology_discovered` is `True`

#### Scenario: NODE_INFO still polled before discovery
- **WHEN** `_tlv_sections()` is called on a device with `has_battery_packs=True` and `topology_discovered=False`
- **THEN** the returned sections include `(NODE_INFO, 32)`
