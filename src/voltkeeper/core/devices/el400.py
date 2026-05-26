# ABOUTME: EL400 (Elite 400) device definition — V2 protocol, APK v3.0.9 ELITE200_V2 family.
# ABOUTME: 56V portable power station, model #29. Adds remote power control and sleep mode.
# ABOUTME: TODO(hardware): verify against physical device.

from enum import Enum, unique
from typing import List

from ..commands import InvFrequency, LedColor, ReadHoldingRegisters, SystemPowerOff, WorkingMode
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    REMOTE_STARTUP_SOC,
    SLEEP_POWER_THRESHOLD,
    SYSTEM_TIME,
    SYSTEM_TIME_ZONE,
    V1_UPS_MODE,
    WORKING_MODE,
    V2Base,
)


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


class EL400(V2Base):
    """EL400 portable power station. V2 protocol, 56V system."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EL400", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_uint32_field("system_time", SYSTEM_TIME)
        s.add_uint_field("system_timezone", SYSTEM_TIME_ZONE)
        s.add_enum_field("working_mode", WORKING_MODE, WorkingMode)
        s.add_bool_field("ctrl_led", 2007)
        s.add_bool_field("ac_output", 2011)
        s.add_bool_field("dc_output", 2012)
        # TODO(hardware): system_power EnumField (replaces the old power_off/sleep_mode
        # BoolField pair which both read register 2013 and collided on non-zero values).
        # Verify against a real EL400 — semantic mapping comes from APK docs.
        s.add_enum_field("system_power", 2013, SystemPowerOff)
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
        s.add_uint_field("remote_startup_soc", REMOTE_STARTUP_SOC, range=(0, 100))
        s.add_uint_field("soc_holding_low", 2075, range=(0, 100))
        s.add_enum_field("led_color", 2078, LedColor)
        s.add_uint_field("sleep_power_threshold", SLEEP_POWER_THRESHOLD)
        s.add_uint_field("soc_holding_high", 2083, range=(0, 100))
        s.add_bool_field("factory_reset", 2206)
        s.add_bool_field("ctrl_grid", 2207)
        s.add_bool_field("ctrl_feed", 2208)
        # inv_voltage mapping depends on voltType (not currently discoverable):
        #   voltType=0 (low):  0=100V, 1=120V, 2=208V (EP6K only)
        #   voltType=1 (high): 0=220V, 1=230V, 2=240V
        s.add_uint_field("inv_voltage", 2209)
        s.add_enum_field("inv_freq", 2210, InvFrequency)
        s.add_decimal_field("chg_max_voltage", 2211, 1)
        s.add_decimal_field("chg_max_current", 2212, 1)
        s.add_uint_field("grid_max_power", 2213)
        s.add_decimal_field("grid_max_current", 2214, 1)
        s.add_uint_field("feed_max_power", 2215)
        s.add_decimal_field("feed_max_current", 2216, 1)
        # TODO(hardware): verify — V2 uses same V1 register per APK DeviceSettingsWorkingModeActivityV2
        s.add_bool_field("ups_mode", V1_UPS_MODE)

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "system_power",
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
        "remote_startup_soc",
        "soc_holding_low",
        "led_color",
        "sleep_power_threshold",
        "soc_holding_high",
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
        "ups_mode",
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
            ReadHoldingRegisters(V1_UPS_MODE, 1),
        ]
