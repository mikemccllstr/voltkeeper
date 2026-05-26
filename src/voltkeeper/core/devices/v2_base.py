# ABOUTME: Generic V2-protocol base device class — register blocks, structs, parse dispatch.

from typing import Any, List

from ..commands import ReadHoldingRegisters, TlvReadHoldingRegisters, WriteSingleRegister
from ..struct import BoolField, DeviceStruct, EnumField
from ..tlv import TlvParser
from ..utils import _u16
from ._v2_alarm_tables import (
    HIGH_POWER_FAULT_NAMES,
    HIGH_POWER_WARN_NAMES,
    LOW_POWER_FAULT_NAMES,
    LOW_POWER_WARN_NAMES,
    MICRO_INV_FAULT_NAMES,
    MICRO_INV_WARN_NAMES,
    PACK_HIGH_VOLT_ALARM_NAMES,
    PACK_HIGH_VOLT_ERROR_NAMES,
)
from .bluetti_device import BluettiDevice

APP_HOME_DATA = 100
INV_BASE_INFO = 1100
INV_PV_INFO = 1200
INV_GRID_INFO = 1300
INV_LOAD_INFO = 1400
INV_INV_INFO = 1500
INV_BASE_SETTINGS = 2000
INV_ADVANCE_SETTINGS = 2200
SYSTEM_TIME = 2001
SYSTEM_TIME_ZONE = 2004
WORKING_MODE = 2005
CTRL_CHILD_LOCK = 2072
CHILD_LOCK_LEVEL = 2076
AUTO_SLEEP_DAYS = 2073
REMOTE_STARTUP_SOC = 2074
SLEEP_POWER_THRESHOLD = 2079
NODE_INFO = 21000
PACK_MAIN_INFO = 6000
PACK_ITEM_INFO = 6100
PACK_BMU_INFO = 7200

# ── ctrl_event capability bits ──────────────────────────────────────

