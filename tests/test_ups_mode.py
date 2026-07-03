# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.commands import WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A


class TestUpsMode:
    """Tests for ups_mode writable BoolField on V1 and V2 devices (tasks 4.1–4.5)."""

    def test_v1_write_on_produces_register_3035_value_1(self):
        """AC300 write ups_mode on → WriteSingleRegister(3035, 1) (task 4.1)."""
        from voltkeeper.core.devices.ac300 import AC300

        dev = AC300("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "on")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 1

    def test_v1_write_off_produces_register_3035_value_0(self):
        """AC300 write ups_mode off → WriteSingleRegister(3035, 0) (task 4.2)."""
        from voltkeeper.core.devices.ac300 import AC300

        dev = AC300("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "off")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 0

    def test_v1_read_register_3035_value_1_yields_ups_mode_true(self):
        """Reading register 3035 value 1 yields ups_mode=True in parsed result (task 4.3)."""
        from voltkeeper.core.devices.ac300 import AC300

        dev = AC300("AA:BB:CC:DD:EE:FF", "0")
        # Single register read: 2 bytes, value 0x0001
        data = bytes([0x00, 0x01])
        result = dev.parse(3035, data)
        assert result.get("ups_mode") is True

    def test_v1_read_register_3035_value_0_yields_ups_mode_false(self):
        """Reading register 3035 value 0 yields ups_mode=False in parsed result."""
        from voltkeeper.core.devices.ac300 import AC300

        dev = AC300("AA:BB:CC:DD:EE:FF", "0")
        data = bytes([0x00, 0x00])
        result = dev.parse(3035, data)
        assert result.get("ups_mode") is False

    def test_v2_write_on_produces_register_3035_value_1(self):
        """EL400 write ups_mode on → WriteSingleRegister(3035, 1) (task 4.4)."""
        from voltkeeper.core.devices.el400 import EL400

        dev = EL400("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "on")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 1

    def test_v2_write_off_produces_register_3035_value_0(self):
        """EL400 write ups_mode off → WriteSingleRegister(3035, 0)."""
        from voltkeeper.core.devices.el400 import EL400

        dev = EL400("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "off")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 0

    def test_v2_read_register_3035_value_1_yields_ups_mode_true(self):
        """V2 parse of register 3035 value 1 yields ups_mode=True."""
        from voltkeeper.core.devices.el400 import EL400

        dev = EL400("AA:BB:CC:DD:EE:FF", "0")
        data = bytes([0x00, 0x01])
        result = dev.parse(3035, data)
        assert result.get("ups_mode") is True

    def test_v1_all_supporting_devices_expose_ups_mode(self):
        """AC300, AC500, AC200L, AC200PL, EP500 all have ups_mode in WRITABLE_FIELD_NAMES."""
        from voltkeeper.core.devices.ac200l import AC200L
        from voltkeeper.core.devices.ac200pl import AC200PL
        from voltkeeper.core.devices.ac300 import AC300
        from voltkeeper.core.devices.ac500 import AC500
        from voltkeeper.core.devices.ep500 import EP500

        for cls in (AC300, AC500, AC200L, AC200PL, EP500):
            assert "ups_mode" in cls.WRITABLE_FIELD_NAMES, f"{cls.__name__} missing ups_mode"

    def test_v2_all_supporting_devices_expose_ups_mode(self):
        """EL10V2, EL30V2, EL400, EP600 all have ups_mode in WRITABLE_FIELD_NAMES.
        EL100V2 removed — APK never reads 3035 for V2, hardware returns exception 3."""
        from voltkeeper.core.devices.el10v2 import EL10V2
        from voltkeeper.core.devices.el30v2 import EL30V2
        from voltkeeper.core.devices.el400 import EL400
        from voltkeeper.core.devices.ep600 import EP600

        for cls in (EL10V2, EL30V2, EL400, EP600):
            assert "ups_mode" in cls.WRITABLE_FIELD_NAMES, f"{cls.__name__} missing ups_mode"

    def test_unsupported_devices_do_not_expose_ups_mode(self):
        """ups_mode is NOT exposed on AC2A, EB3A, AC60, AC180, AORA Mini (task 4.5)."""
        from voltkeeper.core.devices.ac60 import AC60
        from voltkeeper.core.devices.ac180 import AC180
        from voltkeeper.core.devices.aora_mini import Aora100Mini
        from voltkeeper.core.devices.eb3a import EB3A

        for cls in (AC2A, EB3A, AC60, AC180, Aora100Mini):
            names = getattr(cls, "WRITABLE_FIELD_NAMES", [])
            assert "ups_mode" not in names, f"{cls.__name__} wrongly has ups_mode"

    def test_ep500_write_produces_register_3035(self):
        """EP500 write ups_mode on → WriteSingleRegister(3035, 1)."""
        from voltkeeper.core.devices.ep500 import EP500

        dev = EP500("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "on")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 1

    def test_ep600_write_produces_register_3035(self):
        """EP600 write ups_mode off → WriteSingleRegister(3035, 0)."""
        from voltkeeper.core.devices.ep600 import EP600

        dev = EP600("AA:BB:CC:DD:EE:FF", "0")
        cmd = dev.build_setter_command("ups_mode", "off")
        assert isinstance(cmd, WriteSingleRegister)
        assert cmd.address == 3035
        assert cmd.value == 0
