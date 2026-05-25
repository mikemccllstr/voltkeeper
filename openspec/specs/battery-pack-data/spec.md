## ADDED Requirements

### Requirement: Battery pack register constants defined

The system SHALL define module-level constants for battery pack register block addresses in `v2_base.py`: `PACK_MAIN_INFO = 6000`, `PACK_ITEM_INFO = 6100`, `PACK_BMU_INFO = 7200`.

#### Scenario: Pack register constants are importable
- **WHEN** importing `v2_base.py`
- **THEN** `PACK_MAIN_INFO`, `PACK_ITEM_INFO`, and `PACK_BMU_INFO` are available as integer constants with the documented addresses

### Requirement: PACK_MAIN_INFO struct parses pack telemetry

The system SHALL define a `DeviceStruct` for `PACK_MAIN_INFO` (register 6000) that parses the following fields from the register block response: pack voltage, pack current, pack SOC, pack temperature, pack charging status, cell count, cycle count, and pack serial number.

#### Scenario: Pack main info parses voltage
- **WHEN** a PACK_MAIN_INFO response is parsed
- **THEN** `packVoltage` is returned as a `DecimalField` (raw value × 0.01 V)
- **THEN** `packCurrent` is returned as a `SignedDecimalField` (raw value × 0.01 A)
- **THEN** `packSoc` is returned as a `UintField` (0–100%)

#### Scenario: Pack main info parses temperature
- **WHEN** a PACK_MAIN_INFO response is parsed
- **THEN** `packTemperature` is returned as a `TemperatureField` (raw − 40 °C)

#### Scenario: Pack main info parses serial number
- **WHEN** a PACK_MAIN_INFO response is parsed
- **THEN** `packSerialNumber` is returned as a `BcdSerialField`

### Requirement: PACK_ITEM_INFO struct parses cell-level data

The system SHALL define a `DeviceStruct` for `PACK_ITEM_INFO` (register 6100) that parses per-cell voltage values. The struct SHALL support a configurable number of cells (up to 16).

#### Scenario: Pack item info parses cell voltages
- **WHEN** a PACK_ITEM_INFO response is parsed for an 8-cell pack
- **THEN** `cellVoltage1` through `cellVoltage8` are returned as `UintField` values (raw mV)
- **THEN** cells beyond the configured count are not included

#### Scenario: Pack item info returns empty for zero cells
- **WHEN** a PACK_ITEM_INFO response is parsed but cell count is 0
- **THEN** an empty cell voltage dict is returned

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

### Requirement: Battery pack data published over MQTT

The `NORMAL_DEVICE_FIELDS` mapping in `mqtt_client.py` SHALL include battery pack fields (`packVoltage`, `packCurrent`, `packSoc`, `packTemperature`) for Home Assistant MQTT auto-discovery.

#### Scenario: Pack SOC published over MQTT
- **WHEN** PACK_MAIN_INFO is parsed and `packSoc` has a value
- **THEN** `packSoc` is published to MQTT as a sensor entity via Home Assistant discovery
