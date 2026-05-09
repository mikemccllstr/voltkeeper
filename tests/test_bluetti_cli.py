# ABOUTME: Unit tests for bluetti-cli — utility functions, struct-based protocol parsers, CLI behavior.
# ABOUTME: Uses real AC2A register data captured via BLE as test fixtures.

import asyncio
import csv
import json
import time
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from click.testing import CliRunner

import src.bluetti_cli.load_test as lt
from src.bluetti_cli.bus import CommandMessage, EventBus, ParserMessage
from src.bluetti_cli.cli import cli
from src.bluetti_cli.core.commands import WriteMultipleRegisters, WriteSingleRegister
from src.bluetti_cli.core.devices.ac2a import AC2A, ChargingMode
from src.bluetti_cli.core.devices.bluetti_device import BluettiDevice
from src.bluetti_cli.core.utils import (
    _ascii,
    _bcd_sn,
    _format_version,
    _s16,
    _s32,
    _u16,
    _u32,
    crc16_modbus,
)
from src.bluetti_cli.device_handler import SourceChangeWatcher, _watch_source_changes
from src.bluetti_cli.mqtt_client import (
    CHARGING_STATUS_MAP,
    COMMAND_TOPIC_RE,
    NORMAL_DEVICE_FIELDS,
    MQTTClient,
    MqttFieldType,
)
from src.bluetti_cli.shutdown_watch import ShutdownWatch


@pytest.fixture
def ac2a_device():
    return AC2A("00:00:00:00:00:00", "TEST")


@pytest.fixture
def ac2a_device_num():
    """AC2A with a numeric SN so COMMAND_TOPIC_RE (requires \\d+) can match."""
    return AC2A("00:00:00:00:00:00", "12345678")


# ═══════════════════════════════════════════════════════════════════════
#  CRC-16-Modbus
# ═══════════════════════════════════════════════════════════════════════


class TestCrc16Modbus:
    def test_empty_returns_init_value(self):
        assert crc16_modbus(b"") == b"\xff\xff"

    def test_roundtrip_verify(self):
        frame = b"\x01\x03\x00\x64\x00\x06"
        crc = crc16_modbus(frame)
        assert crc16_modbus(frame + crc) == b"\x00\x00"

    def test_deterministic(self):
        assert crc16_modbus(b"\x01\x03\x00\x64\x00\x06") == crc16_modbus(
            b"\x01\x03\x00\x64\x00\x06"
        )

    def test_known_vector(self):
        assert crc16_modbus(b"\x02\x07") == b"\x41\x12"


# ═══════════════════════════════════════════════════════════════════════
#  16-bit integer helpers
# ═══════════════════════════════════════════════════════════════════════


class TestU16:
    def test_zero(self):
        assert _u16(b"\x00\x00", 0) == 0

    def test_max(self):
        assert _u16(b"\xff\xff", 0) == 65535

    def test_mid_value(self):
        assert _u16(b"\x12\x34", 0) == 0x1234

    def test_offset(self):
        assert _u16(b"\x00\x00\xab\xcd", 2) == 0xABCD


class TestS16:
    def test_zero(self):
        assert _s16(b"\x00\x00", 0) == 0

    def test_positive(self):
        assert _s16(b"\x12\x34", 0) == 0x1234

    def test_negative_one(self):
        assert _s16(b"\xff\xff", 0) == -1

    def test_negative(self):
        assert _s16(b"\x80\x00", 0) == -32768

    def test_max_positive(self):
        assert _s16(b"\x7f\xff", 0) == 32767


# ═══════════════════════════════════════════════════════════════════════
#  32-bit integer helpers (low-register-first)
# ═══════════════════════════════════════════════════════════════════════


class TestU32:
    def test_zero(self):
        assert _u32(b"\x00\x00\x00\x00", 0) == 0

    def test_max(self):
        assert _u32(b"\xff\xff\xff\xff", 0) == 0xFFFFFFFF

    def test_low_register_first_small_value(self):
        assert _u32(b"\x00\xc7\x00\x00", 0) == 199

    def test_higher_register_set(self):
        assert _u32(b"\x00\x00\x00\x01", 0) == 65536

    def test_offset(self):
        data = b"\x00\x00\x00\x00\x56\x78\x12\x34"
        assert _u32(data, 4) == 0x12345678

    def test_grid_power_example(self):
        assert _u32(b"\x00\x93\x00\x00", 0) == 147


class TestS32:
    def test_zero(self):
        assert _s32(b"\x00\x00\x00\x00", 0) == 0

    def test_positive(self):
        assert _s32(b"\x00\x93\x00\x00", 0) == 147

    def test_negative_one(self):
        assert _s32(b"\xff\xff\xff\xff", 0) == -1

    def test_negative(self):
        assert _s32(b"\x00\x00\x80\x00", 0) == -2147483648


# ═══════════════════════════════════════════════════════════════════════
#  ASCII string parsing
# ═══════════════════════════════════════════════════════════════════════


class TestAscii:
    def test_plain_string(self):
        assert _ascii(b"HELLO\x00\x00\x00", 0, 8) == "HELLO"

    def test_null_terminated(self):
        assert _ascii(b"AC2A\x00\x00\x00\x00\x00\x00\x00\x00", 0, 12) == "AC2A"

    def test_strips_whitespace(self):
        assert _ascii(b"  foo  \x00", 0, 8) == "foo"

    def test_non_ascii_replaced(self):
        result = _ascii(b"\xff\xfe", 0, 2)
        assert isinstance(result, str)

    def test_byte_swap_plain(self):
        assert _ascii(b"BA", 0, 2, byte_swap=True) == "AB"

    def test_byte_swap_ac2a_model(self):
        raw = b"\x43\x41\x41\x32\x00\x00\x00\x00\x00\x00\x00\x00"
        assert _ascii(raw, 0, 12, byte_swap=True) == "AC2A"

    def test_byte_swap_odd_length(self):
        assert _ascii(b"BAZ", 0, 3, byte_swap=True) == "ABZ"


# ═══════════════════════════════════════════════════════════════════════
#  BCD serial number parsing
# ═══════════════════════════════════════════════════════════════════════


class TestBcdSn:
    def test_all_zeros(self):
        assert _bcd_sn(b"\x00\x00\x00\x00", 0, 4) == ""

    def test_byte_swapped_pairs(self):
        data = b"\x9c\x75\x97\x7f"
        result = _bcd_sn(data, 0, 4)
        assert result.startswith("759C")
        assert "7F97" in result

    def test_offset(self):
        data = b"\xff\xff\x12\x34"
        assert _bcd_sn(data, 2, 2) == "3412"


