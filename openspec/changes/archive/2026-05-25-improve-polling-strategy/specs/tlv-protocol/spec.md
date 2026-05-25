## ADDED Requirements

### Requirement: TLV read request encoding

The system SHALL support building TLV-encoded Modbus read requests that bundle multiple register block reads into a single command. The request encoding SHALL match the APK's `ModbusTaskUtils.buildTLVReadTask()` format: `<slave_addr> <0x03> <0x40 0x00 0x04> <item_count> [<addr_hi> <addr_lo> <len_hi> <len_lo>]... <CRC>`.

#### Scenario: TLV read request for single register block
- **WHEN** a TLV read request is built with one register address and length
- **THEN** the command bytes begin with `<slave> 0x03 0x40 0x00 0x04 0x00 0x01` followed by the address/length pair and CRC

#### Scenario: TLV read request for multiple register blocks
- **WHEN** a TLV read request is built with three register address/length pairs
- **THEN** the command bytes contain `item_count=3` and all three pairs in order

### Requirement: TLV-bundled polling for V2 devices

For V2 devices with TLV support, the system SHALL send a single TLV-bundled read request per poll cycle instead of individual `ReadHoldingRegisters` commands. The response SHALL be parsed by the existing `TlvParser` and dispatched to device structs.

#### Scenario: TLV-bundled poll executed
- **WHEN** a V2 device with TLV support is polled
- **THEN** a single TLV read request is sent containing all register blocks for the current cycle
- **THEN** the TLV response is parsed and each item is dispatched to the appropriate struct

#### Scenario: TLV bundling skipped for non-TLV devices
- **WHEN** a V2 device does not support TLV (determined by protocol version or base config)
- **THEN** individual `ReadHoldingRegisters` commands are used as before

## MODIFIED Requirements

### Requirement: NODE_INFO polling triggered by topology detection

The system SHALL poll NODE_INFO (register 21000) at connect time for every V2 device, regardless of whether multi-device topology is suspected. The poll SHALL be a write-then-read pattern: write version=1 to register 21000, then read the TLV response. If NODE_INFO fails or returns empty, the system SHALL fall back to assuming a single-device configuration. During subsequent polling cycles, NODE_INFO SHALL be polled only when the discovered topology indicates sub-devices exist.

#### Scenario: NODE_INFO polled at connect time on all V2 devices
- **WHEN** a V2 device BLE connection is established
- **THEN** NODE_INFO (register 21000) is polled using the write-then-read pattern
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
