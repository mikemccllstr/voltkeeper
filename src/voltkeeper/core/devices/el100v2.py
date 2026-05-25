# ABOUTME: EL100V2 (Elite 100 V2) device definition — V2 protocol per APK v3.0.9 template chain
# ABOUTME:   ELITE200_V2 → AC200PL → AC240. 56V portable power station, model ID 31.

from enum import Enum, unique
from typing import List

from ..commands import ReadHoldingRegisters
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    SYSTEM_TIME,
    SYSTEM_TIME_ZONE,
    V2Base,
)


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


class El100V2(V2Base):
    """EL100V2 portable power station. V2 protocol, 56V system."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EL100V2", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_uint32_field("system_time", SYSTEM_TIME)
        s.add_uint_field("system_timezone", SYSTEM_TIME_ZONE)
        s.add_uint_field("working_mode", 2005)
        s.add_bool_field("ctrl_led", 2007)
        s.add_bool_field("ac_output", 2011)
        s.add_bool_field("dc_output", 2012)
        s.add_bool_field("power_off", 2013)
        s.add_bool_field("dc_eco_mode", 2014)
        s.add_uint_field("dc_eco_auto_off_time", 2015)
        s.add_uint_field("dc_eco_power", 2016)
        s.add_bool_field("ac_eco_mode", 2017)
        s.add_uint_field("ac_eco_auto_off_time", 2018)
        s.add_uint_field("ac_eco_power", 2019)
        s.add_enum_field("charging_mode", 2020, ChargingMode)
        s.add_uint_field("battery_range_start", 2022, range=(0, 100))
        s.add_uint_field("battery_range_end", 2023, range=(0, 100))
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067)
        s.add_uint_field("soc_low", 2075, range=(0, 100))
        s.add_uint_field("led_color", 2078)
        s.add_uint_field("soc_high", 2083, range=(0, 100))
        s.add_bool_field("factory_reset", 2206)
        s.add_bool_field("ctrl_grid", 2207)
        s.add_bool_field("ctrl_feed", 2208)
        s.add_uint_field("inv_voltage", 2209)
        s.add_uint_field("inv_freq", 2210)
        s.add_decimal_field("chg_max_voltage", 2211, 1)
        s.add_decimal_field("chg_max_current", 2212, 1)
        s.add_uint_field("grid_max_power", 2213)
        s.add_decimal_field("grid_max_current", 2214, 1)
        s.add_uint_field("feed_max_power", 2215)
        s.add_decimal_field("feed_max_current", 2216, 1)

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
        "battery_range_start",
        "battery_range_end",
        "alarm_sound",
        "lcd_timeout",
        "soc_low",
        "led_color",
        "soc_high",
        "factory_reset",
        "ctrl_grid",
        "ctrl_feed",
        "inv_voltage",
        "inv_freq",
        "chg_max_voltage",
        "chg_max_current",
        "grid_max_power",
        "grid_max_current",
        "feed_max_power",
        "feed_max_current",
        "working_mode",
        "system_time",
        "system_timezone",
        "ctrl_led",
    ]

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
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 18),
        ]
