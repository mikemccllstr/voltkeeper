# ABOUTME: Generic V1-protocol base device class — register blocks, structs, parse dispatch.
# ABOUTME: Unit 9 per IMPLEMENTATION_UNITS.md.
#
# V1 devices are always plaintext (no BLE encryption). Per FINDINGS §15.4 as of
# APK 3.0.8, isBLEEncrypted / isESP32Encrypted are false for all V1 models
# (protocolVer < 2000). Subclasses added in Unit 10 rely on this.

from typing import Any, List

from ..commands import ReadHoldingRegisters, WriteSingleRegister
from ..struct import BoolField, DeviceStruct, EnumField
from ..utils import _u16
from .bluetti_device import BluettiDevice

BASE_CONFIG = 1
BLUETOOTH_PASSWORD = 7
BASE_REAL_DATA = 10
MODBUS_PROTOCOL_VER = 16
# TODO(hardware): FINDINGS §15.5 lists DEVICE_SN at register 21, but §15.6 puts
# the SN at byte-offset 14-21 (registers 17-20). Hardware verification needed
# to resolve. The struct uses register 21 per §15.5 until proven otherwise.
DEVICE_SN = 21
MCU_STATUS = 22
ADDITIONAL_DATA = 70
BMS_PACK = 91
THREE_PHASE_DATA = 130
PV_CHARGE_DATA = 157
WIFI_SWITCH_STATUS = 190

SETTABLE_DATA = 3000
WORKING_MODE = 3001
INVERTER_FREQUENCY = 3003
AC_SWITCH = 3007
DC_SWITCH = 3008
PV_CONTROL = 3009
GRID_CHARGING_SWITCH = 3011
LED_CONTROL = 3034
UPS_MODE = 3035
SYSTEM_POWER_OFF = 3060
LCD_SCREEN_TIME = 3061
SET_SYSTEM_FACTORY_RESET = 3062
ECO_CONTROL = 3063
CHARGING_MODE = 3065
POWER_LIFTING_MODE = 3066
CTRL_AC_ECO_MODE = 3067
DC_ECO_POWER = 3069
AC_ECO_POWER = 3070
OUTPUT_VOLTAGE = 3079
SYS_SWITCH_RECOVERY = 3090


class V1Base(BluettiDevice):
    WRITABLE_FIELD_NAMES: list[str] = []

    def __init__(self, address: str, type: str, sn: str):
        self.real_data_struct = DeviceStruct()
        self._build_real_data_struct()

        self.control_struct = DeviceStruct()

        super().__init__(address, type, sn)

    # ── BASE_REAL_DATA (register 10) — per FINDINGS §15.6 ──────────────

    def _build_real_data_struct(self):
        s = self.real_data_struct
        s.add_swap_string_field("deviceModel", 10, 6)
        s.add_uint_field("protocolVer", 16)
        s.add_bcd_sn_field("deviceSN", 21, 4)
        s.add_uint_field("pvChargingPower", 36)
        s.add_uint_field("gridChargingPower", 37)
        s.add_uint_field("acLoadPower", 38)
        s.add_uint_field("dcLoadPower", 39)
        s.add_uint_field("feedBackPower", 40)
        s.add_decimal32_field("totalPVPower", 41, 1)
        s.add_uint_field("batterySOC", 43)
        s.add_uint_field("pvIconDisplay", 44)
        s.add_uint_field("gridIconDisplay", 45)
        s.add_uint_field("pv2BatteryEnergyLine", 46)
        s.add_uint_field("grid2BatteryEnergyLine", 47)
        s.add_uint_field("battery2ACEnergyLine", 48)
        s.add_uint_field("battery2DCEnergyLine", 49)
        s.add_uint_field("battery2GridEnergyLine", 50)
        s.add_uint_field("grid2LoadEnergyLine", 51)
        s.add_uint_field("pv2GridEnergyLine", 52)
        s.add_uint_field("batteryDischargingStatus", 53)
        s.add_uint_field("chgFullTime", 63)
        s.add_uint_field("dsgEmptyTime", 64)
        s.add_uint_field("sysIsHighVolt", 65)
        s.add_uint8_field("maxGridChgCurrentEnable", 66, 0)
        s.add_uint8_field("gridPlusModeEnable", 66, 1)
        s.add_uint_field("rateVoltage", 67)
        s.add_uint_field("rateFrequency", 68)

    # ── Parse dispatch ─────────────────────────────────────────────────

    def parse(self, address: int, data: bytes) -> dict:
        if BASE_REAL_DATA <= address < 100:
            result = self.real_data_struct.parse(address, data)
            self._fill_software_versions(result, data)
            return result
        elif SETTABLE_DATA <= address < 3100:
            return self.control_struct.parse(address, data)
        return {}

    # ── Custom array helpers ────────────────────────────────────────────

    @staticmethod
    def _fill_software_versions(result: dict, data: bytes):
        """Parse mcu1-4 + hmi1-2 software versions from BASE_REAL_DATA.

        Per FINDINGS §15.6: 6 version fields at register offsets 23-34,
        each 4 bytes in endian [2][3][0][1] format.
        """
        labels = ["mcu1ver", "mcu2ver", "mcu3ver", "mcu4ver", "hmi1ver", "hmi2ver"]
        for i, label in enumerate(labels):
            off = (23 - BASE_REAL_DATA + i * 2) * 2
            if len(data) < off + 4:
                break
            ver = (_u16(data, off + 2) << 16) | _u16(data, off)
            if ver > 0:
                result[label] = ver

    # ── Writable-field plumbing (mirrors V2Base) ───────────────────────

    def _all_polling_structs(self) -> tuple[DeviceStruct, ...]:
        return (self.real_data_struct, self.control_struct)

    def has_field(self, field: str) -> bool:
        return field in self.WRITABLE_FIELD_NAMES or any(
            f.name == field for fs in self._all_polling_structs() for f in fs.fields
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

    # ── Device properties ──────────────────────────────────────────────

    @property
    def polling_commands(self) -> List[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(BASE_REAL_DATA, 110),
        ]

    @property
    def logging_commands(self) -> List[ReadHoldingRegisters]:
        return self.polling_commands

    @property
    def writable_ranges(self) -> List[range]:
        return [range(SETTABLE_DATA, 3100)]