# ═══════════════════════════════════════════════════════════════════════
#  Firmware version formatting
# ═══════════════════════════════════════════════════════════════════════


class TestFormatVersion:
    def test_short(self):
        assert _format_version(100) == "v100"

    def test_four_digits(self):
        assert _format_version(9001) == "v9001"

    def test_five_digits(self):
        assert _format_version(77337) == "v7733.7"

    def test_six_digits(self):
        assert _format_version(123456) == "v1234.56"

    def test_seven_plus(self):
        assert _format_version(773390339) == "v77339.03.39"

    def test_zero(self):
        assert _format_version(0) == "v0"


# ═══════════════════════════════════════════════════════════════════════
#  Home data parser (register 100) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseHomeData:
    def test_empty_data(self, ac2a_device):
        assert ac2a_device.parse(100, b"") == {}
        result = ac2a_device.parse(100, b"\x00" * 4)
        assert "packTotalVoltage" in result
        assert "packTotalCurrent" in result
        assert len(result) == 2

    def test_battery_fields_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "packTotalVoltage" in result
        assert "packTotalCurrent" in result
        assert "packTotalSoc" in result
        assert "packChargingStatus" in result
        assert 20 <= result["packTotalVoltage"] <= 40
        assert 0 <= result["packTotalCurrent"] <= 100
        assert 0 <= result["packTotalSoc"] <= 100
        assert result["packChargingStatus"] in (0, 1, 2, 3)

    def test_model_name_is_ac2a(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert result["deviceModel"].startswith("AC2A")

    def test_serial_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "deviceSN" in result
        assert len(result["deviceSN"]) > 0

    def test_power_meters_have_keys(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        for key in ("totalDCPower", "totalACPower", "totalPVPower", "totalGridPower"):
            assert key in result

    def test_energy_totals_have_keys(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        for key in (
            "totalDCEnergy",
            "totalACEnergy",
            "totalPVChargingEnergy",
            "totalGridChargingEnergy",
        ):
            assert key in result
            assert result[key] >= 0.0

    def test_status_fields_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "chargingMode" in result
        assert "invWorkingStatus" in result

    def test_short_data_only_basics(self, ac2a_device):
        data = b"\x0a\xaa\x00\x16\x00\x64\x00\x02\x01\x00\x01\x00"
        result = ac2a_device.parse(100, data)
        assert result["packTotalSoc"] == 100
        assert result["packTotalVoltage"] == Decimal("27.3")
        assert "deviceModel" not in result


# ═══════════════════════════════════════════════════════════════════════
#  Inverter base info parser (register 1100) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvBaseInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1100, b"") == {}

    def test_inv_type(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result["invType"] == "AC2A"

    def test_inv_id(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result["invId"] == 0

    def test_software_versions_present(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        soft_keys = [k for k in result if k.startswith("software[")]
        assert len(soft_keys) >= 0
        for k in soft_keys:
            assert "ver=v" in result[k]

    def test_temperatures_absent_when_sensor_off(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result.get("ambientTemp") is None
        assert result.get("invMaxTemp") is None


# ═══════════════════════════════════════════════════════════════════════
#  Inverter PV info parser (register 1200) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvPvInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1200, b"") == {}

    def test_keys_present(self, ac2a_device, ac2a_inv_pv_bytes):
        result = ac2a_device.parse(1200, ac2a_inv_pv_bytes)
        assert "totalChgPower" in result
        assert "totalChgEnergy" in result


# ═══════════════════════════════════════════════════════════════════════
#  Grid info parser (register 1300) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvGridInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1300, b"") == {}

    def test_frequency_in_range(self, ac2a_device, ac2a_inv_grid_bytes):
        result = ac2a_device.parse(1300, ac2a_inv_grid_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_device, ac2a_inv_grid_bytes):
        result = ac2a_device.parse(1300, ac2a_inv_grid_bytes)
        assert "gridPhase[0].voltage" in result
        assert "gridPhase[0].current" in result
        assert "gridPhase[0].power" in result


# ═══════════════════════════════════════════════════════════════════════
#  Load info parser (register 1400) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvLoadInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1400, b"") == {}

    def test_dc_keys_present(self, ac2a_device, ac2a_inv_load_bytes):
        result = ac2a_device.parse(1400, ac2a_inv_load_bytes)
        for key in ("dc5VPower", "dc12VPower", "dc24VPower"):
            assert key in result


# ═══════════════════════════════════════════════════════════════════════
#  Inverter output parser (register 1500) — via AC2A struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvInvInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1500, b"") == {}

    def test_frequency_in_range(self, ac2a_device, ac2a_inv_inv_bytes):
        result = ac2a_device.parse(1500, ac2a_inv_inv_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_device, ac2a_inv_inv_bytes):
        result = ac2a_device.parse(1500, ac2a_inv_inv_bytes)
        assert "invPhase[0].voltage" in result
        assert "invPhase[0].current" in result
        assert "invPhase[0].power" in result
        assert "invPhase[0].workStatus" in result


# ═══════════════════════════════════════════════════════════════════════
#  Control register parser (register 2000) — via AC2A control_struct
# ═══════════════════════════════════════════════════════════════════════


class TestParseControlData:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(2000, b"") == {}

    def test_ac_output_on(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["ac_output"] is True

    def test_dc_output_off(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["dc_output"] is False

    def test_ac_eco_mode_on(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["ac_eco_mode"] is True

    def test_charging_mode_turbo(self, ac2a_device, ac2a_control_bytes):
        from src.bluetti_cli.core.devices.ac2a import ChargingMode

        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["charging_mode"] == ChargingMode.TURBO

    def test_battery_range(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["battery_range_start"] == 20
        assert result["battery_range_end"] == 80

    def test_build_setter_ac_output_on(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("ac_output", True)
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_build_setter_dc_output_off(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_output", False)
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_build_setter_charging_mode_enum(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "TURBO")
        assert cmd.address == 2020
        assert cmd.value == 1

    def test_has_field_setter_writable(self, ac2a_device):
        assert ac2a_device.has_field_setter("ac_output") is True
        assert ac2a_device.has_field_setter("dc_output") is True
        assert ac2a_device.has_field_setter("charging_mode") is True

    def test_has_field_setter_read_only(self, ac2a_device):
        assert ac2a_device.has_field_setter("packTotalSoc") is False
        assert ac2a_device.has_field_setter("totalACPower") is False


# ═══════════════════════════════════════════════════════════════════════
#  Write command classes — frame construction, CRC, response sizes
# ═══════════════════════════════════════════════════════════════════════


class TestWriteCommands:
    def test_write_single_frame(self):
        cmd = WriteSingleRegister(0x07DB, 1)
        frame = bytes(cmd)
        assert len(frame) == 8
        assert frame[:4] == b"\x01\x06\x07\xdb"
        assert frame[4:6] == b"\x00\x01"
        assert crc16_modbus(frame[:-2]) == frame[-2:]

    def test_write_single_zero_value(self):
        cmd = WriteSingleRegister(0x07DC, 0)
        frame = bytes(cmd)
        assert len(frame) == 8
        assert frame[:4] == b"\x01\x06\x07\xdc"
        assert frame[4:6] == b"\x00\x00"

    def test_write_single_response_size(self):
        cmd = WriteSingleRegister(2011, 1)
        assert cmd.response_size() == 8

    def test_write_single_exception_detection(self):
        cmd = WriteSingleRegister(2011, 1)
        exception = bytes([0x01, 0x86, 0x02])
        exception += crc16_modbus(exception)
        assert cmd.is_exception_response(exception)

    def test_write_multiple_frame(self):
        cmd = WriteMultipleRegisters(0x02BC, bytes([0x00, 0x01, 0x02, 0x03]))
        frame = bytes(cmd)
        assert len(frame) == 13
        assert frame[:2] == b"\x01\x10"
        assert crc16_modbus(frame[:-2]) == frame[-2:]

    def test_write_multiple_rejects_odd_length(self):
        with pytest.raises(ValueError, match="multiple of 2"):
            WriteMultipleRegisters(100, b"\x01\x02\x03")

    def test_write_multiple_response_size(self):
        cmd = WriteMultipleRegisters(0x02BC, bytes([0x00, 0x01]))
        assert cmd.response_size() == 8


# ═══════════════════════════════════════════════════════════════════════
#  ChargingMode enum
# ═══════════════════════════════════════════════════════════════════════


class TestChargingMode:
    def test_values(self):
        assert ChargingMode.STANDARD.value == 0
        assert ChargingMode.TURBO.value == 1
        assert ChargingMode.SILENT.value == 2

    def test_name_lookup(self):
        assert ChargingMode["STANDARD"].value == 0
        assert ChargingMode["TURBO"].value == 1
        assert ChargingMode["SILENT"].value == 2

    def test_value_lookup(self):
        assert ChargingMode(0) == ChargingMode.STANDARD
        assert ChargingMode(1) == ChargingMode.TURBO
        assert ChargingMode(2) == ChargingMode.SILENT


# ═══════════════════════════════════════════════════════════════════════
#  CTRL_EVENT bit decoder
# ═══════════════════════════════════════════════════════════════════════


class TestCtrlEvent:
    def test_all_off(self, ac2a_device):
        caps = AC2A.decode_ctrl_event(0)
        assert all(not v for v in caps.values())
        assert len(caps) == 11

    def test_all_on(self, ac2a_device):
        caps = AC2A.decode_ctrl_event(0x07FF)
        assert all(caps.values())

    def test_partial_bits(self, ac2a_device):
        caps = AC2A.decode_ctrl_event(0x0407)
        assert caps["power_control"]
        assert caps["ac_control"]
        assert caps["dc_control"]
        assert not caps["inv_control"]
        assert caps["super_power"]


# ═══════════════════════════════════════════════════════════════════════
#  AC2A writable field model — field detection and command building
# ═══════════════════════════════════════════════════════════════════════


class TestAC2AWritableFields:
    def test_writable_fields_known(self, ac2a_device):
        for field in AC2A.WRITABLE_FIELD_NAMES:
            assert ac2a_device.has_field_setter(field), f"{field} should be writable"

    def test_readonly_fields_not_writable(self, ac2a_device):
        assert not ac2a_device.has_field_setter("packTotalSoc")
        assert not ac2a_device.has_field_setter("deviceModel")
        assert not ac2a_device.has_field_setter("totalDCPower")

    def test_unknown_field_rejected(self, ac2a_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            ac2a_device.build_setter_command("nonexistent", "on")

    def test_bool_true_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("ac_output", "on")
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_bool_false_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_output", "off")
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_bool_true_bool(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("power_lifting", True)
        assert cmd.address == 2021
        assert cmd.value == 1

    def test_bool_false_bool(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("power_lifting", False)
        assert cmd.value == 0

    def test_enum_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "turbo")
        assert cmd.address == 2020
        assert cmd.value == ChargingMode.TURBO.value

    def test_enum_string_case_insensitive(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "SILENT")
        assert cmd.value == ChargingMode.SILENT.value

    def test_uint_value(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("battery_range_start", 50)
        assert cmd.address == 2022
        assert cmd.value == 50

    def test_control_struct_has_ctrl_event(self, ac2a_device):
        names = [f.name for f in ac2a_device.control_struct.fields]
        assert "ctrl_event" in names
        assert "ac_output" in names
        assert "charging_mode" in names


# ═══════════════════════════════════════════════════════════════════════
#  BluettiDevice base class contract
# ═══════════════════════════════════════════════════════════════════════


class TestBluettiDeviceBase:
    def test_parse_raises_not_implemented(self):
        """Base parse() must raise NotImplementedError, not AttributeError."""
        device = BluettiDevice("00:00:00:00:00:00", "TEST", "SN")
        with pytest.raises(NotImplementedError):
            device.parse(100, b"\x00" * 4)

    def test_has_field_raises_not_implemented(self):
        device = BluettiDevice("00:00:00:00:00:00", "TEST", "SN")
        with pytest.raises(NotImplementedError):
            device.has_field("packTotalSoc")


# ═══════════════════════════════════════════════════════════════════════
#  EventBus — message routing
# ═══════════════════════════════════════════════════════════════════════


class TestEventBus:
    @pytest.mark.asyncio
    async def test_parser_message_dispatched(self, ac2a_device):
        bus = EventBus()
        received = []

        async def listener(msg: ParserMessage):
            received.append(msg)

        bus.add_parser_listener(listener)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(ParserMessage(ac2a_device, {"test": 1}))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].device is ac2a_device
        assert received[0].parsed == {"test": 1}

    @pytest.mark.asyncio
    async def test_command_message_dispatched(self, ac2a_device):
        bus = EventBus()
        received = []

        async def listener(msg: CommandMessage):
            received.append(msg)

        cmd = WriteSingleRegister(2011, 1)
        bus.add_command_listener(listener)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(CommandMessage(ac2a_device, cmd))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].device is ac2a_device
        assert received[0].command.address == 2011

    @pytest.mark.asyncio
    async def test_multiple_listeners(self, ac2a_device):
        bus = EventBus()
        results = []

        async def listener_a(msg: ParserMessage):
            results.append("a")

        async def listener_b(msg: ParserMessage):
            results.append("b")

        bus.add_parser_listener(listener_a)
        bus.add_parser_listener(listener_b)
        bus_task = asyncio.create_task(bus.run())
        await bus.put(ParserMessage(ac2a_device, {}))
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert sorted(results) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_messages_put_before_run_are_not_lost(self, ac2a_device):
        """Messages enqueued before run() starts must not be dropped."""
        bus = EventBus()
        received = []

        async def listener(msg: ParserMessage):
            received.append(msg)

        bus.add_parser_listener(listener)
        # put() is called BEFORE run() — the queue must be the same object
        await bus.put(ParserMessage(ac2a_device, {"pre": True}))

        bus_task = asyncio.create_task(bus.run())
        await asyncio.sleep(0.1)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].parsed == {"pre": True}


# ═══════════════════════════════════════════════════════════════════════
#  MQTT client — topic parsing, field configs, HA payloads
# ═══════════════════════════════════════════════════════════════════════


class TestMqttClient:
    def test_command_topic_re_matches(self):
        m = COMMAND_TOPIC_RE.match("bluetti/command/AC2A-12345678/ac_output")
        assert m is not None
        assert m[1] == "AC2A"
        assert m[2] == "12345678"
        assert m[3] == "ac_output"

    def test_command_topic_re_non_matches(self):
        assert COMMAND_TOPIC_RE.match("bluetti/state/AC2A-123/total_battery_percent") is None
        assert COMMAND_TOPIC_RE.match("other/command/AC2A-123/ac_output") is None
        assert COMMAND_TOPIC_RE.match("bluetti/command/abc") is None

    def test_normal_fields_have_battery_keys(self):
        assert "packTotalSoc" in NORMAL_DEVICE_FIELDS
        assert "packTotalVoltage" in NORMAL_DEVICE_FIELDS
        assert "packChargingStatus" in NORMAL_DEVICE_FIELDS

    def test_normal_fields_have_power_keys(self):
        assert "totalPVPower" in NORMAL_DEVICE_FIELDS
        assert "totalACPower" in NORMAL_DEVICE_FIELDS
        assert "totalDCPower" in NORMAL_DEVICE_FIELDS

    def test_normal_fields_have_control_keys(self):
        assert "ac_output" in NORMAL_DEVICE_FIELDS
        assert "dc_output" in NORMAL_DEVICE_FIELDS
        assert "charging_mode" in NORMAL_DEVICE_FIELDS
        assert "power_off" in NORMAL_DEVICE_FIELDS

    def test_bool_field_config(self):
        config = NORMAL_DEVICE_FIELDS["ac_output"]
        assert config.type == MqttFieldType.BOOL
        assert config.setter is True
        assert config.advanced is False

    def test_enum_field_config(self):
        config = NORMAL_DEVICE_FIELDS["charging_mode"]
        assert config.type == MqttFieldType.ENUM
        assert config.setter is True
        assert "options" in config.home_assistant_extra

    def test_button_field_config(self):
        config = NORMAL_DEVICE_FIELDS["power_off"]
        assert config.type == MqttFieldType.BUTTON
        assert config.home_assistant_extra["payload_press"] == "ON"

    def test_ha_payload_has_device_info(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["packTotalSoc"]
        payload = mqtt._ha_config_payload("packTotalSoc", ac2a_device, config)

        data = json.loads(payload)
        assert "device" in data
        assert data["device"]["manufacturer"] == "Bluetti"
        assert data["device"]["model"] == "AC2A"
        assert "TEST" in data["device"]["identifiers"]

    def test_ha_payload_setter_has_command_topic(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["ac_output"]
        payload = mqtt._ha_config_payload("ac_output", ac2a_device, config)

        data = json.loads(payload)
        assert "command_topic" in data
        # command_topic must use the field key ("ac_output"), not topic_name
        # ("ac_output_on"), so that _handle_command can match it in
        # NORMAL_DEVICE_FIELDS and dispatch the write correctly.
        assert data["command_topic"] == "bluetti/command/AC2A-TEST/ac_output"

    def test_ha_payload_nonsetter_no_command_topic(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["packTotalSoc"]
        payload = mqtt._ha_config_payload("packTotalSoc", ac2a_device, config)

        data = json.loads(payload)
        assert "command_topic" not in data
        assert data["state_topic"] == "bluetti/state/AC2A-TEST/total_battery_percent"

    def test_charging_status_map(self):
        assert CHARGING_STATUS_MAP[0] == "IDLE"
        assert CHARGING_STATUS_MAP[1] == "CHARGING"
        assert CHARGING_STATUS_MAP[2] == "DISCHARGING"
        assert CHARGING_STATUS_MAP[3] == "FLOATING"

    def test_all_fields_have_topic_name(self):
        for name, config in NORMAL_DEVICE_FIELDS.items():
            assert config.topic_name is not None, f"{name} missing topic_name"

    def test_topic_names_are_snake_case(self):
        for name, config in NORMAL_DEVICE_FIELDS.items():
            topic = config.topic_name
            assert topic, f"{name} has empty topic_name"
            assert "_" in topic or topic.islower(), f"{name} topic '{topic}' not snake_case"
            assert topic == topic.lower(), f"{name} topic '{topic}' has uppercase"

    def test_battery_fields_match_bluetti_mqtt(self):
        assert NORMAL_DEVICE_FIELDS["packTotalSoc"].topic_name == "total_battery_percent"
        assert NORMAL_DEVICE_FIELDS["packTotalVoltage"].topic_name == "total_battery_voltage"
        assert NORMAL_DEVICE_FIELDS["packTotalCurrent"].topic_name == "total_battery_current"

    def test_control_fields_match_bluetti_mqtt(self):
        assert NORMAL_DEVICE_FIELDS["ac_output"].topic_name == "ac_output_on"
        assert NORMAL_DEVICE_FIELDS["dc_output"].topic_name == "dc_output_on"
        assert NORMAL_DEVICE_FIELDS["chargingMode"].topic_name == "charging_mode"
        assert NORMAL_DEVICE_FIELDS["power_lifting"].topic_name == "power_lifting_on"

    def test_listener_registered_exactly_once_at_init(self):
        """MQTTClient must register its listener at construction, not inside run()."""
        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        # Exactly one listener after construction — not zero (added too late)
        # and not growing on every reconnect.
        assert len(bus.parser_listeners) == 1
        assert bus.parser_listeners[0] == mqtt.handle_message

    # ── _handle_message publish path ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_handle_message_publishes_numeric(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packTotalSoc": 85}),
        )

        mock_client.publish.assert_called_once()
        topic, = [c.args[0] for c in mock_client.publish.call_args_list]
        assert topic == "bluetti/state/AC2A-TEST/total_battery_percent"
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"85"

    @pytest.mark.asyncio
    async def test_handle_message_publishes_bool_on_off(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"ac_output": True}),
        )
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"ON"

        mock_client.publish.reset_mock()
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"ac_output": False}),
        )
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"OFF"

    @pytest.mark.asyncio
    async def test_handle_message_time_to_full_scaled(self, ac2a_device):
        """packChgFullTime raw value is ×6 to convert 0.1h units to minutes."""
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        # charging → time_to_full should be published, time_to_empty skipped
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 1, "packChgFullTime": 10}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert "bluetti/state/AC2A-TEST/time_to_full_minutes" in calls
        assert calls["bluetti/state/AC2A-TEST/time_to_full_minutes"] == b"60"
        assert "bluetti/state/AC2A-TEST/time_to_empty_minutes" not in calls

    @pytest.mark.asyncio
    async def test_handle_message_time_to_empty_skipped_when_charging(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        # discharging → time_to_empty published, time_to_full skipped
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 2, "packDsgEmptyTime": 20}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert "bluetti/state/AC2A-TEST/time_to_empty_minutes" in calls
        assert calls["bluetti/state/AC2A-TEST/time_to_empty_minutes"] == b"120"
        assert "bluetti/state/AC2A-TEST/time_to_full_minutes" not in calls

    @pytest.mark.asyncio
    async def test_handle_message_charging_status_enum(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 2}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert calls["bluetti/state/AC2A-TEST/pack_charging_status"] == b"DISCHARGING"

    @pytest.mark.asyncio
    async def test_handle_message_unknown_field_skipped(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"notAKnownField": 99}),
        )
        mock_client.publish.assert_not_called()

    # ── _handle_command dispatch path ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_handle_command_bool_on_puts_write_command(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mqtt.devices.append(ac2a_device_num)

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-12345678/ac_output"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].command.address == 2011
        assert received[0].command.value == 1

    @pytest.mark.asyncio
    async def test_handle_command_bool_off(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mqtt.devices.append(ac2a_device_num)

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-12345678/dc_output"
        mock_msg.payload = b"OFF"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].command.address == 2012
        assert received[0].command.value == 0

    @pytest.mark.asyncio
    async def test_handle_command_unknown_topic_ignored(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/bad-topic"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_handle_command_unknown_device_ignored(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        # ac2a_device_num NOT added to mqtt.devices — valid format but unknown device

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-99999999/ac_output"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 0


# ═══════════════════════════════════════════════════════════════════════
#  DeviceHandler — polling data flow
# ═══════════════════════════════════════════════════════════════════════


class TestDeviceHandler:
    @pytest.mark.asyncio
    async def test_poll_once_no_double_strip(self, ac2a_device, ac2a_home_bytes):
        """execute() already returns stripped body; _poll_once must not strip again."""
        from unittest.mock import MagicMock

        from src.bluetti_cli.bus import EventBus
        from src.bluetti_cli.device_handler import DeviceHandler

        bus = EventBus()
        handler = DeviceHandler("00:00:00:00:00:00", ac2a_device, 0, bus)

        mock_client = MagicMock()
        handler.client = mock_client
        mock_client.is_connected = True

        # execute() returns the already-stripped body (12 bytes for 6 regs)
        home_body = ac2a_home_bytes[:12]

        async def fake_execute(cmd):
            return home_body

        mock_client.execute = fake_execute

        received = []
        bus.add_parser_listener(lambda msg: received.append(msg))

        bus_task = asyncio.create_task(bus.run())
        await handler._poll_once()
        await asyncio.sleep(0.1)
        bus_task.cancel()

        assert len(received) > 0, "no ParserMessage dispatched"
        parsed = received[0].parsed
        # These should be real-looking values, not garbled by double-strip
        assert "packTotalSoc" in parsed
        assert parsed["packTotalSoc"] == 100
        assert 20 <= parsed["packTotalVoltage"] <= 40
        assert 0 <= parsed["packTotalCurrent"] <= 100


# ═══════════════════════════════════════════════════════════════════════
#  CLI unit tests (Click CliRunner)
# ═══════════════════════════════════════════════════════════════════════


class TestCli:
    def test_no_args_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Bluetti power station CLI" in result.output
        assert "status" in result.output
        assert "scan" in result.output
        assert "write" in result.output

    def test_help_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "bluetti-cli" in result.output

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.output
        assert "-v" in result.output
        assert "ADDRESS" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in result.output

    def test_write_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--help"])
        assert result.exit_code == 0
        assert "ADDRESS" in result.output
        assert "FIELD" in result.output
        assert "VALUE" in result.output


# ═══════════════════════════════════════════════════════════════════════
#  Load test
# ═══════════════════════════════════════════════════════════════════════



class TestEnergyComputation:
    def test_single_step(self):
        result = lt._compute_energy(100, 200, 3600, 0)
        assert result == pytest.approx(150.0)

    def test_zero_delta(self):
        result = lt._compute_energy(100, 200, 0, 50)
        assert result == pytest.approx(50.0)

    def test_accumulate_over_steps(self):
        e = lt._compute_energy(0, 100, 1800, 0)
        assert e == pytest.approx(25.0)
        e = lt._compute_energy(100, 200, 1800, e)
        assert e == pytest.approx(100.0)

    def test_zero_power(self):
        result = lt._compute_energy(0, 0, 3600, 10)
        assert result == pytest.approx(10.0)

    def test_small_delta(self):
        result = lt._compute_energy(50, 50, 30, 0)
        assert result == pytest.approx(50 * 30 / 3600)


class TestSocBar:
    def test_100_percent(self):
        bar = lt._soc_bar(100)
        assert "░" not in bar
        assert len(bar) == lt.SOC_BAR_WIDTH

    def test_0_percent(self):
        bar = lt._soc_bar(0)
        assert "█" not in bar
        assert len(bar) == lt.SOC_BAR_WIDTH

    def test_50_percent(self):
        bar = lt._soc_bar(50)
        assert bar.count("█") == lt.SOC_BAR_WIDTH // 2
        assert bar.count("░") == lt.SOC_BAR_WIDTH // 2

    def test_none_is_all_blank(self):
        bar = lt._soc_bar(None)
        assert bar == "░" * lt.SOC_BAR_WIDTH

    def test_negative_clamped(self):
        bar = lt._soc_bar(-10)
        assert bar == "░" * lt.SOC_BAR_WIDTH

    def test_over_100_clamped(self):
        bar = lt._soc_bar(110)
        assert bar == "█" * lt.SOC_BAR_WIDTH


class TestBuildSample:
    def test_all_fields_present(self):
        home = {
            "packTotalSoc": 85,
            "packTotalVoltage": Decimal("26.5"),
            "packTotalCurrent": Decimal("18.2"),
            "totalDCPower": 50,
            "totalACPower": 400,
            "totalPVPower": 0,
            "totalGridPower": 0,
            "packChargingStatus": 2,
            "packDsgEmptyTime": 200,
            "ambientTemp": 30,
            "invMaxTemp": 42,
            "totalDCEnergy": Decimal("1250.5"),
        }
        sample = lt._build_sample(home, 120.0, "test phase")
        assert sample["soc_pct"] == 85
        assert sample["pack_v"] == Decimal("26.5")
        assert sample["dc_power_w"] == 50
        assert sample["ac_power_w"] == 400
        assert sample["total_power_w"] == 450
        assert sample["elapsed_s"] == 120.0
        assert sample["charging_status"] == "Discharging"
        assert sample["phase"] == "test phase"

    def test_missing_fields_become_empty_strings(self):
        sample = lt._build_sample({}, 0)
        assert sample["soc_pct"] == ""
        assert sample["pack_v"] == ""
        assert sample["ambient_temp_c"] == ""
        assert sample["inv_temp_c"] == ""
        assert sample["est_remaining_min"] == ""
        assert sample["energy_register_wh"] == ""

    def test_power_defaults_to_zero(self):
        sample = lt._build_sample({}, 0)
        assert sample["dc_power_w"] == 0
        assert sample["ac_power_w"] == 0
        assert sample["total_power_w"] == 0

    def test_negative_ac_power_abs(self):
        sample = lt._build_sample({"totalACPower": -300}, 0)
        assert sample["ac_power_w"] == 300

    def test_phase_defaults_to_empty(self):
        sample = lt._build_sample({}, 0)
        assert sample["phase"] == ""


class TestPreRequisites:
    def test_all_clear(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 100,
            "totalGridPower": 0,
            "totalPVPower": 0,
        })
        assert warnings == []

    def test_soc_too_low(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 50,
            "totalGridPower": 0,
            "totalPVPower": 0,
        })
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_soc_missing(self):
        warnings = lt._check_prerequisites({
            "totalGridPower": 0,
            "totalPVPower": 0,
        })
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_grid_too_high(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 100,
            "totalGridPower": 200,
            "totalPVPower": 0,
        })
        assert len(warnings) == 1
        assert "Grid" in warnings[0]

    def test_grid_just_under_limit(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 100,
            "totalGridPower": 5,
            "totalPVPower": 0,
        })
        assert warnings == []

    def test_pv_too_high(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 100,
            "totalGridPower": 0,
            "totalPVPower": 20,
        })
        assert len(warnings) == 1
        assert "PV" in warnings[0]

    def test_multiple_warnings(self):
        warnings = lt._check_prerequisites({
            "packTotalSoc": 40,
            "totalGridPower": 100,
            "totalPVPower": 30,
        })
        assert len(warnings) == 3


class TestRuntimeWarnings:
    def test_no_warnings(self):
        assert lt._check_warnings({"grid_power_w": 0, "pv_power_w": 0}) == []

    def test_grid_above_threshold(self):
        warnings = lt._check_warnings({"grid_power_w": 15, "pv_power_w": 0})
        assert len(warnings) == 1
        assert "Grid" in warnings[0]

    def test_pv_above_threshold(self):
        warnings = lt._check_warnings({"grid_power_w": 0, "pv_power_w": 20})
        assert len(warnings) == 1
        assert "PV" in warnings[0]

    def test_grid_at_threshold_ok(self):
        assert lt._check_warnings({"grid_power_w": 10, "pv_power_w": 0}) == []

    def test_pv_at_threshold_ok(self):
        assert lt._check_warnings({"grid_power_w": 0, "pv_power_w": 10}) == []

    def test_both_above(self):
        warnings = lt._check_warnings({"grid_power_w": 50, "pv_power_w": 100})
        assert len(warnings) == 2

    def test_missing_keys_no_warning(self):
        assert lt._check_warnings({}) == []


class TestCSVHeader:
    def test_header_has_required_columns(self):
        assert "timestamp" in lt.CSV_COLUMNS
        assert "elapsed_s" in lt.CSV_COLUMNS
        assert "soc_pct" in lt.CSV_COLUMNS
        assert "pack_v" in lt.CSV_COLUMNS
        assert "energy_computed_wh" in lt.CSV_COLUMNS
        assert "energy_register_wh" in lt.CSV_COLUMNS
        assert "phase" in lt.CSV_COLUMNS

    def test_csv_columns_count(self):
        assert len(lt.CSV_COLUMNS) == 17

    def test_header_comment_block(self, ac2a_device):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_header(writer, ac2a_device, "test", 100, 60)
        content = buf.getvalue()
        assert "# bluetti-cli load test" in content
        assert "# Device: AC2A-TEST" in content
        assert "# Phase: test" in content
        assert "# Expected load: 100 W" in content
        assert "# Interval: 60 s" in content
        assert "timestamp,elapsed_s" in content

    def test_header_without_optional_fields(self, ac2a_device):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_header(writer, ac2a_device, None, None, 60)
        content = buf.getvalue()
        assert "# Phase" not in content
        assert "# Expected load" not in content

    def test_csv_row_writes_all_columns(self):
        buf = StringIO()
        writer = csv.writer(buf)
        data = {col: f"val_{col}" for col in lt.CSV_COLUMNS}
        lt._write_csv_row(writer, data)
        content = buf.getvalue().strip()
        assert content.count(",") == len(lt.CSV_COLUMNS) - 1

    def test_csv_row_empty_for_missing_fields(self):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_row(writer, {"timestamp": "2026-01-01T00:00:00"})
        content = buf.getvalue().strip()
        values = content.split(",")
        assert values[0] == "2026-01-01T00:00:00"
        assert all(v == "" for v in values[1:])

    def test_csv_row_decimal_handling(self):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_row(writer, {"pack_v": Decimal("27.3"), "timestamp": "t"})
        content = buf.getvalue().strip()
        values = content.split(",")
        assert values[lt.CSV_COLUMNS.index("pack_v")] == "27.3"


class TestLoadTestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["load-test", "--help"])
        assert result.exit_code == 0
        assert "load" in result.output.lower()
        assert "--interval" in result.output
        assert "--output" in result.output
        assert "--expected-load" in result.output
        assert "--phase" in result.output
        assert "ADDRESS" in result.output

    def test_rejects_short_interval(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "load-test", "AA:BB:CC:DD:EE:FF", "--interval", "5",
        ])
        assert result.exit_code != 0
        assert "15" in result.output


# ═══════════════════════════════════════════════════════════════════════
#  CSV analysis (post-test)
# ═══════════════════════════════════════════════════════════════════════


class TestCsvAnalysis:
    _BASIC_CSV = (
        "# bluetti-cli load test\n"
        "# Device: AC2A-TEST\n"
        "#\n"
        "timestamp,elapsed_s,soc_pct,pack_v,pack_a,total_power_w,energy_computed_wh,energy_register_wh,est_remaining_min,ambient_temp_c,inv_temp_c\n"
        "2026-01-01T00:00:00,0,100,27.0,0,0,0,1000.0,500,25,30\n"
        "2026-01-01T00:01:00,60,99,26.9,18,500,8.3,1008.3,490,26,31\n"
        "2026-01-01T00:02:00,120,98,26.8,18,500,16.7,1016.7,480,27,32\n"
        "2026-01-01T00:03:00,180,97,26.7,18,500,25.0,1025.0,470,28,33\n"
        "2026-01-01T00:04:00,240,96,26.6,18,500,33.3,1033.3,460,29,34\n"
    )

    def _write_csv(self, tmp_path, content=_BASIC_CSV):
        path = tmp_path / "test.csv"
        path.write_text(content)
        return str(path)

    def test_returns_none_for_short_csv(self, tmp_path):
        path = self._write_csv(tmp_path, "a,b\n1,2\n3,4\n5,6\n")
        assert lt._analyze_csv(path) is None

    def test_capacity_is_last_energy_computed(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["capacity_wh"] == pytest.approx(33.3)

    def test_register_delta(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["register_delta_wh"] == pytest.approx(1033.3 - 1000.0)

    def test_avg_and_peak_load(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["avg_load_w"] == pytest.approx(400)  # (0+500+500+500+500)/5
        assert result["peak_load_w"] == pytest.approx(500)

    def test_efficiency(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        # pack power: 0*0=0, 26.9*18=484.2, 26.8*18=482.4, 26.7*18=480.6, 26.6*18=478.8
        # avg pack = 385.2, avg out = 400, eff = 400/385.2*100 ≈ 103.8
        assert result["efficiency_pct"] is not None
        assert result["efficiency_pct"] > 0

    def test_voltage_at_soc_milestones(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        v = result["voltage_at_soc"]
        assert "100%" in v
        assert v["100%"] == pytest.approx(27.0)
        # 96% SOC is the lowest we have, should be recorded at some milestone
        assert v.get("75%") is None  # never reached 75%

    def test_bms_accuracy_at_50pct(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        # SOC never drops to 50% in this data, so no BMS accuracy
        assert result["bms_accuracy"] is None

    def test_bms_with_crossing_50(self, tmp_path):
        content = (
            "# test\n"
            "timestamp,elapsed_s,soc_pct,total_power_w,est_remaining_min,energy_computed_wh\n"
            "t0,0,100,0,600,0\n"
            "t1,600,60,500,300,100\n"
            "t2,1200,55,500,290,200\n"
            "t3,1800,49,500,240,300\n"
            "t4,2400,45,500,200,400\n"
            "t5,3000,0,500,0,500\n"
        )
        path = self._write_csv(tmp_path, content)
        result = lt._analyze_csv(path)
        # First row with SOC ≤ 50 is t3 (49%)
        assert result["bms_accuracy"] == pytest.approx(240)
        # total runtime = 3000s, t3 elapsed = 1800s, remaining = 1200s = 20 min
        assert result["actual_remaining_at_50pct"] == pytest.approx(20.0)

    def test_max_temperatures(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["max_ambient_c"] == 29
        assert result["max_inverter_c"] == 34

    def test_missing_optional_columns(self, tmp_path):
        content = (
            "# test\n"
            "timestamp,elapsed_s,soc_pct,total_power_w,energy_computed_wh\n"
            "t0,0,100,0,0\n"
            "t1,60,99,500,8.3\n"
            "t2,120,98,500,16.7\n"
            "t3,180,97,500,25.0\n"
            "t4,240,96,500,33.3\n"
            "t5,300,0,500,50.0\n"
        )
        path = self._write_csv(tmp_path, content)
        result = lt._analyze_csv(path)
        assert result["capacity_wh"] == pytest.approx(50.0)
        assert result["register_delta_wh"] is None
        assert result["efficiency_pct"] is None
        assert result["voltage_at_soc"] == {}
        assert result["bms_accuracy"] is None
        assert result["max_ambient_c"] is None


# ═══════════════════════════════════════════════════════════════════════
#  Systemd service generation
# ═══════════════════════════════════════════════════════════════════════


class TestMqttPublishService:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish-service", "--help"])
        assert result.exit_code == 0
        assert "--broker" in result.output
        assert "--user" in result.output
        assert "--port" in result.output
        assert "--output" in result.output
        assert "ADDRESS" in result.output

    def test_missing_broker_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish-service", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code != 0
        assert "broker" in result.output.lower()

    def test_generates_service_sections(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "192.168.1.100",
        ])
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "WantedBy=multi-user.target" in output
        assert "Restart=always" in output

    def test_exec_start_contains_address_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "10.0.0.1",
        ])
        assert result.exit_code == 0
        assert "AA:BB:CC:DD:EE:FF" in result.output
        assert "--broker 10.0.0.1" in result.output

    def test_respects_user_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--user", "root",
        ])
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_port_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--port", "8883",
        ])
        assert result.exit_code == 0
        assert "--port 8883" in result.output

    def test_respects_interval_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--interval", "30",
        ])
        assert result.exit_code == 0
        assert "--interval 30" in result.output

    def test_respects_username_password(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--username", "mqttuser", "--password", "s3cret",
        ])
        assert result.exit_code == 0
        assert "--username mqttuser" in result.output
        assert "--password 's3cret'" in result.output

    def test_respects_ha_config(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--ha-config", "none",
        ])
        assert result.exit_code == 0
        assert "--ha-config none" in result.output

    def test_output_to_file(self, tmp_path):
        out = tmp_path / "test.service"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--output", str(out),
        ])
        assert result.exit_code == 0
        content = out.read_text()
        assert "[Unit]" in content
        assert "[Service]" in content

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_exec_override(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--exec", "/usr/local/bin/bluetti-cli",
        ])
        assert result.exit_code == 0
        assert "ExecStart=/usr/local/bin/bluetti-cli" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_restart_always_in_service(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "Restart=always" in result.output

    def test_restart_flag_in_mqtt_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish", "--help"])
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_publish_service_includes_serial(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-publish-service", "AA:BB:CC:DD:EE:FF", "--broker", "x",
            "--serial", "MYSERIAL",
        ])
        assert result.exit_code == 0
        assert "--serial MYSERIAL" in result.output


