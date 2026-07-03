# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from click.testing import CliRunner

from voltkeeper.cli import cli


class TestMqttListenCLI:
    def test_requires_device_type_when_no_address(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--serial", "1234", "--broker", "x"])
        assert result.exit_code != 0
        assert "device-type" in result.output.lower()

    def test_validates_device_type(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen",
                "--serial",
                "1234",
                "--broker",
                "x",
                "--device-type",
                "INVALID",
            ],
        )
        assert result.exit_code != 0
        assert "INVALID" in result.output or "Unknown" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output
        assert "--broker" in result.output
        assert "--shutdown-at" in result.output
        assert "--grace-period" in result.output

    def test_requires_broker(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--serial", "12345"])
        assert result.exit_code != 0

    def test_requires_address_or_serial(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--broker", "x"])
        assert result.exit_code != 0
        assert "ADDRESS" in result.output or "serial" in result.output.lower()

    def test_default_shutdown_at(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen", "--help"])
        assert "10" in result.output

    def test_fails_on_non_linux_platform(self):
        import sys as _sys
        from unittest.mock import patch

        runner = CliRunner()
        with patch.object(_sys, "platform", "win32"):
            result = runner.invoke(cli, ["mqtt-listen", "--serial", "1234", "--broker", "x", "--device-type", "AC2A"])
        assert result.exit_code != 0
        assert "Linux" in result.output
