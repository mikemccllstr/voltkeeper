# ABOUTME: EP500 home power station — V1 protocol (minProtocolVer=1016 in Android).
# ABOUTME: TODO(EP500): verify writable fields and register layout against hardware.

from typing import List

from ..commands import ReadHoldingRegisters
from .v1_base import SETTABLE_DATA, UPS_MODE, V1Base


class EP500(V1Base):
    """EP500 home power station. V1 protocol."""

    protocol_version = 1016

    WRITABLE_FIELD_NAMES = ["ups_mode"]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP500", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ups_mode", UPS_MODE)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [ReadHoldingRegisters(SETTABLE_DATA, 36)]
