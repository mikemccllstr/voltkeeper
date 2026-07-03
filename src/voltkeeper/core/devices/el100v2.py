# ABOUTME: EL100V2 (Elite 100 V2) device definition — V2 protocol per APK v3.0.9 template chain
# ABOUTME:   ELITE200_V2 → AC200PL. 56V portable power station, model ID 31.
# ABOUTME: Verified against physical device (FW SW#3, 2026-05-30).

from enum import Enum, unique
from typing import List

from ..commands import InvFrequency, ReadHoldingRegisters, WorkingMode
from .bluetti_device import SupportTier
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_SETTINGS,
    IOT_BASE_INFO,
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
    CUSTOM = 4


class El100V2(V2Base):
    """EL100V2 portable power station. V2 protocol, 56V system."""

    SUPPORT_TIER = SupportTier.HARDWARE_TESTING

    def __init__(self, address: str, sn: str):
        super().__init__(address, "EL100V2", sn)
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
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067)
        s.add_uint_field("soc_holding_low", 2075, range=(0, 100))
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
        s.add_decimal_field("grid_max_current", 2214, 1, range=(1, 15))
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
        "alarm_sound",
        "lcd_timeout",
        "soc_holding_low",
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
    ]

    @property
    def ctrl_event_bits(self) -> list[tuple[str, str]]:
        from .v2_base import V2_CTRL_EVENT_BITS

        return V2_CTRL_EVENT_BITS

    def decode_ctrl_event(self, ctrl_event: int) -> dict[str, bool]:
        from .v2_base import decode_ctrl_event

        return decode_ctrl_event(ctrl_event)

    @property
    def writable_ranges(self) -> List[range]:
        return [range(2000, 2087), range(2200, 2218)]

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        """Base settings read count per APK v3.0.9 ProtocolParserV2.getReadRegLen.

        protocol_version=2000 maps to count 67 (protocolVer < 2008),
        covering registers 2000–2066.  The EL100V2 BLE gateway rejects
        reads with response payloads above ~140 bytes and reads starting at
        mid-block addresses like 2060.

        Includes IOT_BASE_INFO (11000) for IoT module data — hardware-probed
        on EL100V2 (FW SW#3) to respond successfully.
        """
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 67),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 18),
            ReadHoldingRegisters(IOT_BASE_INFO, 70),
        ]
