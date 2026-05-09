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
GRID_PLUS_MODE = 3002
INVERTER_FREQUENCY = 3003
FEED_SWITCH = 3010
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

# ── V1 alarm/fault name tables (shared by all V1 devices) ──────────────
# Per FINDINGS §15.6: alarmInfo at registers 54-57 (4×16-bit),
# faultInfo at registers 58-62 (5×16-bit per ProtocolParse.java).
# Bit 0 = LSB, index 0 = bit 0.

LOW_POWER_WARN_NAMES: dict[int, list[str]] = {
    1: [
        "Grid Voltage High",
        "Grid Voltage Low",
        "Grid Frequency High",
        "Grid Frequency Low",
        "Grid Oscillation",
        "Networking Operation Abnormal",
        "Grid Connection Fault",
        "Accessory Malfunction",
        "PV Configuration Error",
        "Grid 2 Voltage High",
        "Grid 2 Voltage Low",
        "Grid 2 Frequency High",
        "Grid 2 Frequency Low",
        "Grid 2 Oscillation",
        "Grid Not Connected",
    ],
    2: [
        "Battery Pack Communication Abnormal",
        "IoT Communication Error",
        "UPS Input Overvoltage",
        "UPS Input Undervoltage",
        "UPS Input Overcurrent",
        "UPS Input Overtemperature",
        "UPS Precharge Fault",
        "UPS Hardware Fault",
    ],
}

LOW_POWER_FAULT_NAMES: dict[int, list[str]] = {
    1: [
        "Inverter Overload",
        "Inverter Over Temperature",
        "Inverter Short Circuit",
        "Inverter Output Fault",
        "LLC Output Error",
        "Bus Over Voltage/Hardware Bus Over Voltage",
        "BUS Low Voltage",
        "Hardware Inverter Overcurrent",
        "Hardware Input Overcurrent",
        "Battery Voltage High/Hardware Battery Over Voltage",
        "Battery Voltage Low",
        "Main Relay Failure",
        "Grid Relay Failure",
        "Calibration Fail",
        "Auxiliary Battery Malfunction",
        "Fan Error",
    ],
    2: [
        "Multihost Error",
        "Phase Loss",
        "Multi-machine Communication Abnormal",
        "Multi-machine Synchronization Abnormal",
        "Multi-machine Configuration Abnormal",
        "Generator Voltage Abnormal",
        "System Initialization Failure",
        "Parallel Relay Failure",
        "Grid Input Overcurrent",
        "System Overload",
        "DC Output Overload",
        "Inverter Low Temperature",
    ],
    3: [
        "PV1 Over Voltage",
        "PV2 Over Voltage",
        "PV3 Over Voltage",
        "PV1 Overcurrent",
        "PV2 Overcurrent",
        "PV3 Overcurrent",
        "PV1 Over Temperature",
        "PV2 Over Temperature",
        "PV3 Over Temperature",
        "PV Precharge Fault",
        "PV1 Hardware Error",
        "PV2 Hardware Error",
        "PV3 Hardware Error",
        "PV Insulation Resistance Fault",
    ],
    4: [
        "PV4 Over Voltage",
        "PV4 Overcurrent",
        "PV4 Over Temperature",
        "PV4 Hardware Error",
        "PV1 Low Temperature",
        "PV2 Low Temperature",
        "PV3 Low Temperature",
        "PV4 Low Temperature",
    ],
    5: [
        "DC Output Short Circuit",
        "DC Output Voltage High",
        "DC Output Current High",
        "DC Output Over Temperature",
        "DC Output Failure",
        "BMS Communication Failure",
        "Inverter String Communication Failure",
        "RTC Error",
        "EEPROM Error",
        "BMS System Fault",
        "Controller Temperature Too High",
        "Zero Drift Abnormal (DSP)",
        "DC Output Low Temperature",
        "Leakage Current Fault",
        "Insulation Resistance Failure",
    ],
}


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
            self._fill_alarms(result, data)
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

    @staticmethod
    def _fill_alarms(result: dict, data: bytes):
        """Decode alarmInfo (regs 54-57) and faultInfo (regs 58-62).

        Walks each 16-bit word, bit 0 = LSB, and emits
        ``alarm.<name>: True`` / ``fault.<name>: True`` keys.

        Uses LOW_POWER_WARN_NAMES / LOW_POWER_FAULT_NAMES — all V1
        devices share the same tables regardless of power class.
        """
        base = BASE_REAL_DATA

        # alarmInfo: 4 words starting at register 54
        for word_idx in range(4):
            reg = 54 + word_idx
            off = (reg - base) * 2
            if len(data) < off + 2:
                break
            word_val = _u16(data, off)
            names = LOW_POWER_WARN_NAMES.get(word_idx + 1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names):
                    result[f"alarm.{names[bit]}"] = True

        # faultInfo: 5 words starting at register 58
        for word_idx in range(5):
            reg = 58 + word_idx
            off = (reg - base) * 2
            if len(data) < off + 2:
                break
            word_val = _u16(data, off)
            names = LOW_POWER_FAULT_NAMES.get(word_idx + 1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names):
                    result[f"fault.{names[bit]}"] = True

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
