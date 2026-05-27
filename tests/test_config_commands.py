# ABOUTME: Unit tests for voltkeeper config CLI subcommands — show, set, add-device, remove-device.
# ABOUTME: Tests config file read/write and daemon reload behavior without requiring a running daemon.

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from voltkeeper.cli import cli
from voltkeeper.config import Config, DeviceEntry, ServerConfig, write_config


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = Config(
        server=ServerConfig(api_key="secret-key-abcdef", host="127.0.0.1", port=8080),
        devices=[DeviceEntry(address="AA:BB:CC:DD:EE:FF", name="Living Room")],
    )
    write_config(cfg, path)
    return path


def _run(args, config_path=None, home=None):
    runner = CliRunner()
    patches = []
    if config_path is not None:
        patches.append(patch("voltkeeper.cli.load_config", return_value=_load(config_path)))
        patches.append(patch("voltkeeper.config.load_config", return_value=_load(config_path)))
    if home is not None:
        patches.append(
            patch("voltkeeper.config._xdg_config_path", return_value=home / ".config" / "voltkeeper" / "config.yaml")
        )
        patches.append(
            patch(
                "voltkeeper.cli.find_writable_config_path",
                return_value=home / ".config" / "voltkeeper" / "config.yaml",
                create=True,
            )
        )

    # Always suppress daemon reload to avoid network calls
    patches.append(patch("voltkeeper.cli._try_reload_daemon"))

    [p.start() for p in patches]
    try:
        result = runner.invoke(cli, args)
    finally:
        for p in patches:
            p.stop()
    return result


def _load(path):
    from voltkeeper.config import load_config

    return load_config(path)


class TestConfigShow:
    def test_shows_config_path(self, config_file):
        runner = CliRunner()
        with patch("voltkeeper.config._find_config", return_value=config_file):
            result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert str(config_file) in result.output

    def test_masks_api_key(self, config_file):
        runner = CliRunner()
        with patch("voltkeeper.config._find_config", return_value=config_file):
            result = runner.invoke(cli, ["config", "show"])
        assert "secret-key-abcdef" not in result.output
        assert "secr..." in result.output

    def test_shows_device_list(self, config_file):
        runner = CliRunner()
        with patch("voltkeeper.config._find_config", return_value=config_file):
            result = runner.invoke(cli, ["config", "show"])
        assert "AA:BB:CC:DD:EE:FF" in result.output

    def test_exits_nonzero_when_no_config(self, tmp_path):
        runner = CliRunner()
        with patch("voltkeeper.config._find_config", side_effect=SystemExit(1)):
            result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code != 0


class TestConfigSet:
    def test_set_scan_interval(self, config_file, tmp_path):
        from voltkeeper.config import load_config

        runner = CliRunner()
        with (
            patch("voltkeeper.cli.load_config", return_value=_load(config_file)),
            patch("voltkeeper.cli.find_writable_config_path", return_value=config_file, create=True),
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "set", "scan.interval", "90"])

        assert result.exit_code == 0, result.output
        reloaded = load_config(config_file)
        assert reloaded.scan.interval == 90

    def test_set_invalid_key_exits_nonzero(self, config_file):
        runner = CliRunner()
        with (
            patch("voltkeeper.cli.load_config", return_value=_load(config_file)),
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "set", "unknown.key", "val"])
        assert result.exit_code != 0
        assert "Unknown key" in result.output

    def test_set_restart_required_key_prints_notice(self, config_file):
        runner = CliRunner()
        with (
            patch("voltkeeper.cli.load_config", return_value=_load(config_file)),
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon", wraps=lambda url, req, key: None) as mock_reload,
        ):
            result = runner.invoke(cli, ["config", "set", "server.port", "9090"])

        assert result.exit_code == 0, result.output
        # _try_reload_daemon called with restart_required=True
        assert mock_reload.called
        assert mock_reload.call_args[0][1] is True  # restart_required positional arg


class TestConfigAddDevice:
    def test_add_new_device(self, config_file):
        from voltkeeper.config import load_config

        runner = CliRunner()
        with (
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "add-device", "11:22:33:44:55:66", "--name", "Garage"])

        assert result.exit_code == 0, result.output
        reloaded = load_config(config_file)
        assert any(d.address == "11:22:33:44:55:66" for d in reloaded.devices)
        assert any(d.name == "Garage" for d in reloaded.devices)

    def test_add_normalizes_address_to_uppercase(self, config_file):
        from voltkeeper.config import load_config

        runner = CliRunner()
        with (
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "add-device", "aa:bb:cc:dd:ee:01"])

        assert result.exit_code == 0, result.output
        reloaded = load_config(config_file)
        assert any(d.address == "AA:BB:CC:DD:EE:01" for d in reloaded.devices)

    def test_add_duplicate_is_noop(self, config_file):
        from voltkeeper.config import load_config

        runner = CliRunner()
        with (
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "add-device", "AA:BB:CC:DD:EE:FF"])

        assert result.exit_code == 0
        assert "already in config" in result.output
        reloaded = load_config(config_file)
        assert sum(1 for d in reloaded.devices if d.address == "AA:BB:CC:DD:EE:FF") == 1


class TestConfigRemoveDevice:
    def test_remove_existing_device(self, config_file):
        from voltkeeper.config import load_config

        runner = CliRunner()
        with (
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "remove-device", "AA:BB:CC:DD:EE:FF"])

        assert result.exit_code == 0, result.output
        reloaded = load_config(config_file)
        assert not any(d.address == "AA:BB:CC:DD:EE:FF" for d in reloaded.devices)

    def test_remove_missing_device_is_noop(self, config_file):
        runner = CliRunner()
        with (
            patch("voltkeeper.config.find_writable_config_path", return_value=config_file),
            patch("voltkeeper.cli._try_reload_daemon"),
        ):
            result = runner.invoke(cli, ["config", "remove-device", "99:88:77:66:55:44"])

        assert result.exit_code == 0
        assert "not found" in result.output
