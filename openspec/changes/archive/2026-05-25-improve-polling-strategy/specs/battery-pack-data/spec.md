## MODIFIED Requirements

### Requirement: Battery pack polling is optional

The system SHALL poll battery pack registers (PACK_MAIN_INFO, PACK_ITEM_INFO) only when NODE_INFO discovery at connect time reports battery pack sub-devices are present. The `has_battery_packs` class attribute SHALL serve as an override for devices where NODE_INFO cannot be relied upon. For the AC2A, pack registers SHALL only be polled when NODE_INFO returns pack data.

#### Scenario: AC2A does not poll pack registers when no packs discovered
- **WHEN** an AC2A device connects and NODE_INFO returns no battery pack sub-devices
- **THEN** PACK_MAIN_INFO (6000) is NOT included in the polling command list

#### Scenario: AC2A with external battery polls pack registers
- **WHEN** an AC2A device connects and NODE_INFO returns one or more battery pack sub-devices
- **THEN** PACK_MAIN_INFO (6000) and PACK_ITEM_INFO (6100) ARE included for each discovered pack

#### Scenario: V2 device with has_battery_packs=True forces pack polling
- **WHEN** a V2 device class has `has_battery_packs = True` and NODE_INFO discovery fails
- **THEN** PACK_MAIN_INFO (6000) IS included in the polling command list as a fallback
