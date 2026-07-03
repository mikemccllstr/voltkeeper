# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.devices.ac2a import ChargingMode
from voltkeeper.core.struct import UintField


class TestPrintVerboseControls:
    def test_unit_suffix_and_hint_rendered(self, ac2a_device):
        import unittest.mock as mock

        from voltkeeper.cli.status import _print_verbose

        home = {"packTotalSoc": 80, "packTotalVoltage": 25.6, "packTotalCurrent": 0.0}
        controls = {
            "ac_output": True,
            "dc_eco_auto_off_time": 2,
            "dc_eco_power": 150,
            "charging_mode": ChargingMode.TURBO,
            "sys_low_power": 20,
        }

        output_lines = []

        def fake_echo(msg="", **kw):
            output_lines.append(str(msg))

        with mock.patch("voltkeeper.cli.status.click.echo", side_effect=fake_echo):
            _print_verbose(ac2a_device, home, {}, {}, {}, {}, {}, controls)

        output = "\n".join(output_lines)
        assert "2h" in output
        assert "150W" in output
        assert "[on|off]" in output
        assert "[integer]h" in output
        assert "[integer]W" in output
        assert "[0-100]" in output


class TestFieldHint:
    def test_bool_field(self):
        from voltkeeper.cli.status import _field_hint
        from voltkeeper.core.struct import BoolField

        assert _field_hint(BoolField("ac_output", 2011)) == "[on|off]"

    def test_enum_field(self):
        from enum import Enum

        from voltkeeper.cli.status import _field_hint
        from voltkeeper.core.struct import EnumField

        class Mode(Enum):
            STANDARD = 0
            TURBO = 1

        assert _field_hint(EnumField("mode", 2020, Mode)) == "[standard|turbo]"

    def test_ranged_uint_no_unit(self):
        from voltkeeper.cli.status import _field_hint

        assert _field_hint(UintField("sys_low_power", 2022, range=(0, 100))) == "[0-100]"

    def test_ranged_uint_with_unit(self):
        from voltkeeper.cli.status import _field_hint

        assert _field_hint(UintField("dc_eco_power", 2016, unit="W")) == "[integer]W"

    def test_unranged_uint_no_unit(self):
        from voltkeeper.cli.status import _field_hint

        assert _field_hint(UintField("lcd_timeout", 2067)) == "[integer]"

    def test_unranged_uint_with_unit(self):
        from voltkeeper.cli.status import _field_hint

        assert _field_hint(UintField("dc_eco_auto_off_time", 2015, unit="h")) == "[integer]h"

    def test_other_field_type_returns_empty(self):
        from voltkeeper.cli.status import _field_hint
        from voltkeeper.core.struct import StringField

        assert _field_hint(StringField("deviceModel", 110, 8)) == ""


class TestPrintPowerSection:
    """Tests for the shared _print_power_section(home, indent, show_zeros) helper."""

    def _capture(self, home, indent, show_zeros):
        import unittest.mock as mock

        from voltkeeper.cli.status import _print_power_section

        lines = []

        def fake_echo(msg="", **kw):
            lines.append(str(msg))

        with mock.patch("voltkeeper.cli.status.click.echo", side_effect=fake_echo):
            _print_power_section(home, indent=indent, show_zeros=show_zeros)

        return "\n".join(lines)

    # 1.1 compact mode hides zero PV row
    def test_compact_hides_zero_pv_row(self):
        home = {
            "totalPVPower": 0,
            "totalACPower": 36,
            "totalDCPower": 18,
            "totalGridPower": 36,
        }
        output = self._capture(home, indent="  ", show_zeros=False)
        assert "PV" not in output

    # 1.2 compact mode shows non-zero battery (discharging) in IN
    def test_compact_shows_battery_discharging_in_in_section(self):
        # battery = ac + dc - pv - grid = 36 + 18 - 0 - 36 = 18 W (discharging)
        home = {
            "totalPVPower": 0,
            "totalACPower": 36,
            "totalDCPower": 18,
            "totalGridPower": 36,
        }
        output = self._capture(home, indent="  ", show_zeros=False)
        in_section = output.split("OUT")[0]
        assert "Battery" in in_section
        assert "discharging" in in_section

    # 1.3 compact mode shows grid export in OUT
    def test_compact_shows_grid_export_in_out_section(self):
        # grid = -300 → export
        home = {
            "totalPVPower": 500,
            "totalGridPower": -300,
            "totalACPower": 100,
            "totalDCPower": 50,
        }
        output = self._capture(home, indent="  ", show_zeros=False)
        out_section = output.split("OUT", 1)[1] if "OUT" in output else ""
        assert "Grid export" in out_section
        assert "300" in out_section

    # 1.4 compact mode shows battery (charging) in OUT
    def test_compact_shows_battery_charging_in_out_section(self):
        # battery = 100 + 50 - 500 - (-300) = -50 W (charging)
        home = {
            "totalPVPower": 500,
            "totalGridPower": -300,
            "totalACPower": 100,
            "totalDCPower": 50,
        }
        output = self._capture(home, indent="  ", show_zeros=False)
        out_section = output.split("OUT", 1)[1] if "OUT" in output else ""
        assert "Battery" in out_section
        assert "charging" in out_section

    # 1.5 verbose mode shows PV row even when 0 W
    def test_verbose_shows_zero_pv_row(self):
        home = {
            "totalPVPower": 0,
            "totalACPower": 36,
            "totalDCPower": 18,
            "totalGridPower": 36,
        }
        output = self._capture(home, indent="    ", show_zeros=True)
        assert "PV" in output

    # 1.6 IN Total and OUT Total match expected sums
    def test_in_and_out_totals_match_expected_sums(self):
        # grid=36, ac=36, dc=18, pv=0 → battery=18 (discharging)
        # IN: grid 36 + battery 18 = 54; OUT: ac 36 + dc 18 = 54
        home = {
            "totalPVPower": 0,
            "totalACPower": 36,
            "totalDCPower": 18,
            "totalGridPower": 36,
        }
        output = self._capture(home, indent="  ", show_zeros=False)
        # Both totals should show 54
        assert output.count("54") >= 2
