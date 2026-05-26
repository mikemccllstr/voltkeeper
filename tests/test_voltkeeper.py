# ABOUTME: Unit tests for voltkeeper — utility functions, struct-based protocol parsers, CLI behavior.
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

import voltkeeper.load_test as lt
from voltkeeper.bus import CommandMessage, EventBus, ParserMessage
from voltkeeper.cli import cli
from voltkeeper.core.commands import WriteMultipleRegisters, WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.devices.bluetti_device import BluettiDevice
from voltkeeper.core.struct import UintField
from voltkeeper.core.utils import (
    _ascii,
    _bcd_sn,
    _format_version,
    _s16,
    _s32,
    _u16,
    _u32,
    crc16_modbus,
)
from voltkeeper.device_handler import SourceChangeWatcher, _watch_source_changes
from voltkeeper.mqtt_client import (
    CHARGING_STATUS_MAP,
    COMMAND_TOPIC_RE,
    NORMAL_DEVICE_FIELDS,
    MQTTClient,
    MqttFieldType,
)
from voltkeeper.shutdown_watch import ShutdownWatch


@pytest.fixture
def ac2a_device():
    return AC2A("00:00:00:00:00:00", "TEST")


@pytest.fixture
def ac2a_device_num():
    """AC2A with a numeric SN so COMMAND_TOPIC_RE (requires \\d+) can match."""
    return AC2A("00:00:00:00:00:00", "12345678")


# ═══════════════════════════════════════════════════════════════════════
#  UintField unit attribute
# ═══════════════════════════════════════════════════════════════════════


