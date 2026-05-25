# ABOUTME: Synthetic fixture tests for V1Base register parsing per FINDINGS §15.6.

from voltkeeper.core.devices.v1_base import BASE_REAL_DATA, V1Base


def _make_register_bytes(reg_values: dict[int, int]) -> bytes:
    """Build a Modbus register blob from {register_address: value} pairs.

    Registers not in *reg_values* are filled with zeros. The blob covers
    from BASE_REAL_DATA up to the highest register in *reg_values*.
    """
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
    """Validate every V1Base field that parses from structured register data."""
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")

    # Covers all field-bearing registers from §15.6.
    regs = {
        BASE_REAL_DATA + 0: 0x4542,  # 'E' 'B' — deviceModel bytes 0-1
        BASE_REAL_DATA + 1: 0x3341,  # '3' 'A' — deviceModel bytes 2-3
        BASE_REAL_DATA + 2: 0x3030,  # model padding
        BASE_REAL_DATA + 3: 0x3030,
        BASE_REAL_DATA + 4: 0x3030,
        BASE_REAL_DATA + 5: 0x3030,
        16: 1018,  # protocolVer
        36: 250,  # pvChargingPower
        37: 50,  # gridChargingPower
        38: 200,  # acLoadPower
        39: 30,  # dcLoadPower
        40: 0,  # feedBackPower
        41: 1200,  # totalPVPower raw; expect 120.0 after ÷10
        42: 0,  # totalPVPower high word
        43: 75,  # batterySOC
        44: 1,  # pvIconDisplay
        45: 0,  # gridIconDisplay
        46: 1,  # pv2BatteryEnergyLine
        47: 0,  # grid2BatteryEnergyLine
        48: 1,  # battery2ACEnergyLine
        49: 0,  # battery2DCEnergyLine
        50: 0,  # battery2GridEnergyLine
        51: 0,  # grid2LoadEnergyLine
        52: 0,  # pv2GridEnergyLine
        53: 1,  # batteryDischargingStatus
        63: 45,  # chgFullTime
        64: 0,  # dsgEmptyTime
        65: 0,  # sysIsHighVolt
        66: 0x0101,  # maxGridChgCurrentEnable=1 (high byte), gridPlusModeEnable=1 (low byte)
        67: 230,  # rateVoltage
        68: 50,  # rateFrequency
    }
    data = _make_register_bytes(regs)
    parsed = v1.parse(BASE_REAL_DATA, data)

    assert parsed.get("protocolVer") == 1018
    assert parsed.get("pvChargingPower") == 250
    assert parsed.get("gridChargingPower") == 50
    assert parsed.get("acLoadPower") == 200
    assert parsed.get("dcLoadPower") == 30
    assert parsed.get("feedBackPower") == 0
    assert parsed.get("totalPVPower") == 120.0
    assert parsed.get("batterySOC") == 75
    assert parsed.get("pvIconDisplay") == 1
    assert parsed.get("gridIconDisplay") == 0
    assert parsed.get("pv2BatteryEnergyLine") == 1
    assert parsed.get("grid2BatteryEnergyLine") == 0
    assert parsed.get("battery2ACEnergyLine") == 1
    assert parsed.get("battery2DCEnergyLine") == 0
    assert parsed.get("battery2GridEnergyLine") == 0
    assert parsed.get("grid2LoadEnergyLine") == 0
    assert parsed.get("pv2GridEnergyLine") == 0
    assert parsed.get("batteryDischargingStatus") == 1
    assert parsed.get("chgFullTime") == 45
    assert parsed.get("dsgEmptyTime") == 0
    assert parsed.get("sysIsHighVolt") == 0
    assert parsed.get("maxGridChgCurrentEnable") == 1
    assert parsed.get("gridPlusModeEnable") == 1
    assert parsed.get("rateVoltage") == 230
    assert parsed.get("rateFrequency") == 50


def test_v1_parse_device_model_is_string():
    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")
    # Provide enough registers for the 6-register SwapStringField at register 10
    regs = {
        BASE_REAL_DATA + 0: 0x4542,
        BASE_REAL_DATA + 1: 0x3341,
        BASE_REAL_DATA + 2: 0x0000,
        BASE_REAL_DATA + 3: 0x0000,
        BASE_REAL_DATA + 4: 0x0000,
        BASE_REAL_DATA + 5: 0x0000,
    }
    data = _make_register_bytes(regs)
    parsed = v1.parse(BASE_REAL_DATA, data)
    assert isinstance(parsed.get("deviceModel"), str)
    assert len(parsed.get("deviceModel", "")) > 0


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
    assert cmds[0].quantity == 110


def test_v1_new_settable_constants():
    from voltkeeper.core.devices.v1_base import (
        ECO_AUTO_OFF,
        HIGH_POWER_SETTINGS,
        LOW_POWER_SETTINGS,
        MACHINE_ADDRESS,
        MACHINE_MODE,
        MAX_CHARGING_CURRENT_OF_GRID,
        MAX_CHARGING_POWER,
        MAX_DISCHARGE_POWER,
        MAX_DISCHARGING_CURRENT,
        MAX_PV_CHARGE_CURRENT,
        SYSTEM_TIME,
        WORKING_TIME,
    )

    assert MACHINE_MODE == 3004
    assert MACHINE_ADDRESS == 3005
    assert MAX_PV_CHARGE_CURRENT == 3014
    assert LOW_POWER_SETTINGS == 3015
    assert HIGH_POWER_SETTINGS == 3016
    assert MAX_DISCHARGING_CURRENT == 3018
    assert MAX_CHARGING_CURRENT_OF_GRID == 3019
    assert SYSTEM_TIME == 3031
    assert WORKING_TIME == 3039
    assert MAX_CHARGING_POWER == 3057
    assert MAX_DISCHARGE_POWER == 3058
    assert ECO_AUTO_OFF == 3064
