# ABOUTME: Base class for Bluetti device definitions — struct, polling commands, protocol version.

from typing import Any, List

from ..commands import ReadHoldingRegisters, WriteSingleRegister


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
        raise NotImplementedError

    def build_setter_command(self, field: str, value: Any) -> WriteSingleRegister:
        raise NotImplementedError

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

    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool] | None:
        return None

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        return []
