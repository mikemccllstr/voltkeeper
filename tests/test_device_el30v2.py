# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest


class TestEL30V2:
    @pytest.fixture
    def el30v2_device(self):
        from voltkeeper.core.devices.el30v2 import EL30V2

        return EL30V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL30V22305000")
        assert d.type == "EL30V2"
        assert d.sn == "2305000"

    def test_pack_voltage_scale_25v(self):
        from voltkeeper.core.devices.el30v2 import EL30V2

        assert EL30V2.DEFAULT_PACK_VOLTAGE_SCALE == 2

    def test_writable_fields_known(self, el30v2_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "ctrl_grid",
            "ctrl_feed",
            "inv_voltage",
            "inv_freq",
            "grid_max_power",
            "grid_max_current",
            "feed_max_power",
            "feed_max_current",
        ):
            assert el30v2_device.has_field_setter(field), f"{field} should be writable"

    def test_no_child_lock(self, el30v2_device):
        assert not el30v2_device.has_field_setter("child_lock")

    def test_grid_control_setters(self, el30v2_device):
        cmd = el30v2_device.build_setter_command("ctrl_grid", True)
        assert cmd.address == 2207
        assert cmd.value == 1

        cmd = el30v2_device.build_setter_command("grid_max_current", 15)
        assert cmd.address == 2214

    def test_unknown_field_rejected(self, el30v2_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el30v2_device.build_setter_command("nonexistent", 1)
