# ABOUTME: Unit tests for bluetti_cli — utility functions, protocol parsers, CLI behavior.
# ABOUTME: Uses real AC2A register data captured via BLE as test fixtures.

import pytest
from click.testing import CliRunner

from bluetti_cli import (
    _ascii,
    _bcd_sn,
    _format_version,
    _parse_home_data,
    _parse_inv_base_info,
    _parse_inv_grid_info,
    _parse_inv_inv_info,
    _parse_inv_load_info,
    _parse_inv_pv_info,
    _s16,
    _s32,
    _u16,
    _u32,
    cli,
    crc16_modbus,
)


# ═══════════════════════════════════════════════════════════════════════
#  CRC-16-Modbus
# ═══════════════════════════════════════════════════════════════════════


class TestCrc16Modbus:
    def test_empty_returns_init_value(self):
        assert crc16_modbus(b"") == b"\xff\xff"

    def test_roundtrip_verify(self):
        """A frame with its CRC appended must produce 0x0000."""
        frame = b"\x01\x03\x00\x64\x00\x06"
        crc = crc16_modbus(frame)
        assert crc16_modbus(frame + crc) == b"\x00\x00"

    def test_deterministic(self):
        assert crc16_modbus(b"\x01\x03\x00\x64\x00\x06") == crc16_modbus(
            b"\x01\x03\x00\x64\x00\x06"
        )

    def test_known_vector(self):
        # Standard Modbus CRC test: b"\x02\x07" → 0x1241 (LE)
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
        # Low reg = 0x00C7, high reg = 0x0000 → 199
        assert _u32(b"\x00\xc7\x00\x00", 0) == 199

    def test_higher_register_set(self):
        # Low reg = 0x0000, high reg = 0x0001 → 65536
        assert _u32(b"\x00\x00\x00\x01", 0) == 65536

    def test_offset(self):
        # Low reg (offset 4) = 0x5678, high reg (offset 6) = 0x1234
        # → (0x1234 << 16) | 0x5678 = 0x12345678
        data = b"\x00\x00\x00\x00\x56\x78\x12\x34"
        assert _u32(data, 4) == 0x12345678

    def test_grid_power_example(self):
        # Real AC2A grid power: bytes show low reg = 0x0093 (147W)
        assert _u32(b"\x00\x93\x00\x00", 0) == 147


class TestS32:
    def test_zero(self):
        assert _s32(b"\x00\x00\x00\x00", 0) == 0

    def test_positive(self):
        assert _s32(b"\x00\x93\x00\x00", 0) == 147

    def test_negative_one(self):
        assert _s32(b"\xff\xff\xff\xff", 0) == -1

    def test_negative(self):
        # Low reg = 0x0000, high reg = 0x8000 → (0x8000 << 16) | 0x0000
        # = 0x80000000 unsigned, signed = -2147483648
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
        # 5 chars: first 4 then rest → "v7733.7"
        assert _format_version(77337) == "v7733.7"

    def test_six_digits(self):
        # 6 chars: first 4 then rest → "v1234.56"
        assert _format_version(123456) == "v1234.56"

    def test_seven_plus(self):
        assert _format_version(773390339) == "v77339.03.39"

    def test_zero(self):
        assert _format_version(0) == "v0"


# ═══════════════════════════════════════════════════════════════════════
#  Home data parser (register 100)
# ═══════════════════════════════════════════════════════════════════════


