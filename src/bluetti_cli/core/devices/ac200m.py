# ABOUTME: AC200M (AC200MAX) older mid-range — V1 protocol (minProtocolVer=1016 in Android).
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC200M as V2Base, but the Android
# ABOUTME:   DeviceConnUtil.java sets minProtocolVer=1016 (<2000), which is V1.
# ABOUTME: NOTE(name): internally "AC200M" in the DeviceModel enum, marketed as "AC200MAX".
# ABOUTME: TODO(AC200M): verify against hardware.

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
    UPS_MODE,
    V1Base,
)


class AC200M(V1Base):
    """AC200M (AC200MAX) older mid-range. V1 protocol."""

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "led_control",
        "ups_mode",
        "dc_eco_mode",
        "system_power_off",
        "factory_reset",
    ]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC200M", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ac_output", AC_SWITCH)
        s.add_bool_field("dc_output", DC_SWITCH)
        s.add_bool_field("led_control", LED_CONTROL)
        s.add_bool_field("ups_mode", UPS_MODE)
        s.add_bool_field("dc_eco_mode", ECO_CONTROL)
        s.add_bool_field("system_power_off", SYSTEM_POWER_OFF)
        s.add_bool_field("factory_reset", SET_SYSTEM_FACTORY_RESET)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [ReadHoldingRegisters(SETTABLE_DATA, 100)]
