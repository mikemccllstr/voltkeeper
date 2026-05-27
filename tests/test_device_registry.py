# ABOUTME: Registry and construction smoke tests for all models.

import pytest

from voltkeeper.bluetooth import _device_registry, build_device

ALL_PREFIXES = [
    "AC2A",
    "AC60",
    "EP600",
    "EB3A",
    "AC300",
    "AC500",
    "AC200L",
    "AC200PL",
    "AC200M",
    "EL100V2",
    "AORA100_MINI",
    "AORA30_MINI",
    "AORA200_MINI",
    "HB500S",
    "BH500E",
]

_CLASS_NAME_TO_PREFIX = {
    "El100V2": "EL100V2",
    "Aora100Mini": "AORA100_MINI",
    "Aora30Mini": "AORA30_MINI",
    "Aora200Mini": "AORA200_MINI",
}

ALL_MODELS = [f"{pfx}2305000" for pfx in ALL_PREFIXES]


@pytest.mark.parametrize("model_name", ALL_MODELS)
def test_build_device_constructs_every_model(model_name):
    """Each registered model must construct without raising."""
    device = build_device("AA:BB:CC:DD:EE:FF", model_name)
    assert device.type in ALL_PREFIXES
    assert device.sn.isdigit()


def test_registry_has_all_expected_prefixes():
    registry = _device_registry()
    for prefix in ALL_PREFIXES:
        assert prefix in registry, f"Missing: {prefix}"
        cls = registry[prefix]
        expected_name = _CLASS_NAME_TO_PREFIX.get(cls.__name__, cls.__name__)
        assert expected_name == prefix, f"{prefix!r} maps to {cls.__name__}, not itself"


def test_v2_models_protocol_version():
    from voltkeeper.core.devices.ac2a import AC2A
    from voltkeeper.core.devices.ac60 import AC60
    from voltkeeper.core.devices.el100v2 import El100V2
    from voltkeeper.core.devices.ep600 import EP600

    for cls in (AC2A, AC60, El100V2, EP600):
        d = cls("AA:BB:CC:DD:EE:FF", "1234567")
        assert d.protocol_version == 2000, f"{cls.__name__} should be V2"


def test_v1_models_protocol_version():
    from voltkeeper.core.devices.ac200l import AC200L
    from voltkeeper.core.devices.ac200m import AC200M
    from voltkeeper.core.devices.ac200pl import AC200PL
    from voltkeeper.core.devices.ac300 import AC300
    from voltkeeper.core.devices.ac500 import AC500
    from voltkeeper.core.devices.eb3a import EB3A

    expected = {
        AC200L: 1022,
        AC200M: 1016,
        AC200PL: 1022,
        AC300: 0,
        AC500: 0,
        EB3A: 1019,
    }
    for cls, ver in expected.items():
        d = cls("AA:BB:CC:DD:EE:FF", "1234567")
        assert d.protocol_version == ver, f"{cls.__name__} should be V1 (ver={ver})"


def test_v1_model_has_writable_control_struct():
    """Models with WRITABLE_FIELD_NAMES must populate the control struct."""
    from voltkeeper.core.devices.ac300 import AC300
    from voltkeeper.core.devices.eb3a import EB3A

    for cls in (AC300, EB3A):
        d = cls("AA:BB:CC:DD:EE:FF", "1234567")
        assert len(d.WRITABLE_FIELD_NAMES) > 0, f"{cls.__name__} has no writable fields"
        assert len(d.control_struct.fields) > 0, f"{cls.__name__} control_struct is empty"
        for name in d.WRITABLE_FIELD_NAMES:
            assert d.has_field_setter(name), f"{cls.__name__} missing setter for {name}"


def test_ac200pl_inherits_ac200l_controls():
    from voltkeeper.core.devices.ac200l import AC200L
    from voltkeeper.core.devices.ac200pl import AC200PL

    ac200l = AC200L("AA:BB:CC:DD:EE:FF", "1234567")
    ac200pl = AC200PL("AA:BB:CC:DD:EE:FF", "1234567")
    assert ac200pl.type == "AC200PL"
    assert ac200pl.WRITABLE_FIELD_NAMES == ac200l.WRITABLE_FIELD_NAMES
    assert len(ac200pl.control_struct.fields) == len(ac200l.control_struct.fields)


