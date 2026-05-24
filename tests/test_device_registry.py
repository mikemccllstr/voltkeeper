# ABOUTME: Registry and construction smoke tests for All models added in Unit 10.
# ABOUTME: Unit 10 per IMPLEMENTATION_UNITS.md.

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
]

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
        assert cls.__name__ == prefix, f"{prefix!r} maps to {cls.__name__}, not itself"


def test_v2_models_protocol_version():
    from voltkeeper.core.devices.ac2a import AC2A
    from voltkeeper.core.devices.ac60 import AC60
    from voltkeeper.core.devices.ep600 import EP600

    for cls in (AC2A, AC60, EP600):
        d = cls("AA:BB:CC:DD:EE:FF", "1234567")
        assert d.protocol_version == 2000, f"{cls.__name__} should be V2"


def test_v1_models_are_v1():
    from voltkeeper.core.devices.ac200l import AC200L
    from voltkeeper.core.devices.ac200m import AC200M
    from voltkeeper.core.devices.ac200pl import AC200PL
    from voltkeeper.core.devices.ac300 import AC300
    from voltkeeper.core.devices.ac500 import AC500
    from voltkeeper.core.devices.eb3a import EB3A

    for cls in (AC200L, AC200M, AC200PL, AC300, AC500, EB3A):
        d = cls("AA:BB:CC:DD:EE:FF", "1234567")
        assert d.protocol_version == 0, f"{cls.__name__} should be V1"


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
