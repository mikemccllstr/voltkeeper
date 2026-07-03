# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest


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
