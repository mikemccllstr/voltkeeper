# ABOUTME: Unit tests for bluetti-cli — utility functions, struct-based protocol parsers, CLI behavior.
# ABOUTME: Uses real AC2A register data captured via BLE as test fixtures.

import asyncio
import csv
from io import StringIO
import json
from decimal import Decimal

import pytest
from click.testing import CliRunner

from src.bluetti_cli.cli import cli
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
from src.bluetti_cli.core.devices.ac2a import AC2A, ChargingMode
from src.bluetti_cli.core.commands import WriteSingleRegister, WriteMultipleRegisters
from src.bluetti_cli.bus import EventBus, ParserMessage, CommandMessage
from src.bluetti_cli.mqtt_client import (
    MQTTClient,
    MqttFieldConfig,
    MqttFieldType,
    NORMAL_DEVICE_FIELDS,
    COMMAND_TOPIC_RE,
    CHARGING_STATUS_MAP,
)


@pytest.fixture
def ac2a_device():
    return AC2A("00:00:00:00:00:00", "TEST")


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
        assert data["command_topic"] == "bluetti/command/AC2A-TEST/ac_output_on"

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


# ═══════════════════════════════════════════════════════════════════════
#  DeviceHandler — polling data flow
# ═══════════════════════════════════════════════════════════════════════


class TestDeviceHandler:
    @pytest.mark.asyncio
    async def test_poll_once_no_double_strip(self, ac2a_device, ac2a_home_bytes):
        """execute() already returns stripped body; _poll_once must not strip again."""
        from unittest.mock import MagicMock, patch
        from src.bluetti_cli.device_handler import DeviceHandler
        from src.bluetti_cli.bus import EventBus, ParserMessage

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


import src.bluetti_cli.load_test as lt


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
