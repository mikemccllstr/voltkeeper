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


# ── Array parsing tests (Group 1.1 — should fail until V2Base gains helpers) ──


class TestV2ArrayParsingOnEl100V2:
    """Verify El100V2 gets array keys once helpers move to V2Base."""

    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    def _inv_base_with_versions(self) -> bytes:
        """INV_BASE_INFO payload with 2 firmware entries (ARM, DSP) at bytes 26-37."""
        buf = bytearray(102)
        buf[0:2] = b"\x00\x00"
        buf[2:12] = b"EL100V2\x00\x00\x00"
        buf[12:20] = b"\x1c\x77\xdb\xfa\x02\x4f\x00\x00"
        buf[26:32] = bytes([0x00, 0x01, 0x2E, 0x19, 0x00, 0x03])
        buf[32:38] = bytes([0x00, 0x02, 0x34, 0x54, 0x00, 0x03])
        return bytes(buf)

    def test_software_versions_from_inv_base(self, el100v2_device):
        data = self._inv_base_with_versions()
        result = el100v2_device.parse(1100, data)
        assert result["arm_version"] == 208409
        assert result["dsp_version"] == 210004

    def test_empty_version_entry_skipped(self, el100v2_device):
        buf = bytearray(102)
        buf[0:2] = b"\x00\x00"
        buf[26:32] = b"\x00\x00\x00\x00\x00\x00"
        data = bytes(buf)
        result = el100v2_device.parse(1100, data)
        ver_keys = [k for k in result if k.endswith("_version")]
        assert ver_keys == []

    def test_short_inv_base_truncates_safely(self, el100v2_device):
        data = bytes(30)
        result = el100v2_device.parse(1100, data)
        ver_keys = [k for k in result if k.endswith("_version")]
        assert ver_keys == []

    def _inv_pv_with_one_string(self) -> bytes:
        """INV_PV_INFO payload reporting 1 DC PV string."""
        buf = bytearray(140)
        buf[0:2] = b"\x00\x00"
        buf[18:20] = bytes([0x00, 0x01])  # acPvNumber=0, dcPvNumber=1 at register 1209
        buf[20:36] = bytes(
            [0x00, 0x01, 0x00, 0x02, 0x00, 0x50, 0x00, 0x96, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        return bytes(buf)

    def test_pv_strings_from_inv_pv(self, el100v2_device):
        data = self._inv_pv_with_one_string()
        result = el100v2_device.parse(1200, data)
        assert result["pv[0].workingStatus"] == 1
        assert result["pv[0].type"] == 2
        assert result["pv[0].inputPower"] == 80
        assert result["pv[0].inputVoltage"] == 15.0
        assert result["pv[0].inputCurrent"] == 4.0

    def test_short_pv_payload_truncates_safely(self, el100v2_device):
        buf = bytearray(20)
        buf[0:2] = b"\x00\x01"
        buf[2:4] = b"\x00\x00"
        data = bytes(buf)
        result = el100v2_device.parse(1200, data)
        pv_keys = [k for k in result if k.startswith("pv[")]
        assert pv_keys == []

    def _inv_grid_with_one_phase(self) -> bytes:
        """INV_GRID_INFO payload with sysPhaseNumber=1 at register 1312 (byte offset 24)."""
        buf = bytearray(62)
        buf[24:26] = b"\x00\x01"  # sysPhaseNumber=1
        buf[26:38] = bytes([0xFF, 0xEC, 0x00, 0x96, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return bytes(buf)

    def test_grid_phases_from_inv_grid(self, el100v2_device):
        data = self._inv_grid_with_one_phase()
        result = el100v2_device.parse(1300, data)
        assert result["gridPhase[0].power"] == 20
        assert result["gridPhase[0].voltage"] == 15.0
        assert result["gridPhase[0].current"] == 4.0

    def test_short_grid_payload_truncates_safely(self, el100v2_device):
        data = bytes(26)
        result = el100v2_device.parse(1300, data)
        grid_keys = [k for k in result if k.startswith("gridPhase[")]
        assert grid_keys == []

    def _inv_load_with_one_phase(self) -> bytes:
        """INV_LOAD_INFO payload with sysPhaseNumber=1 at register 1429 (byte offset 58)."""
        buf = bytearray(96)
        buf[58:60] = b"\x00\x01"  # sysPhaseNumber=1
        buf[60:72] = bytes([0x00, 0x64, 0x00, 0x96, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        return bytes(buf)

    def test_load_phases_from_inv_load(self, el100v2_device):
        data = self._inv_load_with_one_phase()
        result = el100v2_device.parse(1400, data)
        assert result["acPhase[0].power"] == 100
        assert result["acPhase[0].voltage"] == 15.0
        assert result["acPhase[0].current"] == 4.0

    def test_short_load_payload_truncates_safely(self, el100v2_device):
        data = bytes(60)
        result = el100v2_device.parse(1400, data)
        load_keys = [k for k in result if k.startswith("acPhase[")]
        assert load_keys == []

    def _inv_inv_with_one_phase(self) -> bytes:
        """INV_INV_INFO payload with sysPhaseNumber=1 at register 1508 (byte offset 16)."""
        buf = bytearray(60)
        buf[16:18] = b"\x00\x01"  # sysPhaseNumber=1
        buf[18:30] = bytes([0x00, 0x02, 0x00, 0x64, 0x00, 0x96, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00])
        return bytes(buf)

    def test_inv_phases_from_inv_inv(self, el100v2_device):
        data = self._inv_inv_with_one_phase()
        result = el100v2_device.parse(1500, data)
        assert result["invPhase[0].workStatus"] == 2
        assert result["invPhase[0].power"] == 100
        assert result["invPhase[0].voltage"] == 15.0
        assert result["invPhase[0].current"] == 4.0

    def test_short_inv_payload_truncates_safely(self, el100v2_device):
        data = bytes(18)
        result = el100v2_device.parse(1500, data)
        inv_keys = [k for k in result if k.startswith("invPhase[")]
        assert inv_keys == []


# ── Control surface tests (Group 2.1 — should fail until fields removed) ──────


class TestEl100V2RemovedFields:
    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_sys_low_power_not_writable(self, el100v2_device):
        assert not el100v2_device.has_field_setter("sys_low_power")

    def test_sys_high_power_not_writable(self, el100v2_device):
        assert not el100v2_device.has_field_setter("sys_high_power")

    def test_led_color_not_writable(self, el100v2_device):
        assert not el100v2_device.has_field_setter("led_color")

    def test_ctrl_led_still_writable(self, el100v2_device):
        assert el100v2_device.has_field_setter("ctrl_led")

    def test_no_field_at_sys_low_power_register(self, el100v2_device):
        names = [f.name for f in el100v2_device.control_struct.fields if f.address == 2022]
        assert names == []

    def test_no_field_at_sys_high_power_register(self, el100v2_device):
        names = [f.name for f in el100v2_device.control_struct.fields if f.address == 2023]
        assert names == []

    def test_no_field_at_led_color_register(self, el100v2_device):
        names = [f.name for f in el100v2_device.control_struct.fields if f.address == 2078]
        assert names == []

    def test_fields_not_in_writable_field_names(self, el100v2_device):
        from voltkeeper.core.devices.el100v2 import El100V2

        assert "sys_low_power" not in El100V2.WRITABLE_FIELD_NAMES
        assert "sys_high_power" not in El100V2.WRITABLE_FIELD_NAMES
        assert "led_color" not in El100V2.WRITABLE_FIELD_NAMES


# ── Custom charging mode and grid_max_current tests (Group 2.2) ───────────────


class TestEl100V2CustomChargingMode:
    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    def test_custom_charging_mode_available(self, el100v2_device):
        from voltkeeper.core.devices.el100v2 import ChargingMode

        assert hasattr(ChargingMode, "CUSTOM")
        assert ChargingMode.CUSTOM.value == 4

    def test_build_setter_charging_mode_custom(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("charging_mode", "CUSTOM")
        assert cmd.address == 2020
        assert cmd.value == 4

    def test_build_setter_charging_mode_custom_lowercase(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("charging_mode", "custom")
        assert cmd.address == 2020
        assert cmd.value == 4

    def test_grid_max_current_range_accepts_1(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("grid_max_current", 1)
        assert cmd.address == 2214
        assert cmd.value == 1

    def test_grid_max_current_range_accepts_15(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("grid_max_current", 15)
        assert cmd.address == 2214
        assert cmd.value == 15

    def test_grid_max_current_range_accepts_0(self, el100v2_device):
        cmd = el100v2_device.build_setter_command("grid_max_current", 0)
        assert cmd.address == 2214
        assert cmd.value == 0

    def test_grid_max_current_range_rejects_16(self, el100v2_device):
        with pytest.raises(ValueError, match="not in range"):
            el100v2_device.build_setter_command("grid_max_current", 16)


class TestEl100V2EcoRanges:
    """ECO field ranges established on hardware (verify-EL100V2-2026-07-03):
    app ECO settings screen and tier-3 probe results agree."""

    @pytest.fixture
    def el100v2_device(self):
        from voltkeeper.core.devices.el100v2 import El100V2

        return El100V2("AA:BB:CC:DD:EE:FF", "2305000")

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("ac_eco_power", 10),
            ("ac_eco_power", 40),
            ("dc_eco_power", 5),
            ("dc_eco_power", 20),
            ("ac_eco_auto_off_time", 1),
            ("ac_eco_auto_off_time", 4),
            ("dc_eco_auto_off_time", 1),
            ("dc_eco_auto_off_time", 4),
        ],
    )
    def test_eco_range_accepts_bounds(self, el100v2_device, field, value):
        cmd = el100v2_device.build_setter_command(field, value)
        assert cmd.value == value

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("ac_eco_power", 9),
            ("ac_eco_power", 41),
            ("dc_eco_power", 4),
            ("dc_eco_power", 21),
            ("ac_eco_auto_off_time", 0),
            ("ac_eco_auto_off_time", 5),
            ("dc_eco_auto_off_time", 0),
            ("dc_eco_auto_off_time", 5),
        ],
    )
    def test_eco_range_rejects_out_of_range(self, el100v2_device, field, value):
        with pytest.raises(ValueError, match="not in range"):
            el100v2_device.build_setter_command(field, value)
