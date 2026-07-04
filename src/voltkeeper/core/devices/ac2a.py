# ABOUTME: AC2A device definition — V2 register map, inherits from V2Base with custom array helpers.

from typing import List

from ..commands import EmsCtrlMode, InvFrequency, LedColor, Pv2Type, PvType, ReadHoldingRegisters, WorkingMode
from .bluetti_device import SupportTier
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    SYSTEM_TIME,
    SYSTEM_TIME_ZONE,
    WORKING_MODE,
    ChargingMode,
    V2Base,
)


class AC2A(V2Base):
    SUPPORT_TIER = SupportTier.HARDWARE_VERIFIED
    # AC2A is an 8S LiFePO4 pack (~25.6 V nominal); raw register × 0.01 = volts.
    # All other documented V2 models use ÷10. If a future model also reads 10×
    # high, follow this override pattern.
    DEFAULT_PACK_VOLTAGE_SCALE = 2

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC2A", sn)
        self._build_control_struct()

    # ── Control struct (model-specific) ─────────────────────────────────

    def _build_control_struct(self):
        s = self.control_struct
        s.add_uint32_field("system_time", SYSTEM_TIME)
        s.add_uint_field(
            "system_timezone", SYSTEM_TIME_ZONE
        )  # APK does not parse this register in parseInvBaseSettings
        s.add_uint_field("ctrl_event", 2006)
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
        s.add_enum_field("pv_type_set", 2060, PvType)
        s.add_enum_field("pv2_type_set", 2061, Pv2Type)
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067, range=(0, 255))
        s.add_uint_field("soc_holding_low", 2075, range=(0, 100))
        s.add_enum_field("led_color", 2078, LedColor)
        s.add_uint_field("soc_holding_high", 2083, range=(0, 100))
        s.add_uint_field("pv_adv_set", 2084)
        s.add_bool_field("ja12_enable", 2086)
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
        s.add_enum_field("ems_ctrl_mode_set", 2241, EmsCtrlMode)

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
        "led_color",
        "soc_holding_low",
        "soc_holding_high",
        "factory_reset",
        "inv_voltage",
        "inv_freq",
        "working_mode",
        "system_time",
        "system_timezone",
        "ctrl_led",
        "pv_type_set",
        "pv2_type_set",
        "pv_adv_set",
        "ja12_enable",
        "ctrl_grid",
        "ctrl_feed",
        "chg_max_voltage",
        "chg_max_current",
        "grid_max_power",
        "grid_max_current",
        "feed_max_power",
        "feed_max_current",
        "ems_ctrl_mode_set",
    ]

    CTRL_EVENT_BITS = [
        ("power_control", "power"),
        ("ac_control", "ac"),
        ("dc_control", "dc"),
        ("inv_control", "inv"),
        ("grid_control", "grid"),
        ("pv_control", "pv"),
        ("feedback", "feedback"),
        ("meter", "meter"),
        ("led", "led"),
        ("eco", "eco"),
        ("super_power", "super_power"),
    ]

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        return self.CTRL_EVENT_BITS

    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool]:
        from .v2_base import decode_ctrl_event

        return decode_ctrl_event(ctrl_event)

    # ── Device properties ──────────────────────────────────────────────

    @property
    def writable_ranges(self) -> List[range]:
        return [range(2000, 2087), range(2200, 2242)]

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 24),
            ReadHoldingRegisters(INV_BASE_SETTINGS + 60, 27),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 18),
            ReadHoldingRegisters(2241, 1),
        ]
