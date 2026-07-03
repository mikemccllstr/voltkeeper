# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.utils import (
    _ascii,
    _bcd_sn,
    _s16,
    _s32,
    _u16,
    _u32,
    crc16_modbus,
    format_version,
)


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


class TestFormatVersion:
    def test_short(self):
        assert format_version(100) == "v100"

    def test_four_digits(self):
        assert format_version(9001) == "v9001"

    def test_five_digits(self):
        assert format_version(77337) == "v7733.7"

    def test_six_digits(self):
        assert format_version(123456) == "v1234.56"

    def test_seven_plus(self):
        assert format_version(773390339) == "v77339.03.39"

    def test_zero(self):
        assert format_version(0) == "v0"
