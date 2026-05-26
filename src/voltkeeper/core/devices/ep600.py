# ABOUTME: EP600 home power station — V2 protocol, high-voltage pack (÷10 default).
# ABOUTME: TODO(EP600): verify against hardware.

from typing import List

from ..commands import ReadHoldingRegisters
from .v2_base import V1_UPS_MODE, V2Base


class EP600(V2Base):
    """EP600 home power station. V2 protocol, high-voltage pack."""

    V2_ALARM_PROFILE = "high_power"
    PACK_ALARM_PROFILE = "high_volt"

    WRITABLE_FIELD_NAMES = ["ups_mode"]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EP600", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        # TODO(hardware): verify — V2 uses same V1 register per APK DeviceSettingsWorkingModeActivityV2
        s.add_bool_field("ups_mode", V1_UPS_MODE)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [ReadHoldingRegisters(V1_UPS_MODE, 1)]
