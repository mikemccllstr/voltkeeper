# ABOUTME: BLE/Modbus exception types used across the bluetooth layer.


class ParseError(Exception):
    pass


class ModbusError(Exception):
    pass


class BadConnectionError(Exception):
    pass
