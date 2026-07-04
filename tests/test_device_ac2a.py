# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

from decimal import Decimal

import pytest

from voltkeeper.core.devices.ac2a import AC2A, ChargingMode


class TestParseHomeData:
    def test_empty_data(self, ac2a_device):
        assert ac2a_device.parse(100, b"") == {}
        result = ac2a_device.parse(100, b"\x00" * 4)
        assert "packTotalVoltage" in result
        assert "packTotalCurrent" in result
        assert len(result) == 2

    def test_battery_fields_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "packTotalVoltage" in result
        assert "packTotalCurrent" in result
        assert "packTotalSoc" in result
        assert "packChargingStatus" in result
        assert 20 <= result["packTotalVoltage"] <= 40
        assert 0 <= result["packTotalCurrent"] <= 100
        assert 0 <= result["packTotalSoc"] <= 100
        assert result["packChargingStatus"] in (0, 1, 2, 3)

    def test_model_name_is_ac2a(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert result["deviceModel"].startswith("AC2A")

    def test_serial_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "deviceSN" in result
        assert len(result["deviceSN"]) > 0

    def test_power_meters_have_keys(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        for key in ("totalDCPower", "totalACPower", "totalPVPower", "totalGridPower"):
            assert key in result

    def test_energy_totals_have_keys(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        for key in (
            "totalDCEnergy",
            "totalACEnergy",
            "totalPVChargingEnergy",
            "totalGridChargingEnergy",
        ):
            assert key in result
            assert result[key] >= 0.0

    def test_status_fields_present(self, ac2a_device, ac2a_home_bytes):
        result = ac2a_device.parse(100, ac2a_home_bytes)
        assert "chargingMode" in result
        assert "invWorkingStatus" in result

    def test_short_data_only_basics(self, ac2a_device):
        data = b"\x0a\xaa\x00\x16\x00\x64\x00\x02\x01\x00\x01\x00"
        result = ac2a_device.parse(100, data)
        assert result["packTotalSoc"] == 100
        assert result["packTotalVoltage"] == Decimal("27.3")
        assert "deviceModel" not in result


class TestParseInvBaseInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1100, b"") == {}

    def test_inv_type(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result["invType"] == "AC2A"

    def test_inv_id(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result["invId"] == 0

    def test_software_versions_present(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        ver_keys = sorted(k for k in result if k.endswith("_version"))
        assert ver_keys == ["arm_version", "dsp_version"]
        # Entry 0: 00 01 2e 19 00 03 → mcu_type=1 (ARM), version=0x00032e19=208409
        assert result["arm_version"] == 208409
        # Entry 1: 00 02 34 54 00 03 → mcu_type=2 (DSP), version=0x00033454=210004
        assert result["dsp_version"] == 210004

    def test_temperatures_absent_when_sensor_off(self, ac2a_device, ac2a_inv_base_bytes):
        result = ac2a_device.parse(1100, ac2a_inv_base_bytes)
        assert result.get("ambientTemp") is None
        assert result.get("invMaxTemp") is None


class TestParseInvPvInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1200, b"") == {}

    def test_keys_present(self, ac2a_device, ac2a_inv_pv_bytes):
        result = ac2a_device.parse(1200, ac2a_inv_pv_bytes)
        assert "totalChgPower" in result
        assert "totalChgEnergy" in result


class TestParseInvGridInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1300, b"") == {}

    def test_frequency_in_range(self, ac2a_device, ac2a_inv_grid_bytes):
        result = ac2a_device.parse(1300, ac2a_inv_grid_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_device, ac2a_inv_grid_bytes):
        result = ac2a_device.parse(1300, ac2a_inv_grid_bytes)
        assert "gridPhase[0].voltage" in result
        assert "gridPhase[0].current" in result
        assert "gridPhase[0].power" in result


class TestParseInvLoadInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1400, b"") == {}

    def test_dc_keys_present(self, ac2a_device, ac2a_inv_load_bytes):
        result = ac2a_device.parse(1400, ac2a_inv_load_bytes)
        for key in ("dc5VPower", "dc12VPower", "dc24VPower"):
            assert key in result


class TestParseInvInvInfo:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(1500, b"") == {}

    def test_frequency_in_range(self, ac2a_device, ac2a_inv_inv_bytes):
        result = ac2a_device.parse(1500, ac2a_inv_inv_bytes)
        assert 45 <= result["frequency"] <= 65

    def test_phase1_keys_present(self, ac2a_device, ac2a_inv_inv_bytes):
        result = ac2a_device.parse(1500, ac2a_inv_inv_bytes)
        assert "invPhase[0].voltage" in result
        assert "invPhase[0].current" in result
        assert "invPhase[0].power" in result
        assert "invPhase[0].workStatus" in result


class TestParseControlData:
    def test_empty(self, ac2a_device):
        assert ac2a_device.parse(2000, b"") == {}

    def test_ac_output_on(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["ac_output"] is True

    def test_dc_output_off(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["dc_output"] is False

    def test_ac_eco_mode_on(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["ac_eco_mode"] is True

    def test_charging_mode_silent(self, ac2a_device, ac2a_control_bytes):
        from voltkeeper.core.devices.ac2a import ChargingMode

        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["charging_mode"] == ChargingMode.SILENT

    def test_sys_power_thresholds(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["sys_low_power"] == 20
        assert result["sys_high_power"] == 80

    def test_build_setter_ac_output_on(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("ac_output", True)
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_build_setter_dc_output_off(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_output", False)
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_build_setter_charging_mode_enum(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "TURBO")
        assert cmd.address == 2020
        assert cmd.value == 2

    def test_has_field_setter_writable(self, ac2a_device):
        assert ac2a_device.has_field_setter("ac_output") is True
        assert ac2a_device.has_field_setter("dc_output") is True
        assert ac2a_device.has_field_setter("charging_mode") is True

    def test_has_field_setter_read_only(self, ac2a_device):
        assert ac2a_device.has_field_setter("packTotalSoc") is False
        assert ac2a_device.has_field_setter("totalACPower") is False

    def test_working_mode_parse_raw(self, ac2a_device, ac2a_control_bytes):
        result = ac2a_device.parse(2000, ac2a_control_bytes)
        assert result["working_mode"] == 0

    def test_working_mode_build_setter_enum(self, ac2a_device):
        from voltkeeper.core.commands import WorkingMode

        cmd = ac2a_device.build_setter_command("working_mode", WorkingMode.STANDARD_UPS)
        assert cmd.address == 2005
        assert cmd.value == 3

    def test_working_mode_build_setter_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("working_mode", "PV_PRIORITY_UPS")
        assert cmd.address == 2005
        assert cmd.value == 2

    def test_working_mode_build_setter_lowercase(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("working_mode", "customized_ups")
        assert cmd.address == 2005
        assert cmd.value == 1

    def test_working_mode_enum_values(self):
        from voltkeeper.core.commands import WorkingMode

        assert WorkingMode.CUSTOMIZED_UPS.value == 1
        assert WorkingMode.PV_PRIORITY_UPS.value == 2
        assert WorkingMode.STANDARD_UPS.value == 3
        assert WorkingMode.TIME_CTRL_UPS.value == 4
        assert WorkingMode.V2_TIME_CTRL_UPS.value == 5
        assert WorkingMode.SELF_CONSUMPTION_EXPORT.value == 11

    def test_build_setter_eco_time_suffixed(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_auto_off_time", "2h")
        assert cmd.address == 2015
        assert cmd.value == 2

    def test_build_setter_eco_time_bare(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_auto_off_time", "2")
        assert cmd.address == 2015
        assert cmd.value == 2

    def test_build_setter_eco_power_suffixed(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_eco_power", "150W")
        assert cmd.address == 2016
        assert cmd.value == 150

    def test_build_setter_eco_power_wrong_case_suffix_raises(self, ac2a_device):
        import pytest as _pytest

        with _pytest.raises((ValueError, TypeError)):
            ac2a_device.build_setter_command("dc_eco_auto_off_time", "2H")


class TestCtrlEvent:
    def test_all_off(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0)
        assert all(not v for v in caps.values())
        assert len(caps) == 11

    def test_all_on(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0x07FF)
        assert all(caps.values())

    def test_partial_bits(self, ac2a_device):
        caps = ac2a_device.decode_ctrl_event(0x0407)
        assert caps["power_control"]
        assert caps["ac_control"]
        assert caps["dc_control"]
        assert not caps["inv_control"]
        assert caps["super_power"]


class TestAC2AWritableFields:
    def test_writable_fields_known(self, ac2a_device):
        for field in AC2A.WRITABLE_FIELD_NAMES:
            assert ac2a_device.has_field_setter(field), f"{field} should be writable"

    def test_readonly_fields_not_writable(self, ac2a_device):
        assert not ac2a_device.has_field_setter("packTotalSoc")
        assert not ac2a_device.has_field_setter("deviceModel")
        assert not ac2a_device.has_field_setter("totalDCPower")

    def test_unknown_field_rejected(self, ac2a_device):
        with pytest.raises(ValueError, match="Unknown writable field"):
            ac2a_device.build_setter_command("nonexistent", "on")

    def test_bool_true_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("ac_output", "on")
        assert cmd.address == 2011
        assert cmd.value == 1

    def test_bool_false_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("dc_output", "off")
        assert cmd.address == 2012
        assert cmd.value == 0

    def test_bool_true_bool(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("power_lifting", True)
        assert cmd.address == 2021
        assert cmd.value == 1

    def test_bool_false_bool(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("power_lifting", False)
        assert cmd.value == 0

    def test_enum_string(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "turbo")
        assert cmd.address == 2020
        assert cmd.value == ChargingMode.TURBO.value

    def test_enum_string_case_insensitive(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("charging_mode", "SILENT")
        assert cmd.value == ChargingMode.SILENT.value

    def test_uint_value(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 50)
        assert cmd.address == 2022
        assert cmd.value == 50

    def test_control_struct_has_ctrl_event(self, ac2a_device):
        names = [f.name for f in ac2a_device.control_struct.fields]
        assert "ctrl_event" in names
        assert "ac_output" in names
        assert "charging_mode" in names


class TestRangeValidation:
    @pytest.fixture
    def ac2a_device(self):
        from voltkeeper.core.devices.ac2a import AC2A

        return AC2A("AA:BB:CC:DD:EE:FF", "2305000")

    def test_in_range_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 20)
        assert cmd.address == 2022
        assert cmd.value == 20

    def test_out_of_range_rejected(self, ac2a_device):
        with pytest.raises(ValueError, match="not in range"):
            ac2a_device.build_setter_command("sys_low_power", 150)

    def test_low_boundary_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 0)
        assert cmd.value == 0

    def test_high_boundary_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("sys_low_power", 100)
        assert cmd.value == 100

    def test_no_range_field_accepted(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("pv_adv_set", 9999)
        assert cmd.value == 9999

    def test_enum_field_not_range_checked(self, ac2a_device):
        cmd = ac2a_device.build_setter_command("inv_freq", "HZ_50")
        assert cmd.address == 2210
        assert cmd.value == 0
