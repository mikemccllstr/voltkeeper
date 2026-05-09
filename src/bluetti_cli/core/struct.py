# ABOUTME: Declarative device register struct — field types and DeviceStruct parser.

import struct
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Tuple, Type


class DeviceField:
    def __init__(self, name: str, address: int, size: int, word_offset: Optional[int] = None):
        self.name = name
        self.address = address
        self.size = size
        self.word_offset = word_offset

    def parse(self, data: bytes) -> Any:
        raise NotImplementedError

    def in_range(self, val: Any) -> bool:
        return True


class UintField(DeviceField):
    def __init__(self, name: str, address: int, range: Optional[Tuple[int, int]] = None):
        self.range = range
        super().__init__(name, address, 1)

    def parse(self, data: bytes) -> int:
        return struct.unpack("!H", data)[0]

    def in_range(self, val: int) -> bool:
        if self.range is None:
            return True
        return self.range[0] <= val <= self.range[1]


class BoolField(DeviceField):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 1)

    def parse(self, data: bytes) -> bool:
        return struct.unpack("!H", data)[0] == 1


class EnumField(DeviceField):
    def __init__(self, name: str, address: int, enum: Type[Enum]):
        self.enum = enum
        super().__init__(name, address, 1)

    def parse(self, data: bytes) -> Any:
        val = struct.unpack("!H", data)[0]
        return self.enum(val)


class DecimalField(DeviceField):
    def __init__(self, name: str, address: int, scale: int, range: Optional[Tuple[int, int]] = None):
        self.scale = scale
        self.range = range
        super().__init__(name, address, 1)

    def parse(self, data: bytes) -> Decimal:
        val = Decimal(struct.unpack("!H", data)[0])
        return val / 10**self.scale

    def in_range(self, val: Decimal) -> bool:
        if self.range is None:
            return True
        return self.range[0] <= val <= self.range[1]


class SignedDecimalField(DeviceField):
    def __init__(self, name: str, address: int, scale: int, range: Optional[Tuple[float, float]] = None):
        self.scale = scale
        self.range = range
        super().__init__(name, address, 2)

    def parse(self, data: bytes) -> Decimal:
        lo = struct.unpack("!H", data[0:2])[0]
        hi = struct.unpack("!H", data[2:4])[0]
        val = (hi << 16) | lo
        if val >= 0x80000000:
            val -= 0x100000000
        return Decimal(val) / 10**self.scale

    def in_range(self, val: Decimal) -> bool:
        if self.range is None:
            return True
        return self.range[0] <= val <= self.range[1]


class Uint8Field(DeviceField):
    def __init__(self, name: str, address: int, word_offset: int, range: Optional[Tuple[int, int]] = None):
        self.range = range
        super().__init__(name, address, 1, word_offset=word_offset)

    def parse(self, data: bytes) -> int:
        return data[0]

    def in_range(self, val: int) -> bool:
        if self.range is None:
            return True
        return self.range[0] <= val <= self.range[1]


class StringField(DeviceField):
    def __init__(self, name: str, address: int, size: int):
        super().__init__(name, address, size)

    def parse(self, data: bytes) -> str:
        return data.rstrip(b"\x00").decode("ascii")


class SwapStringField(DeviceField):
    def __init__(self, name: str, address: int, size: int):
        super().__init__(name, address, size)

    def parse(self, data: bytes) -> str:
        arr = bytearray(data)
        for i in range(0, len(arr) - 1, 2):
            arr[i], arr[i + 1] = arr[i + 1], arr[i]
        return bytes(arr).rstrip(b"\x00").decode("ascii", errors="replace").strip()


class VersionField(DeviceField):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 2)

    def parse(self, data: bytes) -> Decimal:
        values = struct.unpack("!2H", data)
        return Decimal(values[0] + (values[1] << 16)) / 100


class SerialNumberField(DeviceField):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 4)

    def parse(self, data: bytes) -> int:
        values = struct.unpack("!4H", data)
        return values[0] + (values[1] << 16) + (values[2] << 32) + (values[3] << 48)


class Uint32Field(DeviceField):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 2)

    def parse(self, data: bytes) -> int:
        lo = struct.unpack("!H", data[0:2])[0]
        hi = struct.unpack("!H", data[2:4])[0]
        return (hi << 16) | lo


