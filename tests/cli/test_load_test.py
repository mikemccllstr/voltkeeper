# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from click.testing import CliRunner

from voltkeeper.cli import cli


class TestLoadTestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["load-test", "--help"])
        assert result.exit_code == 0
        assert "load" in result.output.lower()
        assert "--interval" in result.output
        assert "--output" in result.output
        assert "--expected-load" in result.output
        assert "--phase" in result.output
        assert "ADDRESS" in result.output

    def test_rejects_short_interval(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "load-test",
                "AA:BB:CC:DD:EE:FF",
                "--interval",
                "5",
            ],
        )
        assert result.exit_code != 0
        assert "15" in result.output
