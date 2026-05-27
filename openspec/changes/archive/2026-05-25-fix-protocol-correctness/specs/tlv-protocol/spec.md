## MODIFIED Requirements

### Requirement: TLV bundles are built per slave address

`V2Base.tlv_polling_commands` SHALL return a list of `TlvReadHoldingRegisters` instances, one per modbus slave address that has register reads scheduled. The main inverter slave (`slave_addr=1`) SHALL receive a bundle containing `APP_HOME_DATA` plus, on slow ticks, the inverter info blocks (`INV_BASE_INFO`, `INV_PV_INFO`, `INV_GRID_INFO`, `INV_LOAD_INFO`, `INV_INV_INFO`), plus `NODE_INFO` when `has_sub_devices` is true. Each discovered pack slave SHALL receive its own bundle containing `PACK_MAIN_INFO` only, addressed to that slave.

When `_discovered_packs` is empty but `has_battery_packs` is true, a single `PACK_MAIN_INFO` SHALL be included in the main slave's bundle (current pre-discovery behavior, unchanged).

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