# ═══════════════════════════════════════════════════════════════════════
#  Source change watcher
# ═══════════════════════════════════════════════════════════════════════


class TestSourceChangeWatcher:
    def test_watcher_event_set_on_py_modify(self, tmp_path):
        (tmp_path / "mod.py").touch()
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        try:
            (tmp_path / "mod.py").write_text("x = 1")
            time.sleep(0.3)
            assert watcher.changed.is_set()
        finally:
            watcher.stop()

    def test_watcher_event_not_set_on_non_py(self, tmp_path):
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        try:
            (tmp_path / "notes.txt").write_text("hello")
            time.sleep(0.3)
            assert not watcher.changed.is_set()
        finally:
            watcher.stop()

    def test_watcher_start_stop(self, tmp_path):
        watcher = SourceChangeWatcher(tmp_path)
        watcher.start()
        watcher.stop()  # should not raise

    def test_watch_coroutine_exits_on_event(self):
        watcher = SourceChangeWatcher(Path("/tmp"))
        watcher.changed.set()
        import pytest
        with pytest.raises(SystemExit) as exc:
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                _watch_source_changes(watcher)
            )
        assert exc.value.code == 0

    def test_watch_coroutine_does_not_exit_without_event(self):
        watcher = SourceChangeWatcher(Path("/tmp"))
        async def run():
            try:
                await asyncio.wait_for(_watch_source_changes(watcher), timeout=0.2)
            except asyncio.TimeoutError:
                pass  # expected — coroutine didn't exit
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(run())


