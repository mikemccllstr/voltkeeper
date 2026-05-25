# ABOUTME: AORA Mini base class — shared register layout for AORA100_MINI, AORA30_MINI, AORA200_MINI.
# ABOUTME: TODO(hardware): verify protocol version, register layout, and writable controls against physical device.

from ..commands import ReadHoldingRegisters
from .bluetti_device import BluettiDevice


class AoraMiniBase(BluettiDevice):
    """Base class for AORA Mini series devices. Protocol details from APK v3.0.9 analysis.

    TODO(hardware): verify protocol version and register layout against physical device.
    """

    def __init__(self, address: str, type: str, sn: str):
        super().__init__(address, type, sn)

    def parse(self, address: int, data: bytes) -> dict:
        return {}

    @property
    def polling_commands(self) -> list[ReadHoldingRegisters]:
        return []

    @property
    def logging_commands(self) -> list[ReadHoldingRegisters]:
        return self.polling_commands


class Aora100Mini(AoraMiniBase):
    """AORA100_MINI — AORA mini series (model 66)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AORA100_MINI", sn)


class Aora30Mini(AoraMiniBase):
    """AORA30_MINI — AORA mini series (model 67)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AORA30_MINI", sn)


class Aora200Mini(AoraMiniBase):
    """AORA200_MINI — AORA mini series (model 68)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AORA200_MINI", sn)
