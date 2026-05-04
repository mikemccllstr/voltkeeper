# ABOUTME: Base class for Bluetti device definitions — struct, polling commands, protocol version.

from typing import List

from ..commands import ReadHoldingRegisters
from ..struct import DeviceStruct


class BluettiDevice:
    struct: DeviceStruct

    def __init__(self, address: str, type: str, sn: str):
        self.address = address
        self.type = type
        self.sn = sn
        self.protocol_version = 0

    def parse(self, address: int, data: bytes) -> dict:
        return self.struct.parse(address, data)

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
