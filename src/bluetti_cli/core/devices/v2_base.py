# ABOUTME: Generic V2-protocol base device class — register blocks, structs, parse dispatch.
# ABOUTME: Unit 8 per IMPLEMENTATION_UNITS.md.

from typing import List

from ..commands import ReadHoldingRegisters
from ..struct import DeviceStruct
from .bluetti_device import BluettiDevice

APP_HOME_DATA = 100
INV_BASE_INFO = 1100
INV_PV_INFO = 1200
INV_GRID_INFO = 1300
INV_LOAD_INFO = 1400
INV_INV_INFO = 1500
INV_BASE_SETTINGS = 2000
INV_ADVANCE_SETTINGS = 2200


class V2Base(BluettiDevice):
    DEFAULT_PACK_VOLTAGE_SCALE = 1

    def __init__(self, address: str, type: str, sn: str):
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

        super().__init__(address, type, sn)
        self.protocol_version = 2000

    # ── Field definitions per register block ────────────────────────────

    def _build_home_struct(self):
        s = self.home_struct
        s.add_decimal_field("packTotalVoltage", 100, self.DEFAULT_PACK_VOLTAGE_SCALE)
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
        s.add_uint_field("ctrl_event", 124)
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

    # ── Parse dispatch ─────────────────────────────────────────────────

    def parse(self, address: int, data: bytes) -> dict:
        if APP_HOME_DATA <= address < INV_BASE_INFO:
            return self.home_struct.parse(address, data)
        elif INV_BASE_INFO <= address < INV_PV_INFO:
            return self.inv_base_struct.parse(address, data)
        elif INV_PV_INFO <= address < INV_GRID_INFO:
            return self.inv_pv_struct.parse(address, data)
        elif INV_GRID_INFO <= address < INV_LOAD_INFO:
            return self.inv_grid_struct.parse(address, data)
        elif INV_LOAD_INFO <= address < INV_INV_INFO:
            return self.inv_load_struct.parse(address, data)
        elif INV_INV_INFO <= address < INV_BASE_SETTINGS:
            return self.inv_inv_struct.parse(address, data)
        return {}

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
    def logging_commands(self) -> List[ReadHoldingRegisters]:
        return self.polling_commands

    @property
    def writable_ranges(self) -> List[range]:
        return [range(2000, 2087), range(2200, 2272)]