V2_CTRL_EVENT_BITS: list[tuple[str, str]] = [
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


def decode_ctrl_event(ctrl_event: int) -> dict[str, bool]:
    """Decode a ctrl_event bitmask into named capability flags."""
    return {name: bool(ctrl_event & (1 << i)) for i, (name, _) in enumerate(V2_CTRL_EVENT_BITS)}


class V2Base(BluettiDevice):
    protocol_version: int = 2000

    # Alarm profile selects which warn/fault name tables _fill_v2_alarms uses.
    # Subclasses for 3-phase home-power devices override to "high_power";
    # micro-inverter devices override to "micro_inv". All portables keep the default.
    V2_ALARM_PROFILE: str = "low_power"

    # Pack alarm profile; None disables pack alarm decoding. Override to
    # "high_volt" on devices with high-voltage packs (e.g. EP600).
    PACK_ALARM_PROFILE: str | None = None

    _V2_INV_TABLES: dict[str, tuple[dict, dict]] = {
        "low_power": (LOW_POWER_WARN_NAMES, LOW_POWER_FAULT_NAMES),
        "high_power": (HIGH_POWER_WARN_NAMES, HIGH_POWER_FAULT_NAMES),
        "micro_inv": (MICRO_INV_WARN_NAMES, MICRO_INV_FAULT_NAMES),
    }

    _V2_PACK_TABLES: dict[str, tuple[dict, dict]] = {
        "high_volt": (PACK_HIGH_VOLT_ALARM_NAMES, PACK_HIGH_VOLT_ERROR_NAMES),
    }

    # Default pack-voltage scale for V2 devices. EP500/EP600 and other
    # high-voltage packs use ÷10 (raw register value × 0.1 = volts). The AC2A
    # is the known exception: its 8S LiFePO4 architecture (~25.6 V nominal)
    # requires ÷100 — see AC2A.DEFAULT_PACK_VOLTAGE_SCALE. When adding a new
    # V2 model, verify the pack voltage with a multimeter against the device
    # LCD; if readings look 10× off, override this attribute on the subclass.
    DEFAULT_PACK_VOLTAGE_SCALE = 1

    # Subclasses populate these. Empty defaults mean a model with no
    # writable controls works correctly — `has_field_setter` returns False
    # for everything and `build_setter_command` raises a clear error.
    WRITABLE_FIELD_NAMES: list[str] = []

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

        # Subclasses with writable controls call self._build_control_struct()
        # themselves AFTER super().__init__ — leave it empty here so models
        # without controls (read-only telemetry only) just work.
        self.control_struct = DeviceStruct()

        self.pack_main_struct = DeviceStruct()
        self._build_pack_main_struct()

        self.pack_item_struct = DeviceStruct()
        self._build_pack_item_struct()

        # ── Topology discovery (populated by discover_topology) ──────
        self._topology_discovered: bool = False
        self._discovered_packs: list[int] = []
        self._discovered_sub_devices: list[Any] = []

        # ── Time-sliced polling ─────────────────────────────────────
        self._poll_counter: int = 0
        self._force_full_poll: bool = False

        super().__init__(address, type, sn)

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

    def _build_pack_main_struct(self):
        s = self.pack_main_struct
        s.add_decimal_field("packVoltage", 6000, 2)
        s.add_decimal_field("packCurrent", 6001, 2)
        s.add_uint_field("packSoc", 6002)
        s.add_temperature_field("packTemperature", 6003, 0)
        s.add_bcd_sn_field("packSerial", 6004, 4)
        s.add_uint_field("cycleCount", 6008)

    def _build_pack_item_struct(self):
        s = self.pack_item_struct
        for i in range(16):
            s.add_uint_field(f"cellVoltage{i + 1}", 6100 + i)

    # ── Parse dispatch ─────────────────────────────────────────────────

    def parse(self, address: int, data: bytes) -> dict:
        if APP_HOME_DATA <= address < INV_BASE_INFO:
            result = self.home_struct.parse(address, data)
            self._fill_v2_alarms(result, data)
            return result
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
        elif INV_BASE_SETTINGS <= address < 2300:
            return self.control_struct.parse(address, data)
        elif address == NODE_INFO:
            return self._parse_node_info(data)
        elif PACK_MAIN_INFO <= address < PACK_ITEM_INFO:
            result = self.pack_main_struct.parse(address, data) if hasattr(self, "pack_main_struct") else {}
            self._fill_v2_pack_alarms(result, data)
            return result
        elif PACK_ITEM_INFO <= address < PACK_BMU_INFO:
            return self.pack_item_struct.parse(address, data) if hasattr(self, "pack_item_struct") else {}
        return {}

    def parse_tlv(self, data: bytes) -> dict:
        """Parse a TLV-bundled response and dispatch each item to its struct."""
        result: dict = {}
        items = TlvParser.parse(data)
        for item in items:
            parsed = self.parse(item.reg_addr, item.value)
            if item.slave_addr != 0:
                prefix = f"sub[{item.slave_addr}]"
                for k, v in parsed.items():
                    result[f"{prefix}.{k}"] = v
            else:
                result.update(parsed)
        return result

    def _parse_node_info(self, data: bytes) -> dict:
        result: dict = {}
        items = TlvParser.parse(data)
        for item in items:
            prefix = f"sub[{item.slave_addr}]"
            try:
                if PACK_MAIN_INFO <= item.reg_addr < PACK_ITEM_INFO:
                    if hasattr(self, "pack_main_struct"):
                        parsed = self.pack_main_struct.parse(item.reg_addr, item.value)
                        self._fill_v2_pack_alarms(parsed, item.value)
                        for k, v in parsed.items():
                            result[f"{prefix}.{k}"] = v
                elif PACK_ITEM_INFO <= item.reg_addr < PACK_BMU_INFO:
                    if hasattr(self, "pack_item_struct"):
                        parsed = self.pack_item_struct.parse(item.reg_addr, item.value)
                        for k, v in parsed.items():
                            result[f"{prefix}.{k}"] = v
            except Exception:
                pass
        return result

    # ── Alarm decoding ─────────────────────────────────────────────────

    def _fill_v2_alarms(self, result: dict, data: bytes) -> None:
        """Decode inverter alarmInfo and faultInfo from an APP_HOME_DATA payload.

        Byte offsets are from ProtocolParserV2.parseHomeData (APK v3.0.9):
          alarmInfo: bytes 52–59, 4 × 16-bit words  TODO(hardware): verify
          faultInfo: bytes 66–77, 6 × 16-bit words  TODO(hardware): verify
        """
        warn_names, fault_names = self._V2_INV_TABLES[self.V2_ALARM_PROFILE]

        for word_idx in range(4):
            off = 52 + word_idx * 2
            if len(data) < off + 2:
                break
            word_val = _u16(data, off)
            names = warn_names.get(word_idx + 1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names) and names[bit] is not None:
                    result[f"alarm.{names[bit]}"] = True

        for word_idx in range(6):
            off = 66 + word_idx * 2
            if len(data) < off + 2:
                break
            word_val = _u16(data, off)
            names = fault_names.get(word_idx + 1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names) and names[bit] is not None:
                    result[f"fault.{names[bit]}"] = True

    def _fill_v2_pack_alarms(self, result: dict, data: bytes) -> None:
        """Decode pack alarm/error bits from a PACK_MAIN_INFO payload.

        Only runs when PACK_ALARM_PROFILE is set. Byte offsets from
        ProtocolParserV2.parsePackMainInfo (APK v3.0.9):
          packSysErr:        bytes 76–81, 3 × 16-bit words  TODO(hardware): verify
          packHighVoltAlarm: bytes 82–83, 1 × 16-bit word   TODO(hardware): verify
        """
        if self.PACK_ALARM_PROFILE is None:
            return
        alarm_names, error_names = self._V2_PACK_TABLES[self.PACK_ALARM_PROFILE]

        for word_idx in range(3):
            off = 76 + word_idx * 2
            if len(data) < off + 2:
                break
            word_val = _u16(data, off)
            names = error_names.get(word_idx + 1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names) and names[bit] is not None:
                    result[f"fault.{names[bit]}"] = True

        off = 82
        if len(data) >= off + 2:
            word_val = _u16(data, off)
            names = alarm_names.get(1, [])
            for bit in range(16):
                if (word_val >> bit) & 1 and bit < len(names) and names[bit] is not None:
                    result[f"alarm.{names[bit]}"] = True

    # ── Writable-field plumbing ────────────────────────────────────────

    def _all_polling_structs(self) -> tuple[DeviceStruct, ...]:
        return (
            self.home_struct,
            self.inv_base_struct,
            self.inv_pv_struct,
            self.inv_grid_struct,
            self.inv_load_struct,
            self.inv_inv_struct,
            self.control_struct,
            self.pack_main_struct,
            self.pack_item_struct,
        )

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

        from ..struct import DecimalField, UintField

        if isinstance(device_field, UintField) and device_field.unit and isinstance(value, str):
            value = value.removesuffix(device_field.unit).strip()

        if isinstance(device_field, DecimalField) and device_field.range is not None:
            from decimal import Decimal

            if not device_field.in_range(Decimal(value)):
                raise ValueError(
                    f"{field}: value {value} not in range ({device_field.range[0]}, {device_field.range[1]})"
                )
        elif isinstance(device_field, UintField) and device_field.range is not None:
            if not device_field.in_range(int(value)):
                raise ValueError(
                    f"{field}: value {value} not in range ({device_field.range[0]}, {device_field.range[1]})"
                )

        return WriteSingleRegister(device_field.address, int(value))

    # ── Device properties ──────────────────────────────────────────────

    @property
    def use_tlv_polling(self) -> bool:
        return self.protocol_version >= 2000

    def _tlv_sections(self) -> list[tuple[int, int]]:
        """Sections for the main-slave (1) TLV bundle.

        Fast blocks (every cycle): HOME, NODE_INFO, plus a pre-discovery PACK
        read for battery-pack devices that haven't yet seen a NODE_INFO
        response.
        Slow blocks (every 3rd cycle): INV_BASE, PV, GRID, LOAD, INV.

        Per-slave pack reads are not included here — they are emitted as
        separate bundles by ``tlv_polling_commands`` once topology is
        discovered.
        """
        sections: list[tuple[int, int]] = [
            (APP_HOME_DATA, self.HOME_DATA_REGS),
        ]
        slow_blocks = [
            (INV_BASE_INFO, 51),
            (INV_PV_INFO, 70),
            (INV_GRID_INFO, 31),
            (INV_LOAD_INFO, 48),
            (INV_INV_INFO, 30),
        ]
        include_slow = self._force_full_poll or (self._poll_counter % 3 == 0)
        if include_slow:
            sections.extend(slow_blocks)
        if self.has_sub_devices:
            sections.append((NODE_INFO, 32))
        # Pre-discovery fallback: a battery-pack device that has not yet seen
        # NODE_INFO data reads PACK_MAIN_INFO from the main slave so the home
        # screen has something to show on the first poll.
        if self.has_battery_packs and not self._discovered_packs:
            sections.append((PACK_MAIN_INFO, 32))
        return sections

    def tick_poll_counter(self) -> None:
        """Advance the poll cycle counter after each poll."""
        self._poll_counter += 1
        if self._poll_counter >= 10000:
            self._poll_counter = 0
        self._force_full_poll = False

    def force_full_poll(self) -> None:
        """Force the next poll cycle to include all register blocks."""
        self._force_full_poll = True
        self._poll_counter = 3 * (self._poll_counter // 3 + 1) - 3

    @property
    def tlv_polling_commands(self) -> List[TlvReadHoldingRegisters]:
        cmds = [TlvReadHoldingRegisters(self._tlv_sections(), slave_addr=1)]
        # Per-slave pack reads: one TLV bundle per discovered pack, matching
        # the APK's ModbusV2Dispatcher behavior. Before discovery, the main
        # bundle's pre-discovery fallback handles it (see _tlv_sections).
        for pack_slave in self._discovered_packs:
            cmds.append(TlvReadHoldingRegisters([(PACK_MAIN_INFO, 32)], slave_addr=pack_slave))
        return cmds

    def discover_topology(self, tlv_data: bytes) -> None:
        """Parse a NODE_INFO TLV response and update discovered topology.

        Called once after BLE connect.  Extracts battery pack slave
        addresses and sub-device entries from the TLV data.
        """
        items = TlvParser.parse(tlv_data)
        self._discovered_packs.clear()
        self._discovered_sub_devices.clear()
        for item in items:
            if PACK_MAIN_INFO <= item.reg_addr < PACK_BMU_INFO:
                self._discovered_packs.append(item.slave_addr)
            else:
                self._discovered_sub_devices.append(item)
        self._topology_discovered = True

    @property
    def topology_discovered(self) -> bool:
        # True only after discover_topology() has consumed a NODE_INFO TLV
        # response. Class-level has_battery_packs declarations are not enough
        # — until the device actually answers, _discovered_packs is empty
        # and per-slave reads can't be addressed correctly.
        return self._topology_discovered

    @property
    def polling_commands(self) -> List[ReadHoldingRegisters]:
        cmds = [
            ReadHoldingRegisters(APP_HOME_DATA, self.HOME_DATA_REGS),
        ]
        if self._force_full_poll or self._poll_counter % 3 == 0:
            cmds.extend(
                [
                    ReadHoldingRegisters(INV_BASE_INFO, 51),
                    ReadHoldingRegisters(INV_PV_INFO, 70),
                    ReadHoldingRegisters(INV_GRID_INFO, 31),
                    ReadHoldingRegisters(INV_LOAD_INFO, 48),
                    ReadHoldingRegisters(INV_INV_INFO, 30),
                ]
            )
        if self.has_sub_devices:
            cmds.append(ReadHoldingRegisters(NODE_INFO, 32))
        if self._discovered_packs:
            for pack_slave in self._discovered_packs:
                cmds.append(ReadHoldingRegisters(PACK_MAIN_INFO, 32, slave=pack_slave))
        elif self.has_battery_packs:
            cmds.append(ReadHoldingRegisters(PACK_MAIN_INFO, 32))
        return cmds

    @property
    def logging_commands(self) -> List[ReadHoldingRegisters]:
        return self.polling_commands

    @property
    def writable_ranges(self) -> List[range]:
        return [range(2000, 2087), range(2200, 2272)]