def test_v1_alarm_fault_parsing_eb3a_default_tables():
    """EB3A uses ConnectConstants (V1 high-power) alarm tables."""
    from voltkeeper.core.devices.eb3a import EB3A
    from voltkeeper.core.devices.v1_base import BASE_REAL_DATA

    eb3a = EB3A("00:00:00:00:00:00", "1234567")

    # alarmInfo: reg 54-57 (4 words), faultInfo: reg 58-64 (7 words)
    regs = {}
    for r in range(BASE_REAL_DATA, 65):
        regs[r] = 0xFFFF

    size = 65 - BASE_REAL_DATA + 1
    data = bytearray(size * 2)
    for reg, val in regs.items():
        off = (reg - BASE_REAL_DATA) * 2
        data[off] = (val >> 8) & 0xFF
        data[off + 1] = val & 0xFF

    parsed = eb3a.parse(BASE_REAL_DATA, bytes(data))

    alarm_keys = [k for k in parsed if k.startswith("alarm.")]
    fault_keys = [k for k in parsed if k.startswith("fault.")]

    assert len(alarm_keys) > 0, "No alarm keys found"
    assert len(fault_keys) > 0, "No fault keys found"

    # ConnectConstants alarm names (V1 high-power)
    assert "alarm.Grid voltage high" in parsed
    assert "alarm.Meter communication failure" in parsed

    # Low-power alarm names should NOT appear
    assert "alarm.UPS Input Overvoltage" not in parsed
    assert "alarm.Networking Operation Abnormal" not in parsed

    # ConnectConstants fault names
    assert "fault.Inverter Over Load" in parsed
    assert "fault.Voltage Sensor Error" in parsed
    assert "fault.GFCI Hardware Circuit Error" in parsed

    # None entries should NOT be emitted
    assert "fault.None" not in parsed


def test_v1_alarm_fault_parsing_ac200l_low_power_tables():
    """AC200L uses lowPower alarm tables (isLowPower=true)."""
    from voltkeeper.core.devices.ac200l import AC200L
    from voltkeeper.core.devices.v1_base import BASE_REAL_DATA

    ac200l = AC200L("00:00:00:00:00:00", "1234567")

    regs = {}
    for r in range(BASE_REAL_DATA, 65):
        regs[r] = 0xFFFF

    size = 65 - BASE_REAL_DATA + 1
    data = bytearray(size * 2)
    for reg, val in regs.items():
        off = (reg - BASE_REAL_DATA) * 2
        data[off] = (val >> 8) & 0xFF
        data[off + 1] = val & 0xFF

    parsed = ac200l.parse(BASE_REAL_DATA, bytes(data))

    alarm_keys = [k for k in parsed if k.startswith("alarm.")]
    fault_keys = [k for k in parsed if k.startswith("fault.")]

    assert len(alarm_keys) > 0, "No alarm keys found"
    assert len(fault_keys) > 0, "No fault keys found"

    # Low-power alarm names
    assert "alarm.UPS Input Overvoltage" in parsed
    assert "alarm.Networking Operation Abnormal" in parsed
    assert "alarm.PV Configuration Error" in parsed

    # ConnectConstants alarm names should NOT appear
    assert "alarm.Meter communication failure" not in parsed

    # Low-power fault names
    assert "fault.Inverter Overload" in parsed
    assert "fault.PV1 Over Voltage" in parsed
    assert "fault.Leakage Current Fault" in parsed


def test_v1_alarm_fault_parsing_no_bits_set():
    """No bits set → no alarm/fault keys."""
    from voltkeeper.core.devices.v1_base import BASE_REAL_DATA, V1Base

    v1 = V1Base("00:00:00:00:00:00", "EB3A", "TEST")

    size = 63 - BASE_REAL_DATA + 1
    data = bytearray(size * 2)

    parsed = v1.parse(BASE_REAL_DATA, bytes(data))

    alarm_keys = [k for k in parsed if k.startswith("alarm.")]
    fault_keys = [k for k in parsed if k.startswith("fault.")]

    assert len(alarm_keys) == 0
    assert len(fault_keys) == 0


