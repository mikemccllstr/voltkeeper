## ADDED Requirements

### Requirement: IOT_BASE_INFO register block is parsed

The system SHALL parse Modbus register `IOT_BASE_INFO` (11000), reading 70 registers to cover the IoT model, serial number, firmware version, connection status, and networking information. Parsed fields SHALL use the APK v3.0.9 encoding conventions: swapped-byte-pair ASCII for the model string, backwards-hex for the serial number, register-half-swapped unsigned 32-bit for firmware versions, pair-swapped bytes for IP addresses, pair-swapped bytes for MAC addresses, and signed byte for RSSI.

#### Scenario: IoT module is present and responds
- **WHEN** reading 70 registers from `IOT_BASE_INFO` (11000)
- **THEN** the parsed result contains `iot_model` (string), `iot_sn` (string), `iot_software_ver` (int), `rf_ver` (int)
- **THEN** the parsed result contains `ble_status` (bool), `mqtt_status` (bool)
- **THEN** the parsed result contains `wifi_ip` (string), `wifi_mac` (string), `network_rssi` (int), `network_conn_mode` (int)

#### Scenario: IoT module is absent or not responding
- **WHEN** reading `IOT_BASE_INFO` raises a Modbus exception or timeout
- **THEN** the parsed result is an empty dict
- **THEN** no exception propagates to the caller

### Requirement: IoT info is included in control reads for supported devices

Devices with probed IoT hardware SHALL include `ReadHoldingRegisters(IOT_BASE_INFO, 70)` in their `control_commands`. This SHALL be the mechanism by which IoT data enters the poll/verify pipeline — the read happens once at connect time, not every poll cycle.

#### Scenario: EL100V2 control_commands includes IoT read
- **WHEN** inspecting `El100V2.control_commands`
- **THEN** one `ReadHoldingRegisters` targets address 11000 with quantity 70

### Requirement: IoT connection status is surfaced in the status display

When IoT data is available from a device, the status command SHALL display the IoT module's active connection mode, firmware version, and networking status alongside the inverter telemetry.

#### Scenario: BLE-only connection displayed
- **WHEN** the IoT status word shows `ble_status=1` and no other connections active
- **THEN** the status display shows "IoT: BLE connected" or equivalent

#### Scenario: WiFi connection displayed
- **WHEN** the IoT status word shows `wifi_sta=1` with a non-zero IP address
- **THEN** the status display shows the WiFi IP address and RSSI
