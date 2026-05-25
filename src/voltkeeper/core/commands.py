# ABOUTME: Modbus RTU command classes — read/write holding registers with CRC16, TLV-bundled reads.

import struct
from enum import Enum, unique

from .utils import crc16_modbus


@unique
class WorkingMode(Enum):
    CUSTOMIZED_UPS = 1
    PV_PRIORITY_UPS = 2
    STANDARD_UPS = 3
    TIME_CTRL_UPS = 4
    V2_TIME_CTRL_UPS = 5
    SELF_CONSUMPTION_EXPORT = 11


@unique
class InvFrequency(Enum):
    HZ_50 = 0
    HZ_60 = 1


@unique
class PvType(Enum):
    PV = 0
    OTHER = 3


@unique
class Pv2Type(Enum):
    PV = 0
    OTHER = 3
    ALTERNATOR = 4


@unique
class LedColor(Enum):
    OFF = 0
    COOL = 1
    WARM = 2
    SOS = 3


@unique
class EmsCtrlMode(Enum):
    DISABLE = 0
    CLOUD = 3
    LOCAL = 4
    DYNAMIC_PRICE = 5
    AI = 8


# ── TLV read request encoding ────────────────────────────────────────

_TLV_REQ_HEADER = bytes.fromhex("00105208")
_TLV_REQ_INNER_MAGIC = bytes.fromhex("9C450101")


def build_tlv_read_payload(sections: list[tuple[int, int]], slave_addr: int = 1) -> bytearray:
    """Build the raw payload for a TLV-bundled read request.

    Format matches the APK v3.0.9 ``ModbusTaskUtils.buildTLVReadTask()``:
    ``00105208 <total/2:2B> <total:1B> 9C450101 [00<slave> <addr:2B> <bytes:2B>]... <CRC16>``

    Each section is a ``(register_address, register_count)`` pair.  The byte
    count in each section header is ``register_count * 2``.
    """
    sections_data = bytearray()
    for addr, count in sections:
        sections_data.append(0x00)
        sections_data.append(slave_addr & 0xFF)
        sections_data.extend(struct.pack("!HH", addr, count * 2))

    inner = _TLV_REQ_INNER_MAGIC + bytes(sections_data)
    total_len = len(inner)
    payload = bytearray(_TLV_REQ_HEADER)
    payload.extend(struct.pack("!HB", total_len // 2, total_len))
    payload.extend(inner)
    payload.extend(crc16_modbus(bytes(payload)))
    return payload


class DeviceCommand:
    def __init__(self, function_code: int, data: bytes, slave: int = 1):
        self.function_code = function_code
        self.cmd = bytearray(len(data) + 4)
        self.cmd[0] = slave
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
    def __init__(self, starting_address: int, quantity: int, slave: int = 1):
        self.starting_address = starting_address
        self.quantity = quantity
        super().__init__(3, struct.pack("!HH", starting_address, quantity), slave)

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


class TlvReadHoldingRegisters:
    """TLV-bundled register read request.

    Sends a single command to NODE_INFO (register 21000) that requests
    multiple register blocks at once.  The device responds with TLV-encoded
    data (magic ``40 00 04``) containing all the requested blocks.

    Each section is a ``(register_address, register_count)`` tuple.  The
    class builds the APK v3.0.9-compatible payload and handles TLV response
    validation.
    """

    def __init__(self, sections: list[tuple[int, int]], slave_addr: int = 1):
        self.sections = sections
        self.slave_addr = slave_addr
        self._payload = build_tlv_read_payload(sections, slave_addr)

    def response_size(self) -> int:
        return sum(count * 2 for _, count in self.sections) + 32

    def __bytes__(self) -> bytes:
        return bytes(self._payload)

    def __iter__(self):
        return iter(self._payload)

    def is_exception_response(self, response: bytes) -> bool:
        return len(response) < 3

    def is_valid_response(self, response: bytes | bytearray) -> bool:
        if len(response) < 5:
            return False
        return response[:3] == b"\x40\x00\x04" or response[-2:] == crc16_modbus(response[:-2])

    def parse_response(self, response: bytes) -> bytes:
        return response

    def __repr__(self):
        secs = ", ".join(f"({a},{c})" for a, c in self.sections)
        return f"TlvReadHoldingRegisters(sections=[{secs}])"
