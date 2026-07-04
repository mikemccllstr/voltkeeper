# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest


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
        assert cmd.value == 2

    def test_unknown_field_rejected(self, ac180_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            ac180_device.build_setter_command("nonexistent", 1)

    def test_pack_voltage_scale_default(self):
        from voltkeeper.core.devices.ac180 import AC180

        assert AC180.DEFAULT_PACK_VOLTAGE_SCALE == 1
