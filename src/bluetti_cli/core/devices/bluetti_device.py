# ABOUTME: Base class for Bluetti device definitions — struct, polling commands, protocol version.

from typing import Any, List

from ..commands import ReadHoldingRegisters, WriteSingleRegister
from ..struct import BoolField, DeviceStruct, EnumField


class BluettiDevice:
    def __init__(self, address: str, type: str, sn: str):
        self.address = address
        self.type = type
        self.sn = sn
        self.protocol_version = 0

    def parse(self, address: int, data: bytes) -> dict:
        raise NotImplementedError

    def has_field(self, field: str) -> bool:
        raise NotImplementedError

    def has_field_setter(self, field: str) -> bool:
        matches = [f for f in self.struct.fields if f.name == field]
        return any(any(f.address in r for r in self.writable_ranges) for f in matches)

    def build_setter_command(self, field: str, value: Any) -> WriteSingleRegister:
        matches = [f for f in self.struct.fields if f.name == field]
        device_field = next(
            f for f in matches if any(f.address in r for r in self.writable_ranges)
        )

        if isinstance(device_field, EnumField):
            value = device_field.enum[value].value
        elif isinstance(device_field, BoolField):
            value = 1 if value else 0

        return WriteSingleRegister(device_field.address, int(value))

    @property
    def pack_num_max(self) -> int:
        return 1

    @property
    def polling_commands(self) -> List[ReadHoldingRegisters]:
        raise NotImplementedError

    @property
    def logging_commands(self) -> List[ReadHoldingRegisters]:
        raise NotImplementedError

    @property
    def writable_ranges(self) -> List[range]:
        return []
