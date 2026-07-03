# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest

from voltkeeper.core.utils import (
    _u16,
)


def _iot_response_bytes() -> bytes:
    """Real IoT response bytes from EL100V2 hardware probe (FW SW#3).
    Byte offsets match APK v3.0.9 parseIOTInfo:
      0-11:  iotModel (swapped "IOT")
      12-19: iotSn (getDeviceSN format)
      28-31: iotSoftwareVer
      32-35: rfVer
      36-37: status word (bit 2 = ble_status)
    """
    return bytes(
        [
            0x4F,
            0x49,
            0x00,
            0x54,
            0x00,
            0x00,
            0x00,
            0x00,  # 0-7
            0x00,
            0x00,
            0x00,
            0x00,
            0x1C,
            0x77,
            0xDB,
            0xFA,  # 8-15
            0x02,
            0x4F,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,  # 16-23
            0x00,
            0x00,
            0x00,
            0x00,
            0x3E,
            0x6B,
            0x00,
            0x0C,  # 24-31
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x04,  # 32-37: status=0x0004
        ]
    )


class TestEl100V2:
    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_registry_construction(self):
        from voltkeeper.bluetooth import build_device

        d = build_device("AA:BB:CC:DD:EE:FF", "EL100V22305000")
        assert d.type == "EL100V2"
        assert d.sn == "2305000"

    def test_polling_commands_inherits_v2(self, el100v2_device):
        cmds = el100v2_device.polling_commands
        addrs = {cmd.starting_address for cmd in cmds}
        for expected in (100, 1100, 1200, 1300, 1400, 1500):
            assert expected in addrs, f"Missing register block {expected}"

    def test_use_tlv_polling(self, el100v2_device):
        assert el100v2_device.use_tlv_polling is True

    def test_writable_fields_known(self, el100v2_device):
        from voltkeeper.core.devices.el100v2 import El100V2

        for field in El100V2.WRITABLE_FIELD_NAMES:
            assert el100v2_device.has_field_setter(field), f"{field} should be writable"

    def test_readonly_fields_not_writable(self, el100v2_device):
        assert not el100v2_device.has_field_setter("packTotalSoc")
        assert not el100v2_device.has_field_setter("deviceModel")
        assert not el100v2_device.has_field_setter("totalDCPower")

    def test_unknown_field_rejected(self, el100v2_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            el100v2_device.build_setter_command("nonexistent", 1)

    def test_build_setter_ac_output(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("ac_output", True)
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_build_setter_dc_output(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("dc_output", False)
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_build_setter_charging_mode(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("charging_mode", "TURBO")
        assert cmd.address == 2020
        assert cmd.value == 1

    def test_build_setter_ctrl_grid(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("ctrl_grid", True)
        assert cmd.address == 2207
        assert cmd.value == 1

    def test_build_setter_grid_max_current(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("grid_max_current", 15)
        assert cmd.address == 2214

    def test_ctrl_event_decode_all_off(self, el100v2_device):
        caps = el100v2_device.decode_ctrl_event(0)
        assert all(not v for v in caps.values())
        assert len(caps) == 11

    def test_ctrl_event_decode_partial(self, el100v2_device):
        caps = el100v2_device.decode_ctrl_event(0x0407)
        assert caps["power_control"]
        assert caps["ac_control"]
        assert caps["dc_control"]
        assert not caps["inv_control"]
        assert caps["super_power"]

    def test_ctrl_event_bits_defined(self, el100v2_device):
        bits = el100v2_device.ctrl_event_bits
        assert len(bits) == 11
        assert bits[0] == ("power_control", "power")

    def test_control_commands_merged_read(self, el100v2_device):
        cmds = el100v2_device.control_commands
        assert len(cmds) == 3
        addrs = {cmd.starting_address for cmd in cmds}
        assert 2060 not in addrs, "block 2060 read should be merged into 2000"
        assert 3035 not in addrs, "UPS mode read should be removed"
        assert 11000 in addrs, "IoT base info should be read"
        read_2000 = [c for c in cmds if c.starting_address == 2000]
        assert len(read_2000) == 1
        assert read_2000[0].quantity == 67
        read_2200 = [c for c in cmds if c.starting_address == 2200]
        assert len(read_2200) == 1
        assert read_2200[0].quantity == 18
        read_11000 = [c for c in cmds if c.starting_address == 11000]
        assert len(read_11000) == 1
        assert read_11000[0].quantity == 70

    def test_writable_ranges_excludes_ups(self, el100v2_device):
        ranges = el100v2_device.writable_ranges
        assert len(ranges) == 2
        assert not any(3035 in r for r in ranges), "UPS register 3035 should not be in writable_ranges"

    def test_no_ups_mode(self, el100v2_device):
        from voltkeeper.core.devices.el100v2 import El100V2

        assert "ups_mode" not in El100V2.WRITABLE_FIELD_NAMES
        assert not el100v2_device.has_field_setter("ups_mode")

    def test_iot_parsing(self, el100v2_device):
        """Parse known IoT response data."""
        from voltkeeper.core.devices.v2_base import (
            _iot_ascii_swapped,
            _iot_bit32,
            _iot_device_sn,
        )

        raw = _iot_response_bytes()
        assert len(raw) >= 38

        model = _iot_ascii_swapped(raw, 0, 12)
        assert model == "IOT"

        sn = _iot_device_sn(raw, 12, 8)
        assert sn == "2542016273527"

        sw_ver = _iot_bit32(raw, 28)
        assert sw_ver == 802411

        rf_ver = _iot_bit32(raw, 32)
        assert rf_ver == 0

        status = _u16(raw, 36)
        assert status & 0x04  # ble_status = 1

        # Parse full response through _parse_iot_info
        result = el100v2_device._parse_iot_info(raw)
        assert result["iot_model"] == "IOT"
        assert result["iot_sn"] == "2542016273527"
        assert result["iot_software_ver"] == 802411
        assert result["iot_rf_ver"] == 0
        assert result["ble_status"] is True
        assert result["mqtt_status"] is False

    def test_iot_no_response(self, el100v2_device):
        """Short response returns empty dict."""
        result = el100v2_device._parse_iot_info(b"")
        assert result == {}

        result = el100v2_device._parse_iot_info(b"\x00" * 10)
        assert result == {}
