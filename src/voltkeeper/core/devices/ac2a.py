# ABOUTME: AC2A device definition — V2 register map, inherits from V2Base with custom array helpers.

from enum import Enum, unique
from typing import List

from ..commands import EmsCtrlMode, InvFrequency, LedColor, Pv2Type, PvType, ReadHoldingRegisters, WorkingMode
from ..utils import _format_version, _s16, _u16
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_INFO,
    INV_BASE_SETTINGS,
    INV_GRID_INFO,
    INV_INV_INFO,
    INV_LOAD_INFO,
    INV_PV_INFO,
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


class AC2A(V2Base):
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
        s.add_uint_field("lcd_timeout", 2067)
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

    # ── Parse dispatch (adds array helpers on top of V2Base) ────────────

    def parse(self, address: int, data: bytes) -> dict:
        result = super().parse(address, data)
        if INV_BASE_INFO <= address < INV_PV_INFO:
            self._fill_software_versions(result, data)
        elif INV_PV_INFO <= address < INV_GRID_INFO:
            self._fill_pv_strings(result, data)
        elif INV_GRID_INFO <= address < INV_LOAD_INFO:
            self._fill_grid_phases(result, data)
        elif INV_LOAD_INFO <= address < INV_INV_INFO:
            self._fill_load_phases(result, data)
        elif INV_INV_INFO <= address < INV_BASE_SETTINGS:
            self._fill_inv_phases(result, data)
        return result

    # ── Custom array helpers ────────────────────────────────────────────

    @staticmethod
    def _fill_software_versions(result: dict, data: bytes):
        for i in range(6):
            off = 26 + i * 6
            if len(data) < off + 6:
                break
            mcu_type = data[off]
            version = (_u16(data, off + 2) << 16) | _u16(data, off + 4)
            if mcu_type > 0 and version > 0:
                result[f"software[{i}]"] = f"MCU={mcu_type}  ver={_format_version(version)}"

    @staticmethod
    def _fill_pv_strings(result: dict, data: bytes):
        pv_count = max(result.get("acPvNumber", 0) + result.get("dcPvNumber", 0), 0)
        pv_count = min(pv_count, 5)

        for i in range(pv_count):
            off = 20 + i * 16
            if len(data) < off + 10:
                break
            prefix = f"pv[{i}]"
            result[f"{prefix}.workingStatus"] = data[off + 1]
            result[f"{prefix}.type"] = data[off + 3]
            result[f"{prefix}.inputPower"] = _u16(data, off + 4)
            result[f"{prefix}.inputVoltage"] = _u16(data, off + 6) / 10.0
            result[f"{prefix}.inputCurrent"] = _u16(data, off + 8) / 10.0

    @staticmethod
    def _fill_grid_phases(result: dict, data: bytes):
        phases = min(result.get("sysPhaseNumber", 3), 3)
        for i in range(phases):
            off = 26 + i * 12
            if len(data) < off + 10:
                break
            prefix = f"gridPhase[{i}]"
            result[f"{prefix}.power"] = abs(_s16(data, off))
            result[f"{prefix}.voltage"] = _u16(data, off + 2) / 10.0
            result[f"{prefix}.current"] = abs(_s16(data, off + 4)) / 10.0

    @staticmethod
    def _fill_load_phases(result: dict, data: bytes):
        phases = min(result.get("sysPhaseNumber", 3), 3)
        for i in range(phases):
            off = 60 + i * 12
            if len(data) < off + 8:
                break
            prefix = f"acPhase[{i}]"
            result[f"{prefix}.power"] = _u16(data, off)
            result[f"{prefix}.voltage"] = _u16(data, off + 2) / 10.0
            result[f"{prefix}.current"] = _u16(data, off + 4) / 10.0

    @staticmethod
    def _fill_inv_phases(result: dict, data: bytes):
        phases = min(result.get("sysPhaseNumber", 3), 3)
        for i in range(phases):
            off = 18 + i * 12
            if len(data) < off + 8:
                break
            prefix = f"invPhase[{i}]"
            result[f"{prefix}.workStatus"] = data[off + 1]
            result[f"{prefix}.power"] = _u16(data, off + 2)
            result[f"{prefix}.voltage"] = _u16(data, off + 4) / 10.0
            result[f"{prefix}.current"] = _u16(data, off + 6) / 10.0

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
