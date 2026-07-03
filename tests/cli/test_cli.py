# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


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
