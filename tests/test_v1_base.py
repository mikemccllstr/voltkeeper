# ABOUTME: Synthetic fixture tests for V1Base register parsing per FINDINGS §15.6.
# ABOUTME: Unit 9 per IMPLEMENTATION_UNITS.md.

from src.bluetti_cli.core.devices.v1_base import BASE_REAL_DATA, V1Base


def _make_register_bytes(reg_values: dict[int, int]) -> bytes:
    """Build a Modbus register blob from {register_address: value} pairs."""
    if not reg_values:
        return b""
    max_reg = max(reg_values.keys())
    size = max_reg - BASE_REAL_DATA + 1
    data = bytearray(size * 2)
    for reg, value in reg_values.items():
        offset = (reg - BASE_REAL_DATA) * 2
        data[offset] = (value >> 8) & 0xFF
        data[offset + 1] = value & 0xFF
    return bytes(data)


def test_v1_parse_base_real_data():
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")

    # Synthetic EB3A-like data
    regs = {
        BASE_REAL_DATA + 0: 0x4542,  # 'E' 'B' (model ASCII)
        BASE_REAL_DATA + 1: 0x3341,  # '3' 'A'
        BASE_REAL_DATA + 2: 0x0000,
        BASE_REAL_DATA + 3: 0x0000,
        BASE_REAL_DATA + 4: 0x0000,
        BASE_REAL_DATA + 5: 0x0000,
        16: 1018,  # protocolVer
        BASE_REAL_DATA + 11: 0x4741,  # more SN data
        43: 75,  # batterySOC 75%
        44: 1,  # pvIconDisplay
        45: 0,  # gridIconDisplay
    }
    data = _make_register_bytes(regs)
    parsed = v1.parse(BASE_REAL_DATA, data)

    assert parsed.get("batterySOC") == 75
    assert parsed.get("pvIconDisplay") == 1
    assert parsed.get("gridIconDisplay") == 0


def test_v1_empty_control_struct():
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")

    assert v1.control_struct is not None
    assert v1.WRITABLE_FIELD_NAMES == []
    assert v1.has_field_setter("ac_output") is False


def test_v1_parse_falls_through_for_unknown_range():
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")
    parsed = v1.parse(9999, b"\x00" * 10)
    assert parsed == {}


def test_v1_polling_commands():
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")
    cmds = v1.polling_commands
    assert len(cmds) >= 1
    assert cmds[0].starting_address == BASE_REAL_DATA