# ═══════════════════════════════════════════════════════════════════════
#  Shutdown watch latch logic
# ═══════════════════════════════════════════════════════════════════════


class TestShutdownWatch:
    def test_no_latch_above_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        assert w.handle_soc(50) is None
        assert not w.latched

    def test_no_latch_at_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        assert w.handle_soc(10) is None
        assert not w.latched

    def test_latch_below_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        cmd = w.handle_soc(5)
        assert cmd is None  # grace period hasn't expired yet
        assert w.latched
        assert w.fire_at is not None
        assert w.time_remaining > 0

    def test_latch_stays_set_on_recovery(self):
        w = ShutdownWatch(threshold=10, grace=60)
        w.handle_soc(5)
        assert w.latched
        w.handle_soc(80)
        assert w.latched  # still latched

    def test_grace_timer_shutdown_after_expiry(self):
        w = ShutdownWatch(threshold=10, grace=0)
        cmd = w.handle_soc(5)
        assert cmd == "sudo shutdown -h now"

    def test_grace_timer_not_expired(self):
        w = ShutdownWatch(threshold=10, grace=999)
        cmd = w.handle_soc(5)
        assert cmd is None
        assert w.time_remaining > 0

    def test_latch_triggers_recovery_log(self, caplog):
        import logging
        w = ShutdownWatch(threshold=10, grace=60)
        with caplog.at_level(logging.INFO):
            w.handle_soc(5)
            w.handle_soc(50)
        assert "shutdown already triggered" in caplog.text