class Signed32Field(DeviceField):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 2)

    def parse(self, data: bytes) -> int:
        lo = struct.unpack("!H", data[0:2])[0]
        hi = struct.unpack("!H", data[2:4])[0]
        val = (hi << 16) | lo
        if val >= 0x80000000:
            val -= 0x100000000
        return val


class Decimal32Field(DeviceField):
    def __init__(self, name: str, address: int, scale: int = 1, range: Optional[Tuple[float, float]] = None):
        self.scale = scale
        self.range = range
        super().__init__(name, address, 2)

    def parse(self, data: bytes) -> Decimal:
        lo = struct.unpack("!H", data[0:2])[0]
        hi = struct.unpack("!H", data[2:4])[0]
        val = (hi << 16) | lo
        return Decimal(val) / 10**self.scale

    def in_range(self, val: Decimal) -> bool:
        if self.range is None:
            return True
        return self.range[0] <= val <= self.range[1]


class TemperatureField(DeviceField):
    def __init__(self, name: str, address: int, word_offset: int = 0):
        super().__init__(name, address, 1, word_offset=word_offset)

    def parse(self, data: bytes) -> Optional[int]:
        val = data[0]
        return val - 40 if val else None


class BcdSerialField(DeviceField):
    def __init__(self, name: str, address: int, size: int):
        super().__init__(name, address, size)

    def parse(self, data: bytes) -> str:
        chars = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                chars.append(f"{data[i + 1]:02X}{data[i]:02X}")
        return "".join(chars).lstrip("0")


class DeviceStruct:
    def __init__(self):
        self.fields: list[DeviceField] = []

    def add_uint_field(self, name: str, address: int, range: Optional[Tuple[int, int]] = None):
        self.fields.append(UintField(name, address, range))

    def add_bool_field(self, name: str, address: int):
        self.fields.append(BoolField(name, address))

    def add_enum_field(self, name: str, address: int, enum: Type[Enum]):
        self.fields.append(EnumField(name, address, enum))

    def add_decimal_field(self, name: str, address: int, scale: int, range: Optional[Tuple[int, int]] = None):
        self.fields.append(DecimalField(name, address, scale, range))

    def add_signed_decimal_field(
        self, name: str, address: int, scale: int, range: Optional[Tuple[float, float]] = None
    ):
        self.fields.append(SignedDecimalField(name, address, scale, range))

    def add_uint8_field(self, name: str, address: int, word_offset: int, range: Optional[Tuple[int, int]] = None):
        self.fields.append(Uint8Field(name, address, word_offset, range))

    def add_string_field(self, name: str, address: int, size: int):
        self.fields.append(StringField(name, address, size))

    def add_swap_string_field(self, name: str, address: int, size: int):
        self.fields.append(SwapStringField(name, address, size))

    def add_version_field(self, name: str, address: int):
        self.fields.append(VersionField(name, address))

    def add_sn_field(self, name: str, address: int):
        self.fields.append(SerialNumberField(name, address))

    def add_uint32_field(self, name: str, address: int):
        self.fields.append(Uint32Field(name, address))

    def add_signed32_field(self, name: str, address: int):
        self.fields.append(Signed32Field(name, address))

    def add_decimal32_field(self, name: str, address: int, scale: int = 1, range: Optional[Tuple[float, float]] = None):
        self.fields.append(Decimal32Field(name, address, scale, range))

    def add_temperature_field(self, name: str, address: int, word_offset: int = 0):
        self.fields.append(TemperatureField(name, address, word_offset))

    def add_bcd_sn_field(self, name: str, address: int, size: int):
        self.fields.append(BcdSerialField(name, address, size))

    def parse(self, starting_address: int, data: bytes) -> dict:
        data_size = len(data) // 2
        r = range(starting_address, starting_address + data_size)
        fields = [f for f in self.fields if f.address in r and f.address + f.size - 1 in r]

        parsed = {}
        for f in fields:
            data_start = 2 * (f.address - starting_address)
            if f.word_offset is not None:
                field_data = bytes([data[data_start + f.word_offset]])
            else:
                field_data = data[data_start : data_start + 2 * f.size]
            val = f.parse(field_data)
            if not f.in_range(val):
                continue
            parsed[f.name] = val

        return parsed