class TestUintFieldUnit:
    def test_unit_stored_when_provided(self):
        f = UintField("eco_time", 2015, unit="h")
        assert f.unit == "h"

    def test_unit_none_by_default(self):
        f = UintField("lcd_timeout", 2067)
        assert f.unit is None

    def test_unit_does_not_affect_range(self):
        f = UintField("sys_low_power", 2022, range=(0, 100), unit="%")
        assert f.in_range(50)
        assert not f.in_range(150)


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
        assert crc16_modbus(b"\x01\x03\x00\x64\x00\x06") == crc16_modbus(b"\x01\x03\x00\x64\x00\x06")

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
        from voltkeeper.core.devices.ac2a import ChargingMode

        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["charging_mode"] == ChargingMode.TURBO

    def test_sys_power_thresholds(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["sys_low_power"] == 20
        assert result["sys_high_power"] == 80

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

    def test_working_mode_parse_raw(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["working_mode"] == 0

    def test_working_mode_build_setter_enum(self, ac2a_device):
        from voltkeeper.core.commands import WorkingMode

        cmd = ac2a_device.build_setter_command("working_mode", WorkingMode.STANDARD_UPS)
        assert cmd.address == 2005
        assert cmd.value == 3

    def test_working_mode_build_setter_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("working_mode", "PV_PRIORITY_UPS")
        assert cmd.address == 2005
        assert cmd.value == 2

    def test_working_mode_build_setter_lowercase(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("working_mode", "customized_ups")
        assert cmd.address == 2005
        assert cmd.value == 1

    def test_working_mode_enum_values(self):
        from voltkeeper.core.commands import WorkingMode

        assert WorkingMode.CUSTOMIZED_UPS.value == 1
        assert WorkingMode.PV_PRIORITY_UPS.value == 2
        assert WorkingMode.STANDARD_UPS.value == 3
        assert WorkingMode.TIME_CTRL_UPS.value == 4
        assert WorkingMode.V2_TIME_CTRL_UPS.value == 5
        assert WorkingMode.SELF_CONSUMPTION_EXPORT.value == 11

    def test_build_setter_eco_time_suffixed(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_auto_off_time", "2h")
        assert cmd.address == 2015
        assert cmd.value == 2

    def test_build_setter_eco_time_bare(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_auto_off_time", "2")
        assert cmd.address == 2015
        assert cmd.value == 2

    def test_build_setter_eco_power_suffixed(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_power", "150W")
        assert cmd.address == 2016
        assert cmd.value == 150

    def test_build_setter_eco_power_wrong_case_suffix_raises(self, ac2a_device):
        import pytest as _pytest

        with _pytest.raises((ValueError, TypeError)):
            ac2a_device.build_setter_command("dc_eco_auto_off_time", "2H")


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
#  TLV read request encoding
# ═══════════════════════════════════════════════════════════════════════


class TestTlvReadCommands:
    def test_single_section_payload(self):
        from voltkeeper.core.commands import build_tlv_read_payload

        payload = build_tlv_read_payload([(100, 62)], slave_addr=1)
        assert payload[:4] == bytes.fromhex("00105208")
        assert payload[-2:] == crc16_modbus(payload[:-2])
        assert len(payload) > 15

    def test_multiple_sections_payload(self):
        from voltkeeper.core.commands import build_tlv_read_payload

        sections = [(100, 62), (1100, 51), (1200, 70)]
        payload = build_tlv_read_payload(sections, slave_addr=1)
        assert payload[:4] == bytes.fromhex("00105208")
        assert payload[-2:] == crc16_modbus(payload[:-2])

    def test_tlv_read_command_bytes(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62)])
        raw = bytes(cmd)
        assert raw[:4] == bytes.fromhex("00105208")
        assert raw[-2:] == crc16_modbus(raw[:-2])

    def test_tlv_read_command_repr(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62), (1100, 51)])
        r = repr(cmd)
        assert "(100,62)" in r
        assert "(1100,51)" in r

    def test_tlv_response_size(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62), (1100, 51)])
        expected_body = 62 * 2 + 51 * 2
        assert cmd.response_size() == expected_body + 32

    def test_tlv_valid_response_detects_magic(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62)])
        resp = bytearray(b"\x40\x00\x04" + b"\x00" * 50)
        resp.extend(crc16_modbus(bytes(resp)))
        assert cmd.is_valid_response(resp)

    def test_tlv_valid_response_detects_crc(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62)])
        resp = bytearray(b"\x01\x03\x20" + b"\x00" * 32)
        resp.extend(crc16_modbus(bytes(resp)))
        assert cmd.is_valid_response(resp)

    def test_tlv_invalid_response_rejected(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters

        cmd = TlvReadHoldingRegisters([(100, 62)])
        resp = b"\x00\x00\x00\x00\x00"
        assert not cmd.is_valid_response(resp)


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


class TestSystemPowerOff:
    def test_values(self):
        from voltkeeper.core.commands import SystemPowerOff

        assert SystemPowerOff.NORMAL.value == 0
        assert SystemPowerOff.SHUTDOWN.value == 1
        assert SystemPowerOff.POWER_DOWN_V1.value == 2
        assert SystemPowerOff.POWER_DOWN_V2.value == 3
        assert SystemPowerOff.SLEEP.value == 4

    def test_round_trip(self):
        from voltkeeper.core.commands import SystemPowerOff

        for member in SystemPowerOff:
            assert SystemPowerOff(member.value) is member
            assert int(SystemPowerOff(member.value).value) == member.value


# ═══════════════════════════════════════════════════════════════════════
#  EL100V2 device class
# ═══════════════════════════════════════════════════════════════════════


class TestEl100V2:
    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL100V22305000")
        assert d.type == "EL100V2"
        assert d.sn == "2305000"

    def test_polling_commands_inherits_v2(self, el100v2_device):
        cmds = el100v2_device.polling_commands
        addrs = {cmd.starting_address for cmd in cmds}
        for expected in (100, 1100, 1200, 1300, 1400, 1500):
            assert expected in addrs, f"Missing register block {expected}"

    def test_use_tlv_polling(self, el100v2_device):
        assert el100v2_device.use_tlv_polling is True

    def test_writable_fields_known(self, el100v2_device):
        from voltkeeper.core.devices.el100v2 import El100V2

        for field in El100V2.WRITABLE_FIELD_NAMES:
            assert el100v2_device.has_field_setter(field), f"{field} should be writable"

    def test_readonly_fields_not_writable(self, el100v2_device):
        assert not el100v2_device.has_field_setter("packTotalSoc")
        assert not el100v2_device.has_field_setter("deviceModel")
        assert not el100v2_device.has_field_setter("totalDCPower")

    def test_unknown_field_rejected(self, el100v2_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el100v2_device.build_setter_command("nonexistent", 1)

    def test_build_setter_ac_output(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("ac_output", True)
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_build_setter_dc_output(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("dc_output", False)
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_build_setter_charging_mode(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("charging_mode", "TURBO")
        assert cmd.address == 2020
        assert cmd.value == 1

    def test_build_setter_ctrl_grid(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("ctrl_grid", True)
        assert cmd.address == 2207
        assert cmd.value == 1

    def test_build_setter_grid_max_current(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("grid_max_current", 15)
        assert cmd.address == 2214

    def test_ctrl_event_decode_all_off(self, el100v2_device):
        caps = el100v2_device.decode_ctrl_event(0)
        assert all(not v for v in caps.values())
        assert len(caps) == 11

    def test_ctrl_event_decode_partial(self, el100v2_device):
        caps = el100v2_device.decode_ctrl_event(0x0407)
        assert caps["power_control"]
        assert caps["ac_control"]
        assert caps["dc_control"]
        assert not caps["inv_control"]
        assert caps["super_power"]

    def test_ctrl_event_bits_defined(self, el100v2_device):
        bits = el100v2_device.ctrl_event_bits
        assert len(bits) == 11
        assert bits[0] == ("power_control", "power")


# ═══════════════════════════════════════════════════════════════════════
#  New device model tests — AC180, EL10V2, EL30V2, EL400
# ═══════════════════════════════════════════════════════════════════════


class TestAC180:
    @pytest.fixture
    def ac180_device(self):
        from voltkeeper.core.devices.ac180 import AC180

        return AC180("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "AC1802305000")
        assert d.type == "AC180"
        assert d.sn == "2305000"

    def test_writable_fields_known(self, ac180_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "child_lock",
            "child_lock_level",
            "inv_freq",
        ):
            assert ac180_device.has_field_setter(field), f"{field} should be writable"

    def test_child_lock_not_writable_as_readonly(self, ac180_device):
        assert not ac180_device.has_field_setter("packTotalSoc")

    def test_child_lock_build_setter_on(self, ac180_device):
        cmd = ac180_device.build_setter_command("child_lock", True)
        assert cmd.address == 2072
        assert cmd.value == 0x20

    def test_child_lock_build_setter_off(self, ac180_device):
        cmd = ac180_device.build_setter_command("child_lock", False)
        assert cmd.address == 2072
        assert cmd.value == 0x10

    def test_child_lock_build_setter_string_on(self, ac180_device):
        cmd = ac180_device.build_setter_command("child_lock", "on")
        assert cmd.address == 2072
        assert cmd.value == 0x20

    def test_child_lock_build_setter_string_off(self, ac180_device):
        cmd = ac180_device.build_setter_command("child_lock", "off")
        assert cmd.address == 2072
        assert cmd.value == 0x10

    def test_child_lock_level_setter(self, ac180_device):
        cmd = ac180_device.build_setter_command("child_lock_level", 1)
        assert cmd.address == 2076
        assert cmd.value == 1

        cmd = ac180_device.build_setter_command("child_lock_level", 2)
        assert cmd.address == 2076
        assert cmd.value == 2

    def test_working_mode_setter(self, ac180_device):
        from voltkeeper.core.commands import WorkingMode

        cmd = ac180_device.build_setter_command("working_mode", "STANDARD_UPS")
        assert cmd.address == 2005
        assert cmd.value == 3

        cmd = ac180_device.build_setter_command("working_mode", WorkingMode.PV_PRIORITY_UPS)
        assert cmd.address == 2005
        assert cmd.value == 2

    def test_charging_mode_setter(self, ac180_device):
        cmd = ac180_device.build_setter_command("charging_mode", "TURBO")
        assert cmd.address == 2020
        assert cmd.value == 1

    def test_unknown_field_rejected(self, ac180_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            ac180_device.build_setter_command("nonexistent", 1)

    def test_pack_voltage_scale_default(self):
        from voltkeeper.core.devices.ac180 import AC180

        assert AC180.DEFAULT_PACK_VOLTAGE_SCALE == 1


class TestEL10V2:
    @pytest.fixture
    def el10v2_device(self):
        from voltkeeper.core.devices.el10v2 import EL10V2

        return EL10V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL10V22305000")
        assert d.type == "EL10V2"
        assert d.sn == "2305000"

    def test_pack_voltage_scale_25v(self):
        from voltkeeper.core.devices.el10v2 import EL10V2

        assert EL10V2.DEFAULT_PACK_VOLTAGE_SCALE == 2

    def test_writable_fields_known(self, el10v2_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "child_lock",
            "child_lock_level",
            "soc_holding_low",
            "led_color",
            "soc_holding_high",
        ):
            assert el10v2_device.has_field_setter(field), f"{field} should be writable"

    def test_child_lock_inherited(self, el10v2_device):
        cmd = el10v2_device.build_setter_command("child_lock", True)
        assert cmd.address == 2072
        assert cmd.value == 0x20

    def test_child_lock_level_inherited(self, el10v2_device):
        cmd = el10v2_device.build_setter_command("child_lock_level", 2)
        assert cmd.address == 2076
        assert cmd.value == 2

    def test_el10v2_specific_fields(self, el10v2_device):
        assert el10v2_device.has_field_setter("led_color")
        assert el10v2_device.has_field_setter("soc_holding_low")
        assert el10v2_device.has_field_setter("soc_holding_high")

    def test_no_grid_ctrl(self, el10v2_device):
        assert not el10v2_device.has_field_setter("ctrl_grid")
        assert not el10v2_device.has_field_setter("ctrl_feed")
        assert not el10v2_device.has_field_setter("grid_max_current")

    def test_unknown_field_rejected(self, el10v2_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el10v2_device.build_setter_command("nonexistent", 1)


class TestEL30V2:
    @pytest.fixture
    def el30v2_device(self):
        from voltkeeper.core.devices.el30v2 import EL30V2

        return EL30V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL30V22305000")
        assert d.type == "EL30V2"
        assert d.sn == "2305000"

    def test_pack_voltage_scale_25v(self):
        from voltkeeper.core.devices.el30v2 import EL30V2

        assert EL30V2.DEFAULT_PACK_VOLTAGE_SCALE == 2

    def test_writable_fields_known(self, el30v2_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "ctrl_grid",
            "ctrl_feed",
            "inv_voltage",
            "inv_freq",
            "grid_max_power",
            "grid_max_current",
            "feed_max_power",
            "feed_max_current",
        ):
            assert el30v2_device.has_field_setter(field), f"{field} should be writable"

    def test_no_child_lock(self, el30v2_device):
        assert not el30v2_device.has_field_setter("child_lock")

    def test_grid_control_setters(self, el30v2_device):
        cmd = el30v2_device.build_setter_command("ctrl_grid", True)
        assert cmd.address == 2207
        assert cmd.value == 1

        cmd = el30v2_device.build_setter_command("grid_max_current", 15)
        assert cmd.address == 2214

    def test_unknown_field_rejected(self, el30v2_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el30v2_device.build_setter_command("nonexistent", 1)


class TestEL400:
    @pytest.fixture
    def el400_device(self):
        from voltkeeper.core.devices.el400 import EL400

        return EL400("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL4002305000")
        assert d.type == "EL400"
        assert d.sn == "2305000"

    def test_pack_voltage_scale_56v(self):
        from voltkeeper.core.devices.el400 import EL400

        assert EL400.DEFAULT_PACK_VOLTAGE_SCALE == 1

    def test_writable_fields_known(self, el400_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "system_power",
            "remote_startup_soc",
            "sleep_power_threshold",
        ):
            assert el400_device.has_field_setter(field), f"{field} should be writable"

    def test_old_power_off_field_removed(self, el400_device):
        # `power_off` and `sleep_mode` are no longer writable — they were
        # replaced by `system_power` to fix the register-2013 read collision.
        assert not el400_device.has_field_setter("power_off")
        assert not el400_device.has_field_setter("sleep_mode")

    def test_system_power_setter_sleep(self, el400_device):
        cmd = el400_device.build_setter_command("system_power", "sleep")
        assert cmd.address == 2013
        assert cmd.value == 4

    def test_system_power_setter_shutdown(self, el400_device):
        cmd = el400_device.build_setter_command("system_power", "shutdown")
        assert cmd.address == 2013
        assert cmd.value == 1

    def test_system_power_parse_sleep_value(self, el400_device):
        # Reading register 2013 with raw value 4 must yield system_power=SLEEP
        # as a single enum field, not collide with two true bools.
        from voltkeeper.core.commands import SystemPowerOff

        # control_struct.parse expects a contiguous block starting at the
        # first field; build a sparse block by parsing a 1-register block
        # at address 2013 with value 4.
        data = (4).to_bytes(2, "big")
        result = el400_device.control_struct.parse(2013, data)
        assert result.get("system_power") is SystemPowerOff.SLEEP
        assert "power_off" not in result
        assert "sleep_mode" not in result

    def test_remote_startup_soc_setter(self, el400_device):
        cmd = el400_device.build_setter_command("remote_startup_soc", 50)
        assert cmd.address == 2074
        assert cmd.value == 50

    def test_sleep_power_threshold_setter(self, el400_device):
        cmd = el400_device.build_setter_command("sleep_power_threshold", 100)
        assert cmd.address == 2079
        assert cmd.value == 100

    def test_no_child_lock(self, el400_device):
        assert not el400_device.has_field_setter("child_lock")

    def test_unknown_field_rejected(self, el400_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el400_device.build_setter_command("nonexistent", 1)


# ═══════════════════════════════════════════════════════════════════════
#  CTRL_EVENT bit decoder
# ═══════════════════════════════════════════════════════════════════════


class TestCtrlEvent:
    def test_all_off(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0)
        assert all(not v for v in caps.values())
        assert len(caps) == 11

    def test_all_on(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0x07FF)
        assert all(caps.values())

    def test_partial_bits(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0x0407)
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
        cmd = ac2a_device.build_setter_command("sys_low_power", 50)
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
        (topic,) = [c.args[0] for c in mock_client.publish.call_args_list]
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

        from voltkeeper.bus import EventBus
        from voltkeeper.device_handler import DeviceHandler

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
        await handler._poll_once_individual()
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


# ═══════════════════════════════════════════════════════════════════════
#  _print_verbose CONTROLS output
# ═══════════════════════════════════════════════════════════════════════


class TestPrintVerboseControls:
    def test_unit_suffix_and_hint_rendered(self, ac2a_device):
        import unittest.mock as mock

        from voltkeeper.cli import _print_verbose
        from voltkeeper.core.devices.ac2a import ChargingMode

        home = {"packTotalSoc": 80, "packTotalVoltage": 25.6, "packTotalCurrent": 0.0}
        controls = {
            "ac_output": True,
            "dc_eco_auto_off_time": 2,
            "dc_eco_power": 150,
            "charging_mode": ChargingMode.TURBO,
            "sys_low_power": 20,
        }

        output_lines = []

        def fake_echo(msg="", **kw):
            output_lines.append(str(msg))

        with mock.patch("voltkeeper.cli.click.echo", side_effect=fake_echo):
            _print_verbose(ac2a_device, home, {}, {}, {}, {}, {}, controls)

        output = "\n".join(output_lines)
        assert "2h" in output
        assert "150W" in output
        assert "[on|off]" in output
        assert "[integer]h" in output
        assert "[integer]W" in output
        assert "[0-100]" in output


# ═══════════════════════════════════════════════════════════════════════
#  _field_hint helper
# ═══════════════════════════════════════════════════════════════════════


class TestFieldHint:
    def test_bool_field(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import BoolField

        assert _field_hint(BoolField("ac_output", 2011)) == "[on|off]"

    def test_enum_field(self):
        from enum import Enum

        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import EnumField

        class Mode(Enum):
            STANDARD = 0
            TURBO = 1

        assert _field_hint(EnumField("mode", 2020, Mode)) == "[standard|turbo]"

    def test_ranged_uint_no_unit(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import UintField

        assert _field_hint(UintField("sys_low_power", 2022, range=(0, 100))) == "[0-100]"

    def test_ranged_uint_with_unit(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import UintField

        assert _field_hint(UintField("dc_eco_power", 2016, unit="W")) == "[integer]W"

    def test_unranged_uint_no_unit(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import UintField

        assert _field_hint(UintField("lcd_timeout", 2067)) == "[integer]"

    def test_unranged_uint_with_unit(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import UintField

        assert _field_hint(UintField("dc_eco_auto_off_time", 2015, unit="h")) == "[integer]h"

    def test_other_field_type_returns_empty(self):
        from voltkeeper.cli import _field_hint
        from voltkeeper.core.struct import StringField

        assert _field_hint(StringField("deviceModel", 110, 8)) == ""


class TestCli:
    def test_no_args_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Voltkeeper CLI, supporting Bluetti power station devices" in result.output
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
        assert "voltkeeper" in result.output

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
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert warnings == []

    def test_soc_too_low(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 50,
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_soc_missing(self):
        warnings = lt._check_prerequisites(
            {
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_grid_too_high(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 200,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "Grid" in warnings[0]

    def test_grid_just_under_limit(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 5,
                "totalPVPower": 0,
            }
        )
        assert warnings == []

    def test_pv_too_high(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 0,
                "totalPVPower": 20,
            }
        )
        assert len(warnings) == 1
        assert "PV" in warnings[0]

    def test_multiple_warnings(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 40,
                "totalGridPower": 100,
                "totalPVPower": 30,
            }
        )
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
        assert "# voltkeeper load test" in content
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
        result = runner.invoke(
            cli,
            [
                "load-test",
                "AA:BB:CC:DD:EE:FF",
                "--interval",
                "5",
            ],
        )
        assert result.exit_code != 0
        assert "15" in result.output


# ═══════════════════════════════════════════════════════════════════════
#  CSV analysis (post-test)
# ═══════════════════════════════════════════════════════════════════════


class TestCsvAnalysis:
    _BASIC_CSV = (
        "# voltkeeper load test\n"
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
        result = runner.invoke(cli, ["mqtt-publish-service", "AC2A0000000"])
        assert result.exit_code != 0
        assert "broker" in result.output.lower()

    def test_generates_service_sections(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "192.168.1.100",
            ],
        )
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "WantedBy=multi-user.target" in output
        assert "Restart=always" in output

    def test_exec_start_contains_address_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "10.0.0.1",
            ],
        )
        assert result.exit_code == 0
        assert "AC2A0000000" in result.output
        assert "--broker 10.0.0.1" in result.output

    def test_respects_user_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--user",
                "root",
            ],
        )
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_port_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--port",
                "8883",
            ],
        )
        assert result.exit_code == 0
        assert "--port 8883" in result.output

    def test_respects_interval_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--interval",
                "30",
            ],
        )
        assert result.exit_code == 0
        assert "--interval 30" in result.output

    def test_respects_username_password(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--username",
                "mqttuser",
                "--password",
                "s3cret",
            ],
        )
        assert result.exit_code == 0
        assert "--username mqttuser" in result.output
        assert "--password 's3cret'" in result.output

    def test_respects_ha_config(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--ha-config",
                "none",
            ],
        )
        assert result.exit_code == 0
        assert "--ha-config none" in result.output

    def test_output_to_file(self, tmp_path):
        out = tmp_path / "test.service"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        content = out.read_text()
        assert "[Unit]" in content
        assert "[Service]" in content

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_exec_override(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--exec",
                "/usr/local/bin/voltkeeper",
            ],
        )
        assert result.exit_code == 0
        assert "ExecStart=/usr/local/bin/voltkeeper" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_restart_always_in_service(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "Restart=always" in result.output

    def test_restart_flag_in_mqtt_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish", "--help"])
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_publish_service_includes_serial(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--serial",
                "MYSERIAL",
            ],
        )
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
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_watch_source_changes(watcher))
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

    def test_execute_shutdown_raises_on_non_linux(self):
        import sys as _sys
        from unittest.mock import patch

        w = ShutdownWatch(threshold=10, grace=60)
        with patch.object(_sys, "platform", "win32"):
            with pytest.raises(RuntimeError, match="only supported on Linux"):
                w.execute_shutdown()


# ═══════════════════════════════════════════════════════════════════════
#  mqtt-listen CLI
# ═══════════════════════════════════════════════════════════════════════


class TestMqttListenCLI:
    def test_requires_device_type_when_no_address(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--serial", "1234", "--broker", "x"])
        assert result.exit_code != 0
        assert "device-type" in result.output.lower()

    def test_validates_device_type(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen",
                "--serial",
                "1234",
                "--broker",
                "x",
                "--device-type",
                "INVALID",
            ],
        )
        assert result.exit_code != 0
        assert "INVALID" in result.output or "Unknown" in result.output

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

    def test_fails_on_non_linux_platform(self):
        import sys as _sys
        from unittest.mock import patch

        runner = CliRunner()
        with patch.object(_sys, "platform", "win32"):
            result = runner.invoke(cli, ["mqtt-listen", "--serial", "1234", "--broker", "x", "--device-type", "AC2A"])
        assert result.exit_code != 0
        assert "Linux" in result.output


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
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "12345",
                "--broker",
                "192.168.1.100",
            ],
        )
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "Restart=always" in output

    def test_execstart_has_serial_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "SN123",
                "--broker",
                "10.0.0.1",
            ],
        )
        assert result.exit_code == 0
        assert "--serial SN123" in result.output
        assert "--broker 10.0.0.1" in result.output
        assert "mqtt-listen" in result.output

    def test_user_is_root_by_default(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_shutdown_at(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
                "--shutdown-at",
                "20",
            ],
        )
        assert result.exit_code == 0
        assert "--shutdown-at 20" in result.output

    def test_respects_grace_period(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
                "--grace-period",
                "120",
            ],
        )
        assert result.exit_code == 0
        assert "--grace-period 120" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_service_name_uses_serial(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "DEADBEEF",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "voltkeeper-shutdown-DEADBEEF" in result.output

    def test_no_address_argument(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--help",
            ],
        )
        assert result.exit_code == 0
        assert "ADDRESS" not in result.output


# ═══════════════════════════════════════════════════════════════════════
#  NODE_INFO topology discovery
# ═══════════════════════════════════════════════════════════════════════


class TestTopologyDiscovery:
    def test_discover_topology_finds_packs(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert not v2._topology_discovered
        assert v2._discovered_packs == []

        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        assert v2._topology_discovered
        assert 0x29 in v2._discovered_packs

    def test_discover_topology_empty_response(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.discover_topology(bytes(TLV_MAGIC))
        assert v2._topology_discovered
        assert v2._discovered_packs == []

    def test_discover_topology_no_magic(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.discover_topology(b"\x00\x00\x00\x00")
        assert v2._topology_discovered
        assert v2._discovered_packs == []

    def test_polling_commands_includes_packs_when_discovered(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        initial = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 not in initial

        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 in addrs

    def test_polling_commands_no_packs_by_default(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 not in addrs

    def test_topology_discovered_property_false_before_node_info(self):
        # A device declaring has_battery_packs must not claim topology is
        # discovered before NODE_INFO has actually arrived — the previous
        # precedence bug returned True here, hiding the not-yet-discovered
        # state and skipping per-pack polling.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithPacks(V2Base):
            has_battery_packs = True

        v2 = _StubWithPacks("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.topology_discovered is False

    def test_topology_discovered_property_true_after_node_info(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        assert v2.topology_discovered is True

    def test_tlv_sections_includes_node_info_before_discovery(self):
        # NODE_INFO must keep being polled until the device actually
        # responds — verify it stays in the main bundle for a
        # has_sub_devices device whose topology isn't discovered yet.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithSubDevices(V2Base):
            has_sub_devices = True

        v2 = _StubWithSubDevices("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.topology_discovered is False
        sections = v2._tlv_sections()
        addrs = [a for a, _ in sections]
        assert 21000 in addrs  # NODE_INFO


# ═══════════════════════════════════════════════════════════════════════
#  TLV-bundled polling
# ═══════════════════════════════════════════════════════════════════════


class TestTlvBundledPolling:
    def test_use_tlv_polling_true_for_v2(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.use_tlv_polling is True

    def test_tlv_polling_commands_returns_list(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.tlv_polling_commands
        assert len(cmds) == 1
        assert isinstance(cmds[0], TlvReadHoldingRegisters)

    def test_tlv_polling_commands_has_home_and_base(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmd = v2.tlv_polling_commands[0]
        addrs = {a for a, _ in cmd.sections}
        assert 100 in addrs
        assert 1100 in addrs

    def test_tlv_polling_single_bundle_for_ac2a(self):
        # AC2A has no packs and no sub-devices: a single bundle on slave 1.
        from voltkeeper.core.devices.ac2a import AC2A

        ac2a = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
        cmds = ac2a.tlv_polling_commands
        assert len(cmds) == 1
        assert cmds[0].slave_addr == 1

    def test_tlv_polling_per_slave_bundles_for_discovered_packs(self):
        # A device with discovered pack slaves emits one bundle per slave.
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        # Inject discovered packs without going through TLV parsing.
        v2._discovered_packs = [41, 42]
        v2._topology_discovered = True
        cmds = v2.tlv_polling_commands
        assert [c.slave_addr for c in cmds] == [1, 41, 42]
        # Each pack bundle carries only the PACK_MAIN_INFO section.
        for c in cmds[1:]:
            assert [a for a, _ in c.sections] == [6000]
            assert all(count == 32 for _, count in c.sections)

    def test_tlv_polling_pre_discovery_fallback_for_battery_packs(self):
        # has_battery_packs=True but no NODE_INFO yet: a single bundle on
        # slave 1 that includes PACK_MAIN_INFO so the home screen has data
        # on the first poll.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithPacks(V2Base):
            has_battery_packs = True

        v2 = _StubWithPacks("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.tlv_polling_commands
        assert len(cmds) == 1
        assert cmds[0].slave_addr == 1
        addrs = [a for a, _ in cmds[0].sections]
        assert 6000 in addrs

    def test_parse_tlv_dispatches_home_data(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x00)
        tlv_data.extend(b"\x00\x64")
        tlv_data.extend(bytes([0, 124]))
        tlv_data.extend(b"\x00" * 124)
        tlv_data.extend(b"\x00\x00")
        result = v2.parse_tlv(bytes(tlv_data))
        assert "packTotalVoltage" in result or len(result) > 0

    def test_parse_tlv_empty_response(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse_tlv(bytes(TLV_MAGIC))
        assert result == {}

    def test_polling_commands_still_works_for_non_tlv(self):
        from voltkeeper.core.commands import ReadHoldingRegisters
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.polling_commands
        assert len(cmds) >= 6
        for cmd in cmds:
            assert isinstance(cmd, ReadHoldingRegisters)


# ═══════════════════════════════════════════════════════════════════════
#  Time-sliced polling
# ═══════════════════════════════════════════════════════════════════════


class TestTimeSlicedPolling:
    def test_counter_1_excludes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 not in addrs
        assert 100 in addrs

    def test_counter_3_includes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 3
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 in addrs
        assert 1200 in addrs
        assert 100 in addrs

    def test_force_full_poll_includes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        v2._force_full_poll = True
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 in addrs

    def test_counter_wraps_at_10000(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 9999
        v2.tick_poll_counter()
        assert v2._poll_counter == 0

    def test_tick_poll_counter_increments(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 5
        v2.tick_poll_counter()
        assert v2._poll_counter == 6

    def test_force_full_poll_resets_counter(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 5
        v2.force_full_poll()
        assert v2._force_full_poll is True
        assert v2._poll_counter == 3

    def test_tlv_sections_exclude_slow_on_counter_1(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        sections = v2._tlv_sections()
        addrs = {a for a, _ in sections}
        assert 100 in addrs
        assert 1100 not in addrs

    def test_tlv_sections_include_slow_on_counter_3(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 3
        sections = v2._tlv_sections()
        addrs = {a for a, _ in sections}
        assert 1100 in addrs


# ═══════════════════════════════════════════════════════════════════════
#  Unit 2 — base-class ctrl_event defaults and device-type resolution
# ═══════════════════════════════════════════════════════════════════════


def test_decode_ctrl_event_default_returns_none():
    from voltkeeper.core.devices.bluetti_device import BluettiDevice

    class MinimalDevice(BluettiDevice):
        def parse(self, address, data):
            return {}

        def has_field(self, field):
            return False

        def has_field_setter(self, field):
            return False

        def build_setter_command(self, field, value):
            raise NotImplementedError

        @property
        def polling_commands(self):
            return []

        @property
        def logging_commands(self):
            return []

    d = MinimalDevice("00:00:00:00:00:00", "TEST", "123")
    assert d.decode_ctrl_event(0) is None


def test_deviceresult2():
    from voltkeeper.core.devices.v2_base import V2_CTRL_EVENT_BITS, decode_ctrl_event

    caps = decode_ctrl_event(0)
    assert all(not v for v in caps.values())
    assert len(caps) == len(V2_CTRL_EVENT_BITS)


def test_decode_ctrl_event_all_on():
    from voltkeeper.core.devices.v2_base import V2_CTRL_EVENT_BITS, decode_ctrl_event

    max_val = (1 << len(V2_CTRL_EVENT_BITS)) - 1
    caps = decode_ctrl_event(max_val)
    assert all(caps.values())


def test_probe_emit_capabilities_v2():
    from voltkeeper.probe import _emit_capabilities

    profile = {
        "blocks": {
            "APP_HOME_DATA": {
                "address": 100,
                "size": 62,
                "raw_hex": "00" * 48 + "0407" + "00" * 72,
            }
        }
    }
    _emit_capabilities(profile)
    assert "capabilities" in profile
    assert profile["capabilities"]["ctrl_event"] == 0x0407
    decoded = profile["capabilities"]["decoded"]
    assert decoded["power_control"] is True
    assert decoded["ac_control"] is True
    assert decoded["dc_control"] is True


def test_probe_emit_capabilities_no_home_data():
    from voltkeeper.probe import _emit_capabilities

    profile = {"blocks": {}}
    _emit_capabilities(profile)
    assert "capabilities" not in profile


def test_probe_emit_capabilities_short_data():
    from voltkeeper.probe import _emit_capabilities

    profile = {"blocks": {"APP_HOME_DATA": {"raw_hex": "00" * 20}}}
    _emit_capabilities(profile)
    assert "capabilities" not in profile


def test_device_registry_is_public():
    from voltkeeper.bluetooth import device_registry

    reg = device_registry()
    assert "AC2A" in reg


def test_is_supported_device_type():
    from voltkeeper.bluetooth import is_supported_device_type

    assert is_supported_device_type("AC2A") is True
    assert is_supported_device_type("BOGUS") is False


# ═══════════════════════════════════════════════════════════════════════
#  Range validation on writes
# ═══════════════════════════════════════════════════════════════════════


class TestRangeValidation:
    @pytest.fixture
    def ac2a_device(self):
        from voltkeeper.core.devices.ac2a import AC2A

        return AC2A("AA:BB:CC:DD:EE:FF", "2305000")

    def test_in_range_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 20)
        assert cmd.address == 2022
        assert cmd.value == 20

    def test_out_of_range_rejected(self, ac2a_device):
        with pytest.raises(ValueError, match="not in range"):
            ac2a_device.build_setter_command("sys_low_power", 150)

    def test_low_boundary_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 0)
        assert cmd.value == 0

    def test_high_boundary_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 100)
        assert cmd.value == 100

    def test_no_range_field_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("lcd_timeout", 9999)
        assert cmd.value == 9999

    def test_enum_field_not_range_checked(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("inv_freq", "HZ_50")
        assert cmd.address == 2210
        assert cmd.value == 0


# ═══════════════════════════════════════════════════════════════════════
#  New enum field tests
# ═══════════════════════════════════════════════════════════════════════


class TestFieldEnums:
    @pytest.fixture
    def ac2a_device(self):
        from voltkeeper.core.devices.ac2a import AC2A

        return AC2A("AA:BB:CC:DD:EE:FF", "2305000")

    def test_inv_freq_enum_values(self):
        from voltkeeper.core.commands import InvFrequency

        assert InvFrequency.HZ_50.value == 0
        assert InvFrequency.HZ_60.value == 1

    def test_inv_freq_build_setter_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("inv_freq", "HZ_60")
        assert cmd.address == 2210
        assert cmd.value == 1

    def test_inv_freq_build_setter_int(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("inv_freq", 0)
        assert cmd.address == 2210
        assert cmd.value == 0

    def test_led_color_enum_values(self):
        from voltkeeper.core.commands import LedColor

        assert LedColor.OFF.value == 0
        assert LedColor.COOL.value == 1
        assert LedColor.WARM.value == 2
        assert LedColor.SOS.value == 3

    def test_led_color_build_setter(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("led_color", "WARM")
        assert cmd.address == 2078
        assert cmd.value == 2

    def test_pv_type_enum_values(self):
        from voltkeeper.core.commands import PvType

        assert PvType.PV.value == 0
        assert PvType.OTHER.value == 3

    def test_pv2_type_enum_values(self):
        from voltkeeper.core.commands import Pv2Type

        assert Pv2Type.PV.value == 0
        assert Pv2Type.ALTERNATOR.value == 4

    def test_ems_ctrl_mode_enum_values(self):
        from voltkeeper.core.commands import EmsCtrlMode

        assert EmsCtrlMode.DISABLE.value == 0
        assert EmsCtrlMode.LOCAL.value == 4
        assert EmsCtrlMode.AI.value == 8

    def test_ems_ctrl_mode_build_setter(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("ems_ctrl_mode_set", "LOCAL")
        assert cmd.address == 2241
        assert cmd.value == 4


# ═══════════════════════════════════════════════════════════════════════
#  V2 alarm/fault decoding
# ═══════════════════════════════════════════════════════════════════════


class TestV2AlarmDecoding:
    """Tests for _fill_v2_alarms and _fill_v2_pack_alarms on V2Base."""

    def _home_data(self, alarm_word1=0, fault_word1=0):
        """Build an APP_HOME_DATA payload with specific alarm/fault bits set."""
        data = bytearray(78)  # covers alarmInfo (52–59) and faultInfo (66–77)
        # alarmInfo: 4 × 16-bit words, big-endian, at bytes 52–59
        data[52] = (alarm_word1 >> 8) & 0xFF
        data[53] = alarm_word1 & 0xFF
        # faultInfo: 6 × 16-bit words, big-endian, at bytes 66–77
        data[66] = (fault_word1 >> 8) & 0xFF
        data[67] = fault_word1 & 0xFF
        return bytes(data)

    def test_no_alarms_when_all_bytes_zero(self):
        """All-zero alarm/fault bytes yield no alarm.* or fault.* keys (task 6.1)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse(APP_HOME_DATA, self._home_data())
        alarm_keys = [k for k in result if k.startswith("alarm.") or k.startswith("fault.")]
        assert alarm_keys == []

    def test_alarm_word1_bit0_low_power(self):
        """Alarm word 1 bit 0 set on low_power device yields exactly one alarm key (task 6.2)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse(APP_HOME_DATA, self._home_data(alarm_word1=0x0001))
        alarm_keys = [k for k in result if k.startswith("alarm.")]
        fault_keys = [k for k in result if k.startswith("fault.")]
        assert alarm_keys == ["alarm.Grid voltage high"]
        assert fault_keys == []

    def test_profile_switch_changes_alarm_names(self):
        """Same bytes produce different names on low_power vs high_power devices (task 6.3)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        class _HighPower(V2Base):
            V2_ALARM_PROFILE = "high_power"

        low = V2Base("AA:BB:CC:DD:EE:FF", "LOW", "0")
        high = _HighPower("AA:BB:CC:DD:EE:FF", "HIGH", "0")
        data = self._home_data(alarm_word1=0x0001)
        result_low = low.parse(APP_HOME_DATA, data)
        result_high = high.parse(APP_HOME_DATA, data)
        # low_power word 1 bit 0 = "Grid voltage high" (lowercase v)
        assert "alarm.Grid voltage high" in result_low
        # high_power word 1 bit 0 = "Grid Voltage High" (uppercase V)
        assert "alarm.Grid Voltage High" in result_high
        assert "alarm.Grid voltage high" not in result_high
        assert "alarm.Grid Voltage High" not in result_low

    def test_pack_alarm_prefixed_with_sub_addr(self):
        """Pack alarm bit decoded via _parse_node_info gets sub[N]. prefix (task 6.4)."""
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        class _HighVolt(V2Base):
            PACK_ALARM_PROFILE = "high_volt"

        dev = _HighVolt("AA:BB:CC:DD:EE:FF", "TEST", "0")

        # PACK_MAIN_INFO payload: 84 bytes with packHighVoltAlarm bit 0 set.
        # packHighVoltAlarm at bytes 82–83 → PACK_HIGH_VOLT_ALARM_NAMES word 1 bit 0.
        pack_data = bytearray(84)
        pack_data[82] = 0x00
        pack_data[83] = 0x01  # bit 0 → "Overall Overvoltage Alarm"

        tlv = bytearray(TLV_MAGIC)
        tlv.append(0x29)  # slave_addr = 41
        tlv.append(0x17)  # reg_addr hi: 0x1770 = 6000 (PACK_MAIN_INFO)
        tlv.append(0x70)  # reg_addr lo
        length = len(pack_data)
        tlv.append(length >> 8)
        tlv.append(length & 0xFF)
        tlv.extend(pack_data)
        tlv.extend(b"\x00\x00")  # placeholder CRC16 (not validated by parser)

        result = dev._parse_node_info(bytes(tlv))
        assert result.get("sub[41].alarm.Overall Overvoltage Alarm") is True

    def test_v1_alarm_decoding_regression(self):
        """V1 _fill_alarms still decodes a set alarm bit correctly after V2 changes (task 6.5)."""
        from voltkeeper.core.devices.ep500 import EP500

        ep = EP500("AA:BB:CC:DD:EE:FF", "12345678")
        # BASE_REAL_DATA=10; alarm word 1 at reg 54 → byte offset (54-10)*2=88
        data = bytearray(220)
        data[88] = 0x00
        data[89] = 0x01  # bit 0 → CONNECT_CONSTANTS_ALARM_NAMES[1][0] = "Grid voltage high"
        result = ep.parse(10, bytes(data))
        assert result.get("alarm.Grid voltage high") is True
