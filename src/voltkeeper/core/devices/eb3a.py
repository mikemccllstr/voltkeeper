# ABOUTME: EB3A small portable — V1 protocol (minProtocolVer=1019 in Android).
# ABOUTME: TODO(EB3A): verify against hardware.

from typing import List

from ..commands import ReadHoldingRegisters
from .v1_base import (
    AC_SWITCH,
    DC_SWITCH,
    ECO_CONTROL,
    LED_CONTROL,
    SET_SYSTEM_FACTORY_RESET,
    SETTABLE_DATA,
    SYSTEM_POWER_OFF,
    V1Base,
)


class EB3A(V1Base):
    """EB3A small portable station. V1 protocol."""

    protocol_version = 1019

    # Uses V1Base default ALARM_NAMES/FAULT_NAMES (ConnectConstants).

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "led_control",
        "dc_eco_mode",
        "system_power_off",
        "factory_reset",
    ]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EB3A", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ac_output", AC_SWITCH)
        s.add_bool_field("dc_output", DC_SWITCH)
        s.add_bool_field("led_control", LED_CONTROL)
        s.add_bool_field("dc_eco_mode", ECO_CONTROL)
        s.add_bool_field("system_power_off", SYSTEM_POWER_OFF)
        s.add_bool_field("factory_reset", SET_SYSTEM_FACTORY_RESET)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [ReadHoldingRegisters(SETTABLE_DATA, 100)]
