# ABOUTME: Modbus RTU command classes — read/write holding registers with CRC16.

import struct

from .utils import crc16_modbus


class DeviceCommand:
    def __init__(self, function_code: int, data: bytes):
        self.function_code = function_code
        self.cmd = bytearray(len(data) + 4)
        self.cmd[0] = 1
        self.cmd[1] = function_code
        self.cmd[2:-2] = data
        crc_val = struct.unpack("<H", crc16_modbus(self.cmd[:-2]))[0]
        struct.pack_into("<H", self.cmd, -2, crc_val)

    def response_size(self) -> int:
        raise NotImplementedError

    def __iter__(self):
        return iter(self.cmd)

    def is_exception_response(self, response: bytes) -> bool:
        if len(response) < 2:
            return False
        return response[1] == self.function_code + 0x80

    def is_valid_response(self, response: bytes | bytearray) -> bool:
        if len(response) < 3:
            return False
        return response[-2:] == crc16_modbus(response[:-2])

    def parse_response(self, response: bytes) -> bytes:
        return response


class ReadHoldingRegisters(DeviceCommand):
    def __init__(self, starting_address: int, quantity: int):
        self.starting_address = starting_address
        self.quantity = quantity
        super().__init__(3, struct.pack("!HH", starting_address, quantity))

    def response_size(self):
        return 2 * self.quantity + 5

    def parse_response(self, response: bytes) -> bytes:
        return bytes(response[3:-2])

    def __repr__(self):
        return f"ReadHoldingRegisters(starting_address={self.starting_address}, quantity={self.quantity})"


class WriteSingleRegister(DeviceCommand):
    def __init__(self, address: int, value: int):
        self.address = address
        self.value = value
        super().__init__(6, struct.pack("!HH", address, value))

    def response_size(self):
        return 8

    def parse_response(self, response: bytes) -> bytes:
        return bytes(response[4:6])

    def __repr__(self):
        return f"WriteSingleRegister(address={self.address}, value={self.value:#04x})"


class WriteMultipleRegisters(DeviceCommand):
    def __init__(self, starting_address: int, data: bytes):
        if len(data) % 2 != 0:
            raise ValueError("data size must be multiple of 2")

        self.starting_address = starting_address
        self.data = data

        body = bytearray(len(data) + 5)
        half_len = len(data) >> 1
        struct.pack_into("!HHB", body, 0, starting_address, half_len, len(data))
        body[5:] = data
        super().__init__(16, bytes(body))

    def response_size(self):
        return 8

    def __repr__(self):
        return f"WriteMultipleRegisters(starting_address={self.starting_address}, data={self.data.hex()})"
