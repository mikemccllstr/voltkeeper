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

The system SHALL optionally read NODE_INFO (register 21000) during V2 device polling if the device's base config or home data indicates a multi-device topology (multi-pack, parallel inverter). The read SHALL use Modbus slave address 1.

#### Scenario: NODE_INFO read on multi-pack device
- **WHEN** a V2 device with multiple battery packs is polled
- **THEN** NODE_INFO (register 21000) is read after the standard polling blocks
- **THEN** the TLV response is parsed to enumerate sub-device addresses

#### Scenario: NODE_INFO skipped on single-device system
- **WHEN** a V2 device with no sub-devices (single AC2A alone) is polled
- **THEN** NODE_INFO is not read (avoids unnecessary BLE traffic)

### Requirement: TLV dispatch to device parsers

Each parsed `TlvItem` SHALL be dispatched to the appropriate DeviceStruct parser based on `reg_addr`, using the same dispatch mechanism as direct Modbus reads. The `slave_addr` SHALL be passed alongside the register data for sub-device identification.

#### Scenario: PACK_MAIN_INFO dispatched from TLV item
- **WHEN** a TLV item has regAddr=6000 (PACK_MAIN_INFO) and slaveAddr=41
- **THEN** the PACK_MAIN_INFO struct parser is invoked with the item's value data
- **THEN** the resulting parsed data is tagged with slave_addr=41 (pack ID 0)