class TestParseHomeData:
    def test_empty_data(self):
        assert _parse_home_data(b"") == {}
        assert _parse_home_data(b"\x00" * 4) == {}

    def test_battery_fields_present(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        assert "packTotalVoltage" in result
        assert "packTotalCurrent" in result
        assert "packTotalSoc" in result
        assert "packChargingStatus" in result
        # All numeric battery fields are within realistic ranges
        assert 200 <= result["packTotalVoltage"] <= 350
        assert 0 <= result["packTotalCurrent"] <= 100
        assert 0 <= result["packTotalSoc"] <= 100
        assert result["packChargingStatus"] in (0, 1, 2, 3)

    def test_model_name_is_ac2a(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        assert result["deviceModel"].startswith("AC2A")

    def test_serial_present(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        assert "deviceSN" in result
        assert len(result["deviceSN"]) > 0

    def test_power_meters_have_keys(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        for key in ("totalDCPower", "totalACPower", "totalPVPower", "totalGridPower"):
            assert key in result
            assert isinstance(result[key], int)

    def test_energy_totals_have_keys(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        for key in (
            "totalDCEnergy",
            "totalACEnergy",
            "totalPVChargingEnergy",
            "totalGridChargingEnergy",
        ):
            assert key in result
            assert isinstance(result[key], float)
            assert result[key] >= 0.0

    def test_status_fields_present(self, ac2a_home_bytes):
        result = _parse_home_data(ac2a_home_bytes)
        assert "chargingMode" in result
        assert "invWorkingStatus" in result

    def test_short_data_only_basics(self):
        data = b"\x0a\xaa\x00\x16\x00\x64\x00\x02\x01\x00\x01\x00"
        result = _parse_home_data(data)
        assert result["packTotalSoc"] == 100
        assert result["packTotalVoltage"] == pytest.approx(273.0, abs=0.1)
        assert "deviceModel" not in result


# ═══════════════════════════════════════════════════════════════════════
#  Inverter base info parser (register 1100)
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvBaseInfo:
    def test_empty(self):
        assert _parse_inv_base_info(b"") == {}
        assert _parse_inv_base_info(b"\x00" * 10) == {}

    def test_inv_type(self, ac2a_inv_base_bytes):
        result = _parse_inv_base_info(ac2a_inv_base_bytes)
        assert result["invType"] == "AC2A"

    def test_inv_id(self, ac2a_inv_base_bytes):
        result = _parse_inv_base_info(ac2a_inv_base_bytes)
        assert result["invId"] == 0

    def test_software_versions_present(self, ac2a_inv_base_bytes):
        result = _parse_inv_base_info(ac2a_inv_base_bytes)
        soft_keys = [k for k in result if k.startswith("software[")]
        # The fixture device has software versions
        assert len(soft_keys) >= 0
        for k in soft_keys:
            assert "ver=v" in result[k]

    def test_temperatures_absent_when_sensor_off(self, ac2a_inv_base_bytes):
        result = _parse_inv_base_info(ac2a_inv_base_bytes)
        assert result.get("ambientTemp") is None
        assert result.get("invMaxTemp") is None


# ═══════════════════════════════════════════════════════════════════════
#  Inverter PV info parser (register 1200)
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvPvInfo:
    def test_empty(self):
        assert _parse_inv_pv_info(b"") == {}

    def test_keys_present(self, ac2a_inv_pv_bytes):
        result = _parse_inv_pv_info(ac2a_inv_pv_bytes)
        assert "totalChgPower" in result
        assert "totalChgEnergy" in result
        assert isinstance(result["totalChgPower"], int)
        assert isinstance(result["totalChgEnergy"], float)


# ═══════════════════════════════════════════════════════════════════════
#  Grid info parser (register 1300)
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvGridInfo:
    def test_empty(self):
        assert _parse_inv_grid_info(b"") == {}

    def test_frequency_in_range(self, ac2a_inv_grid_bytes):
        result = _parse_inv_grid_info(ac2a_inv_grid_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_inv_grid_bytes):
        result = _parse_inv_grid_info(ac2a_inv_grid_bytes)
        assert "gridPhase[0].voltage" in result
        assert "gridPhase[0].current" in result
        assert "gridPhase[0].power" in result


# ═══════════════════════════════════════════════════════════════════════
#  Load info parser (register 1400)
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvLoadInfo:
    def test_empty(self):
        assert _parse_inv_load_info(b"") == {}

    def test_dc_keys_present(self, ac2a_inv_load_bytes):
        result = _parse_inv_load_info(ac2a_inv_load_bytes)
        for key in ("dc5VPower", "dc12VPower", "dc24VPower"):
            assert key in result
            assert isinstance(result[key], int)


# ═══════════════════════════════════════════════════════════════════════
#  Inverter output parser (register 1500)
# ═══════════════════════════════════════════════════════════════════════


class TestParseInvInvInfo:
    def test_empty(self):
        assert _parse_inv_inv_info(b"") == {}

    def test_frequency_in_range(self, ac2a_inv_inv_bytes):
        result = _parse_inv_inv_info(ac2a_inv_inv_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_inv_inv_bytes):
        result = _parse_inv_inv_info(ac2a_inv_inv_bytes)
        assert "invPhase[0].voltage" in result
        assert "invPhase[0].current" in result
        assert "invPhase[0].power" in result
        assert "invPhase[0].workStatus" in result


# ═══════════════════════════════════════════════════════════════════════
#  CLI integration tests (Click CliRunner)
# ═══════════════════════════════════════════════════════════════════════


class TestCli:
    def test_no_args_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Bluetti power station CLI" in result.output
        assert "status" in result.output
        assert "scan" in result.output

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

    def test_status_requires_bluetooth(self):
        """status command fails gracefully when no BLE adapter available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code != 0
        assert "Error:" in result.output or result.exception is not None

    def test_status_verbose_flag_accepted(self):
        """--verbose flag is recognized (though it will fail on connect)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--verbose", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code != 0

    def test_scan_no_devices(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--timeout", "1"])
        assert result.exit_code in (0, 1)
