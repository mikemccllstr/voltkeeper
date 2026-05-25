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

The system SHALL NOT poll battery pack registers by default. A device class flag (`has_battery_packs: bool`) SHALL control whether pack registers are included in the polling command list. For the AC2A, this flag SHALL be `False` by default (pack data accessed through external battery unit, not built-in).

#### Scenario: AC2A does not poll pack registers by default
- **WHEN** an AC2A device is polled
- **THEN** PACK_MAIN_INFO (6000) is NOT included in the polling command list

#### Scenario: AC2A with external battery polls pack registers
- **WHEN** an AC2A device is configured with `has_battery_packs = True`
- **THEN** PACK_MAIN_INFO (6000) IS included in the polling command list

### Requirement: Battery pack data published over MQTT

The `NORMAL_DEVICE_FIELDS` mapping in `mqtt_client.py` SHALL include battery pack fields (`packVoltage`, `packCurrent`, `packSoc`, `packTemperature`) for Home Assistant MQTT auto-discovery.

#### Scenario: Pack SOC published over MQTT
- **WHEN** PACK_MAIN_INFO is parsed and `packSoc` has a value
- **THEN** `packSoc` is published to MQTT as a sensor entity via Home Assistant discovery
