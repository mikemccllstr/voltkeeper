# ABOUTME: AC2A device definition — V2 register map with 6 per-block sub-structs + custom array helpers.

from enum import Enum, unique
from typing import Any, List

from ..commands import ReadHoldingRegisters, WriteSingleRegister
from ..struct import BoolField, DeviceStruct, EnumField
from ..utils import _format_version, _s16, _u16
from .bluetti_device import BluettiDevice


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


APP_HOME_DATA = 100
INV_BASE_INFO = 1100
INV_PV_INFO = 1200
INV_GRID_INFO = 1300
INV_LOAD_INFO = 1400
INV_INV_INFO = 1500
INV_BASE_SETTINGS = 2000
INV_ADVANCE_SETTINGS = 2200


class AC2A(BluettiDevice):
    def __init__(self, address: str, sn: str):
        self.protocol_version = 2000

        self.home_struct = DeviceStruct()
        self._build_home_struct()

        self.inv_base_struct = DeviceStruct()
        self._build_inv_base_struct()

        self.inv_pv_struct = DeviceStruct()
        self._build_inv_pv_struct()

        self.inv_grid_struct = DeviceStruct()
        self._build_inv_grid_struct()

        self.inv_load_struct = DeviceStruct()
        self._build_inv_load_struct()

        self.inv_inv_struct = DeviceStruct()
        self._build_inv_inv_struct()

        self.control_struct = DeviceStruct()
        self._build_control_struct()

        super().__init__(address, "AC2A", sn)

    # ── Field definitions per register block ────────────────────────────

    def _build_home_struct(self):
        s = self.home_struct
        # Scale 2 (÷100) — AC2A is newer than the APK we decompiled;
        # the generic V2 parser uses ÷10 for high-voltage packs (EP500/EP600),
        # but AC2A's 8S LiFePO4 architecture (~25.6 V nominal) requires ÷100.
        # Verify against a multimeter if readings look off.
        s.add_decimal_field("packTotalVoltage", 100, 2)
        s.add_decimal_field("packTotalCurrent", 101, 2)
        s.add_uint_field("packTotalSoc", 102)
        s.add_uint_field("packChargingStatus", 103)
        s.add_uint_field("packChgFullTime", 104)
        s.add_uint_field("packDsgEmptyTime", 105)
        s.add_uint_field("packAgingInfo", 106)
        s.add_uint8_field("packCnts", 107, 0)
        s.add_uint8_field("packNumShow", 107, 1)
        s.add_uint_field("packOnline", 108)
        s.add_swap_string_field("deviceModel", 110, 6)
        s.add_bcd_sn_field("deviceSN", 116, 4)
        s.add_uint8_field("invNumber", 120, 1)
        s.add_uint8_field("invPowerType", 122, 1)
        s.add_uint8_field("gridParallelSoC", 125, 1)
        s.add_uint32_field("totalDCPower", 140)
        s.add_signed32_field("totalACPower", 142)
        s.add_uint32_field("totalPVPower", 144)
        s.add_signed32_field("totalGridPower", 146)
        s.add_signed32_field("totalInvPower", 148)
        s.add_decimal32_field("totalDCEnergy", 150, 1)
        s.add_decimal32_field("totalACEnergy", 152, 1)
        s.add_decimal32_field("totalPVChargingEnergy", 154, 1)
        s.add_decimal32_field("totalGridChargingEnergy", 156, 1)
        s.add_decimal32_field("totalFeedbackEnergy", 158, 1)
        s.add_uint8_field("chargingMode", 160, 1)
        s.add_uint8_field("invWorkingStatus", 161, 1)
        s.add_decimal32_field("pvToAcEnergy", 162, 1)
        s.add_uint8_field("selfSufficiencyRate", 164, 1)
        s.add_uint32_field("pvToAcPower", 165)
        s.add_decimal32_field("packDsgEnergyTotal", 167, 1)
        s.add_uint_field("rateVoltage", 169)
        s.add_uint_field("rateFrequency", 170)

    HOME_DATA_REGS = 62
    STATUS_HOME_REGS = 6

    def _build_inv_base_struct(self):
        s = self.inv_base_struct
        s.add_uint8_field("invId", 1100, 1)
        s.add_swap_string_field("invType", 1101, 6)
        s.add_bcd_sn_field("invSN", 1107, 4)
        s.add_uint8_field("invPowerType", 1111, 1)
        s.add_uint8_field("softwareNumber", 1112, 1)
        s.add_temperature_field("ambientTemp", 1151, 0)
        s.add_temperature_field("invMaxTemp", 1152, 0)
        s.add_temperature_field("pvDcdcMaxTemp", 1153, 0)
        s.add_uint_field("inputRateCurrentL1", 1161)
        s.add_uint_field("inputRateCurrentL2", 1162)
        s.add_uint_field("inputRateCurrentL3", 1163)
        s.add_uint_field("outputRateCurrentL1", 1164)
        s.add_uint_field("outputRateCurrentL2", 1165)
        s.add_uint_field("outputRateCurrentL3", 1166)
        s.add_uint_field("gridInputRateCurrentL1", 1167)
        s.add_uint_field("gridInputRateCurrentL2", 1168)
        s.add_uint_field("gridInputRateCurrentL3", 1169)

    def _build_inv_pv_struct(self):
        s = self.inv_pv_struct
        s.add_uint32_field("totalChgPower", 1200)
        s.add_decimal32_field("totalChgEnergy", 1202, 1)
        s.add_uint8_field("acPvNumber", 1209, 0, range=(0, 16))
        s.add_uint8_field("dcPvNumber", 1209, 1, range=(0, 16))

    def _build_inv_grid_struct(self):
        s = self.inv_grid_struct
        s.add_decimal_field("frequency", 1300, 1)
        s.add_signed32_field("totalChgPower", 1301)
        s.add_decimal32_field("totalChgEnergy", 1303, 1)
        s.add_uint8_field("sysPhaseNumber", 1312, 1, range=(0, 4))

    def _build_inv_load_struct(self):
        s = self.inv_load_struct
        s.add_uint32_field("dcLoadTotalPower", 1400)
        s.add_decimal32_field("dcLoadTotalEnergy", 1402, 1)
        s.add_uint_field("dc5VPower", 1404)
        s.add_decimal_field("dc5VCurrent", 1405, 1)
        s.add_uint_field("dc12VPower", 1406)
        s.add_decimal_field("dc12VCurrent", 1407, 1)
        s.add_uint_field("dc24VPower", 1408)
        s.add_decimal_field("dc24VCurrent", 1409, 1)
        s.add_decimal_field("dcVoltTotal", 1412, 1)
        s.add_decimal_field("dcCurrentTotal", 1413, 1)
        s.add_uint32_field("acLoadTotalPower", 1420)
        s.add_decimal32_field("acLoadTotalEnergy", 1422, 1)
        s.add_uint8_field("sysPhaseNumber", 1429, 1, range=(0, 4))

    def _build_inv_inv_struct(self):
        s = self.inv_inv_struct
        s.add_decimal_field("frequency", 1500, 1)
        s.add_decimal32_field("totalEnergy", 1501, 1)
        s.add_uint8_field("sysPhaseNumber", 1508, 1, range=(0, 4))

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
        "ac_output", "dc_output", "power_off", "dc_eco_mode", "ac_eco_mode",
        "charging_mode", "power_lifting", "battery_range_start", "battery_range_end",
        "alarm_sound", "lcd_timeout", "led_color", "soc_low", "soc_high",
        "factory_reset", "inv_voltage", "inv_freq", "working_mode",
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

    @classmethod
    def decode_ctrl_event(cls, ctrl_event: int) -> dict:
        return {
            name: bool(ctrl_event & (1 << i))
            for i, (name, _) in enumerate(cls.CTRL_EVENT_BITS)
        }

    # ── Parse dispatch ─────────────────────────────────────────────────

    def parse(self, address: int, data: bytes) -> dict:
        if APP_HOME_DATA <= address < INV_BASE_INFO:
            return self.home_struct.parse(address, data)
        elif INV_BASE_INFO <= address < INV_PV_INFO:
            result = self.inv_base_struct.parse(address, data)
            self._fill_software_versions(result, data)
            return result
        elif INV_PV_INFO <= address < INV_GRID_INFO:
            result = self.inv_pv_struct.parse(address, data)
            self._fill_pv_strings(result, data)
            return result
        elif INV_GRID_INFO <= address < INV_LOAD_INFO:
            result = self.inv_grid_struct.parse(address, data)
            self._fill_grid_phases(result, data)
            return result
        elif INV_LOAD_INFO <= address < INV_INV_INFO:
            result = self.inv_load_struct.parse(address, data)
            self._fill_load_phases(result, data)
            return result
        elif INV_INV_INFO <= address < INV_BASE_SETTINGS:
            result = self.inv_inv_struct.parse(address, data)
            self._fill_inv_phases(result, data)
            return result
        elif INV_BASE_SETTINGS <= address < INV_ADVANCE_SETTINGS:
            return self.control_struct.parse(address, data)
        elif INV_ADVANCE_SETTINGS <= address < 2300:
            return self.control_struct.parse(address, data)
        return {}

    # ── Custom array helpers (structured data beyond simple fields) ────

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
    def polling_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(APP_HOME_DATA, self.HOME_DATA_REGS),
            ReadHoldingRegisters(INV_BASE_INFO, 51),
            ReadHoldingRegisters(INV_PV_INFO, 70),
            ReadHoldingRegisters(INV_GRID_INFO, 31),
            ReadHoldingRegisters(INV_LOAD_INFO, 48),
            ReadHoldingRegisters(INV_INV_INFO, 30),
        ]

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(INV_BASE_SETTINGS, 24),
            ReadHoldingRegisters(INV_BASE_SETTINGS + 60, 27),
            ReadHoldingRegisters(INV_ADVANCE_SETTINGS, 12),
        ]

    @property
    def logging_commands(self) -> List[ReadHoldingRegisters]:
        return self.polling_commands

    @property
    def writable_ranges(self) -> List[range]:
        return [
            range(INV_BASE_SETTINGS, 2087),
            range(INV_ADVANCE_SETTINGS, 2272),
        ]

    def has_field(self, field: str) -> bool:
        return field in self.WRITABLE_FIELD_NAMES or any(
            f.name == field for fs in (
                self.home_struct, self.inv_base_struct, self.inv_pv_struct,
                self.inv_grid_struct, self.inv_load_struct, self.inv_inv_struct,
            ) for f in fs.fields
        )

    def has_field_setter(self, field: str) -> bool:
        return field in self.WRITABLE_FIELD_NAMES

    def build_setter_command(self, field: str, value: Any) -> WriteSingleRegister:
        matches = [f for f in self.control_struct.fields if f.name == field]
        if not matches:
            raise ValueError(f"Unknown writable field: {field}")
        device_field = matches[0]

        if isinstance(device_field, EnumField):
            if isinstance(value, str):
                value = device_field.enum[value.upper()].value
            else:
                value = device_field.enum(value).value
        elif isinstance(device_field, BoolField):
            if isinstance(value, str):
                value = 1 if value.lower() in ("on", "1", "true", "yes") else 0
            else:
                value = 1 if value else 0

        return WriteSingleRegister(device_field.address, int(value))
