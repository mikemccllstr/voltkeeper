# ABOUTME: AC60 small portable — V2 protocol per Android code (minProtocolVer=2000).
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC60 as V1Base, but the Android
# ABOUTME:   DeviceConnUtil.java sets minProtocolVer=2000, which is V2.
# ABOUTME: TODO(AC60): verify against hardware.

from enum import Enum, unique
from typing import List

from ..commands import ReadHoldingRegisters
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    V2Base,
)


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


class AC60(V2Base):
    """AC60 compact portable station. V2 protocol."""

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "power_off",
        "dc_eco_mode",
        "charging_mode",
        "power_lifting",
        "battery_range_start",
        "battery_range_end",
        "alarm_sound",
        "lcd_timeout",
        "soc_low",
        "soc_high",
        "factory_reset",
        "inv_voltage",
        "inv_freq",
    ]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC60", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ac_output", 2011)
        s.add_bool_field("dc_output", 2012)
        s.add_bool_field("power_off", 2013)
        s.add_bool_field("dc_eco_mode", 2014)
        s.add_enum_field("charging_mode", 2020, ChargingMode)
        s.add_bool_field("power_lifting", 2021)
        s.add_uint_field("battery_range_start", 2022, range=(0, 100))
        s.add_uint_field("battery_range_end", 2023, range=(0, 100))
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067)
        s.add_uint_field("soc_low", 2075, range=(0, 100))
        s.add_uint_field("soc_high", 2083, range=(0, 100))
        s.add_bool_field("factory_reset", 2206)
        s.add_uint_field("inv_voltage", 2209)
        s.add_uint_field("inv_freq", 2210)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 24),
            ReadHoldingRegisters(INV_BASE_SETTINGS + 60, 27),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 12),
        ]
