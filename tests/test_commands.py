# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest

from voltkeeper.core.commands import WriteMultipleRegisters, WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.utils import (
    crc16_modbus,
)


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


class TestFieldEnums:
    @pytest.fixture
    def ac2a_device(self):

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
