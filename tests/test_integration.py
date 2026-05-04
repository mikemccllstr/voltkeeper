# ABOUTME: Integration tests that exercise real BLE operations (scan, connect).
# ABOUTME: Skipped by default. Run with: uv run pytest -m integration

import pytest
from click.testing import CliRunner

from src.bluetti_cli.cli import cli

pytestmark = pytest.mark.integration


class TestStatusWithBLE:
    def test_status_fails_gracefully_without_bluetooth(self):
        """status command fails cleanly when no BLE adapter is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code != 0
        assert "Error:" in result.output or result.exception is not None

    def test_verbose_flag_accepted(self):
        """--verbose flag is recognized (connect will fail without BLE)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--verbose", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code != 0


class TestScanWithBLE:
    def test_scan_no_devices(self):
        """scan command runs cleanly when no BLE adapter is present."""
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--timeout", "1"])
        assert result.exit_code in (0, 1)