def test_build_setter_command_v1():
    from voltkeeper.core.devices.ac300 import AC300

    d = AC300("AA:BB:CC:DD:EE:FF", "1234567")
    cmd = d.build_setter_command("ac_output", True)
    assert cmd.address == 3007
    assert cmd.value == 1

    cmd = d.build_setter_command("charging_mode", "TURBO")
    assert cmd.address == 3065
    assert cmd.value == 1


def test_build_setter_command_v2():
    from voltkeeper.core.devices.ac60 import AC60

    d = AC60("AA:BB:CC:DD:EE:FF", "1234567")
    cmd = d.build_setter_command("ac_output", True)
    assert cmd.address == 2011
    assert cmd.value == 1

    cmd = d.build_setter_command("charging_mode", "SILENT")
    assert cmd.address == 2020
    assert cmd.value == 2


def test_ac2a_lcd_timeout_range_enforced():
    import pytest

    from voltkeeper.core.devices.ac2a import AC2A

    d = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
    cmd = d.build_setter_command("lcd_timeout", 100)
    assert cmd.value == 100

    with pytest.raises(ValueError):
        d.build_setter_command("lcd_timeout", 256)

    with pytest.raises(ValueError):
        d.build_setter_command("lcd_timeout", 65535)


def test_ac200l_control_struct_has_new_fields():
    from voltkeeper.core.devices.ac200l import AC200L

    d = AC200L("AA:BB:CC:DD:EE:FF", "1234567")
    fields = {f.name: f for f in d.control_struct.fields}

    assert "system_time" in fields
    assert fields["system_time"].address == 3031

    assert "max_charging_power" in fields
    assert fields["max_charging_power"].address == 3057

    assert "max_discharge_power" in fields
    assert fields["max_discharge_power"].address == 3058

    assert "eco_auto_off" in fields
    assert fields["eco_auto_off"].address == 3064

    assert d.has_field_setter("system_time")
    assert d.has_field_setter("max_charging_power")
    assert d.has_field_setter("max_discharge_power")


def test_ac2a_control_struct_has_new_fields():
    from voltkeeper.core.devices.ac2a import AC2A

    d = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
    fields = {f.name: f for f in d.control_struct.fields}

    assert "ctrl_grid" in fields
    assert fields["ctrl_grid"].address == 2207

    assert "ctrl_feed" in fields
    assert fields["ctrl_feed"].address == 2208

    assert "system_time" in fields
    assert fields["system_time"].address == 2001

    assert d.has_field_setter("ctrl_grid")
    assert d.has_field_setter("ctrl_feed")


def test_ac2a_writable_ranges():
    from voltkeeper.core.devices.ac2a import AC2A

    d = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
    ranges = d.writable_ranges

    assert any(2001 in r for r in ranges), "2001 not in writable ranges"
    assert any(2026 in r for r in ranges), "2026 not in writable ranges"
    assert any(2207 in r for r in ranges), "2207 not in writable ranges"
    assert any(2216 in r for r in ranges), "2216 not in writable ranges"


def test_build_device_aora_mini():
    d = build_device("AA:BB:CC:DD:EE:FF", "AORA100_MINI12345")
    assert d.type == "AORA100_MINI"
    assert d.sn == "12345"


def test_build_device_hb500s():
    d = build_device("AA:BB:CC:DD:EE:FF", "HB500S1234567890123")
    assert d.type == "HB500S"
    assert d.sn == "1234567890123"


def test_build_device_bh500e():
    d = build_device("AA:BB:CC:DD:EE:FF", "BH500E1234567890123")
    assert d.type == "BH500E"
    assert d.sn == "1234567890123"


def test_battery_pack_base_no_inverter_blocks():
    from voltkeeper.core.devices.battery_packs import BatteryPackBase

    d = BatteryPackBase("AA:BB:CC:DD:EE:FF", "TEST", "0")
    assert not hasattr(d, "inv_base_struct")
    assert not hasattr(d, "inv_pv_struct")
    assert not hasattr(d, "inv_grid_struct")
    assert not hasattr(d, "inv_load_struct")
    assert not hasattr(d, "inv_inv_struct")
