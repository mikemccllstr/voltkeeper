# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from voltkeeper.cli import cli


class TestCli:
    def test_no_args_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Voltkeeper CLI, supporting Bluetti power station devices" in result.output
        assert "status" in result.output
        assert "scan" in result.output
        assert "write" in result.output

    def test_help_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "voltkeeper" in result.output

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.output
        assert "-v" in result.output
        assert "ADDRESS" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in result.output

    def test_write_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--help"])
        assert result.exit_code == 0
        assert "ADDRESS" in result.output
        assert "FIELD" in result.output
        assert "VALUE" in result.output


class TestWriteHelpField:
    """--help-field describes a writable field; FIELD and VALUE are not needed for it."""

    def _invoke(self, args):
        from voltkeeper.core.devices.ac2a import AC2A

        device = AC2A("AA:BB:CC:DD:EE:FF", "0")
        runner = CliRunner()
        with (
            patch("voltkeeper.cli.write.lookup_scan_result", new=AsyncMock(return_value=MagicMock())),
            patch("voltkeeper.cli.write._device_from_scan", return_value=device),
        ):
            return runner.invoke(cli, args)

    def test_help_field_needs_only_address(self):
        result = self._invoke(["write", "AA:BB:CC:DD:EE:FF", "--help-field", "charging_mode"])
        assert result.exit_code == 0
        assert "charging_mode: [standard|silent|turbo]" in result.output

    def test_help_field_range_has_no_unit_suffix(self):
        result = self._invoke(["write", "AA:BB:CC:DD:EE:FF", "--help-field", "sys_low_power"])
        assert result.exit_code == 0
        assert "sys_low_power: [0-100]" in result.output
        assert "%" not in result.output

    def test_write_without_help_field_requires_field_and_value(self):
        result = self._invoke(["write", "AA:BB:CC:DD:EE:FF", "ac_output"])
        assert result.exit_code != 0
        assert "FIELD" in result.output and "VALUE" in result.output
