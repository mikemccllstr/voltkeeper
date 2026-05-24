# ABOUTME: AC2A device definition — V2 register map, inherits from V2Base with custom array helpers.
# ABOUTME: Unit 8 per IMPLEMENTATION_UNITS.md.

from enum import Enum, unique
from typing import List

from ..commands import ReadHoldingRegisters
from ..utils import _format_version, _s16, _u16
from .v2_base import (
    INV_ADVANCE_SETTINGS,
    INV_BASE_INFO,
    INV_BASE_SETTINGS,
    INV_GRID_INFO,
    INV_INV_INFO,
    INV_LOAD_INFO,
    INV_PV_INFO,
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
        s.add_uint_field("ctrl_event", 2006)
        s.add_uint_field("working_mode", 2005)
        s.add_bool_field("ac_output", 2011)
        s.add_bool_field("dc_output", 2012)
        s.add_bool_field("power_off", 2013)
        s.add_bool_field("dc_eco_mode", 2014)
        s.add_bool_field("ac_eco_mode", 2017)
        s.add_enum_field("charging_mode", 2020, ChargingMode)
        s.add_bool_field("power_lifting", 2021)
        s.add_uint_field("battery_range_start", 2022, range=(0, 100))
        s.add_uint_field("battery_range_end", 2023, range=(0, 100))
        s.add_bool_field("alarm_sound", 2066)
        s.add_uint_field("lcd_timeout", 2067)
        s.add_uint_field("soc_low", 2075, range=(0, 100))
        s.add_uint_field("led_color", 2078)
        s.add_uint_field("soc_high", 2083, range=(0, 100))
        s.add_bool_field("factory_reset", 2206)
        s.add_uint_field("inv_voltage", 2209)
        s.add_uint_field("inv_freq", 2210)

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "power_off",
        "dc_eco_mode",
        "ac_eco_mode",
        "charging_mode",
        "power_lifting",
        "battery_range_start",
        "battery_range_end",
        "alarm_sound",
        "lcd_timeout",
        "led_color",
        "soc_low",
        "soc_high",
        "factory_reset",
        "inv_voltage",
        "inv_freq",
        "working_mode",
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
        return {name: bool(ctrl_event & (1 << i)) for i, (name, _) in enumerate(self.CTRL_EVENT_BITS)}

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
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 24),
            ReadHoldingRegisters(INV_BASE_SETTINGS + 60, 27),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 12),
        ]
