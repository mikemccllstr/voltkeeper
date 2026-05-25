# ABOUTME: EL10V2 (Elite 10 V2) device definition — V2 protocol, APK v3.0.9 PLP022→EL10V2 chain.
# ABOUTME: 25V portable power station, model #62. Inherits V2Base with AC180-family writable fields.
# ABOUTME: TODO(hardware): verify against physical device.

from enum import Enum, unique
from typing import Any, List

from ..commands import InvFrequency, LedColor, ReadHoldingRegisters, WorkingMode, WriteSingleRegister
from .v2_base import (
    CHILD_LOCK_LEVEL,
    CTRL_CHILD_LOCK,
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    SYSTEM_TIME,
    SYSTEM_TIME_ZONE,
    WORKING_MODE,
    V2Base,
)


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


class EL10V2(V2Base):
    """EL10V2 portable power station. V2 protocol, 25V system."""

    DEFAULT_PACK_VOLTAGE_SCALE = 2

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EL10V2", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_uint32_field("system_time", SYSTEM_TIME)
        s.add_uint_field("system_timezone", SYSTEM_TIME_ZONE)
        s.add_enum_field("working_mode", WORKING_MODE, WorkingMode)
        s.add_bool_field("ctrl_led", 2007)
        s.add_bool_field("ac_output", 2011)
        s.add_bool_field("dc_output", 2012)
        s.add_bool_field("power_off", 2013)
        s.add_bool_field("dc_eco_mode", 2014)
        s.add_uint_field("dc_eco_auto_off_time", 2015, unit="h")
        s.add_uint_field("dc_eco_power", 2016, unit="W")
        s.add_bool_field("ac_eco_mode", 2017)
        s.add_uint_field("ac_eco_auto_off_time", 2018, unit="h")
        s.add_uint_field("ac_eco_power", 2019, unit="W")
        s.add_enum_field("charging_mode", 2020, ChargingMode)
        s.add_bool_field("power_lifting", 2021)
        s.add_uint_field("sys_low_power", 2022, range=(0, 100))
        s.add_uint_field("sys_high_power", 2023, range=(0, 100))
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067)
        s.add_bool_field("child_lock", CTRL_CHILD_LOCK)
        s.add_uint_field("child_lock_level", CHILD_LOCK_LEVEL, range=(1, 2))
        s.add_uint_field("soc_holding_low", 2075, range=(0, 100))
        s.add_enum_field("led_color", 2078, LedColor)
        s.add_uint_field("soc_holding_high", 2083, range=(0, 100))
        s.add_bool_field("factory_reset", 2206)
        s.add_enum_field("inv_freq", 2210, InvFrequency)

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "power_off",
        "dc_eco_mode",
        "dc_eco_auto_off_time",
        "dc_eco_power",
        "ac_eco_mode",
        "ac_eco_auto_off_time",
        "ac_eco_power",
        "charging_mode",
        "power_lifting",
        "sys_low_power",
        "sys_high_power",
        "alarm_sound",
        "lcd_timeout",
        "child_lock",
        "child_lock_level",
        "soc_holding_low",
        "led_color",
        "soc_holding_high",
        "factory_reset",
        "inv_freq",
        "working_mode",
        "system_time",
        "system_timezone",
        "ctrl_led",
    ]

    def build_setter_command(self, field: str, value: Any) -> WriteSingleRegister:
        if field == "child_lock":
            if isinstance(value, str):
                value = value.lower() in ("on", "1", "true", "yes")
            return WriteSingleRegister(CTRL_CHILD_LOCK, 0x20 if value else 0x10)
        return super().build_setter_command(field, value)

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        from .v2_base import V2_CTRL_EVENT_BITS

        return V2_CTRL_EVENT_BITS

    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool]:
        from .v2_base import decode_ctrl_event

        return decode_ctrl_event(ctrl_event)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 24),
            ReadHoldingRegisters(INV_BASE_SETTINGS + 60, 27),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 12),
        ]