# ═══════════════════════════════════════════════════════════════════════
#  mqtt-listen CLI
# ═══════════════════════════════════════════════════════════════════════


class TestMqttListenCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output
        assert "--broker" in result.output
        assert "--shutdown-at" in result.output
        assert "--grace-period" in result.output

    def test_requires_broker(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--serial", "12345"])
        assert result.exit_code != 0

    def test_requires_address_or_serial(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--broker", "x"])
        assert result.exit_code != 0
        assert "ADDRESS" in result.output or "serial" in result.output.lower()

    def test_default_shutdown_at(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--help"])
        assert "10" in result.output


# ═══════════════════════════════════════════════════════════════════════
#  mqtt-listen-service output
# ═══════════════════════════════════════════════════════════════════════


class TestMqttListenService:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen-service", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output
        assert "--shutdown-at" in result.output

    def test_generates_service_sections(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "12345", "--broker", "192.168.1.100",
        ])
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "Restart=always" in output

    def test_execstart_has_serial_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "SN123", "--broker", "10.0.0.1",
        ])
        assert result.exit_code == 0
        assert "--serial SN123" in result.output
        assert "--broker 10.0.0.1" in result.output
        assert "mqtt-listen" in result.output

    def test_user_is_root_by_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "x", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_shutdown_at(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "x", "--broker", "x",
            "--shutdown-at", "20",
        ])
        assert result.exit_code == 0
        assert "--shutdown-at 20" in result.output

    def test_respects_grace_period(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "x", "--broker", "x",
            "--grace-period", "120",
        ])
        assert result.exit_code == 0
        assert "--grace-period 120" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "x", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "x", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_service_name_uses_serial(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--serial", "DEADBEEF", "--broker", "x",
        ])
        assert result.exit_code == 0
        assert "bluetti-shutdown-DEADBEEF" in result.output

    def test_no_address_argument(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "mqtt-listen-service", "--help",
        ])
        assert result.exit_code == 0
        assert "ADDRESS" not in result.output
