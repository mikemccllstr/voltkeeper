# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest


class TestEL400:
    @pytest.fixture
    def el400_device(self):
        from voltkeeper.core.devices.el400 import EL400

        return EL400("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL4002305000")
        assert d.type == "EL400"
        assert d.sn == "2305000"

    def test_pack_voltage_scale_56v(self):
        from voltkeeper.core.devices.el400 import EL400

        assert EL400.DEFAULT_PACK_VOLTAGE_SCALE == 1

    def test_writable_fields_known(self, el400_device):
        for field in (
            "ac_output",
            "dc_output",
            "charging_mode",
            "power_lifting",
            "working_mode",
            "system_power",
            "remote_startup_soc",
            "sleep_power_threshold",
        ):
            assert el400_device.has_field_setter(field), f"{field} should be writable"

    def test_old_power_off_field_removed(self, el400_device):
        # `power_off` and `sleep_mode` are no longer writable — they were
        # replaced by `system_power` to fix the register-2013 read collision.
        assert not el400_device.has_field_setter("power_off")
        assert not el400_device.has_field_setter("sleep_mode")

    def test_system_power_setter_sleep(self, el400_device):
        cmd = el400_device.build_setter_command("system_power", "sleep")
        assert cmd.address == 2013
        assert cmd.value == 4

    def test_system_power_setter_shutdown(self, el400_device):
        cmd = el400_device.build_setter_command("system_power", "shutdown")
        assert cmd.address == 2013
        assert cmd.value == 1

    def test_system_power_parse_sleep_value(self, el400_device):
        # Reading register 2013 with raw value 4 must yield system_power=SLEEP
        # as a single enum field, not collide with two true bools.
        from voltkeeper.core.commands import SystemPowerOff

        # control_struct.parse expects a contiguous block starting at the
        # first field; build a sparse block by parsing a 1-register block
        # at address 2013 with value 4.
        data = (4).to_bytes(2, "big")
        result = el400_device.control_struct.parse(2013, data)
        assert result.get("system_power") is SystemPowerOff.SLEEP
        assert "power_off" not in result
        assert "sleep_mode" not in result

    def test_remote_startup_soc_setter(self, el400_device):
        cmd = el400_device.build_setter_command("remote_startup_soc", 50)
        assert cmd.address == 2074
        assert cmd.value == 50

    def test_sleep_power_threshold_setter(self, el400_device):
        cmd = el400_device.build_setter_command("sleep_power_threshold", 100)
        assert cmd.address == 2079
        assert cmd.value == 100

    def test_no_child_lock(self, el400_device):
        assert not el400_device.has_field_setter("child_lock")

    def test_unknown_field_rejected(self, el400_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el400_device.build_setter_command("nonexistent", 1)
