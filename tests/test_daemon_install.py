# ABOUTME: Unit tests for `daemon install` and `daemon uninstall` CLI subcommands.
# ABOUTME: Tests install idempotency, --lan flag config, unit file generation, and uninstall cleanup.

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from voltkeeper.cli import cli


def _make_subprocess_ok():
    result = MagicMock()
    result.returncode = 0
    result.stdout = "inactive\n"
    result.stderr = ""
    return result


def _make_subprocess_active():
    result = MagicMock()
    result.returncode = 0
    result.stdout = "active\n"
    result.stderr = ""
    return result


class TestDaemonInstall:
    def test_first_install_writes_unit_file(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        unit_file = unit_dir / "voltkeeper.service"
        assert unit_file.exists()

    def test_first_install_unit_file_contains_exec_start(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        unit_file = unit_dir / "voltkeeper.service"
        content = unit_file.read_text()
        assert "ExecStart=/usr/local/bin/voltkeeperd" in content
        assert "WantedBy=default.target" in content
        assert "NoNewPrivileges=true" in content

    def test_first_install_runs_systemctl_commands(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)

        mock_run = MagicMock(return_value=_make_subprocess_ok())
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", mock_run),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        calls = [c[0][0] for c in mock_run.call_args_list]
        cmds = [" ".join(c) for c in calls]
        assert any("daemon-reload" in c for c in cmds)
        assert any("enable" in c for c in cmds)
        assert any("start" in c for c in cmds)

    def test_first_install_prints_summary(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        assert "voltkeeper" in result.output.lower()
        assert (
            "install" in result.output.lower()
            or "started" in result.output.lower()
            or "enabled" in result.output.lower()
        )

    def test_already_installed_is_idempotent(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        (unit_dir / "voltkeeper.service").write_text("[Unit]\n")

        mock_run = MagicMock(return_value=_make_subprocess_active())
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", mock_run),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        # Should not have run enable/start/daemon-reload
        calls = [c[0][0] for c in mock_run.call_args_list]
        cmds = [" ".join(c) for c in calls]
        assert not any("enable" in c for c in cmds)
        assert not any("start" in c for c in cmds)

    def test_already_installed_prints_status(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        (unit_dir / "voltkeeper.service").write_text("[Unit]\n")

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", return_value=_make_subprocess_active()),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code == 0, result.output
        assert "already" in result.output.lower() or "installed" in result.output.lower()

    def test_lan_flag_sets_host_and_mdns(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)

        written_configs = []

        def capture_write(config, path):
            written_configs.append(config)

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config", side_effect=capture_write),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install", "--lan"])

        assert result.exit_code == 0, result.output
        assert written_configs, "write_config was not called"
        cfg = written_configs[0]
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.mdns is True

    def test_lan_flag_prints_api_key_security_note(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/voltkeeperd"),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
            patch("voltkeeper.cli.load_config", side_effect=SystemExit(1)),
            patch(
                "voltkeeper.config.find_writable_config_path",
                return_value=tmp_path / ".config" / "voltkeeper" / "config.yaml",
            ),
            patch("voltkeeper.cli.write_config"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install", "--lan"])

        assert result.exit_code == 0, result.output
        assert "api" in result.output.lower() or "key" in result.output.lower()

    def test_missing_voltkeeperd_binary_exits_nonzero(self, tmp_path):
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value=None),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "install"])

        assert result.exit_code != 0


class TestDaemonUninstall:
    def test_uninstall_removes_unit_file(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        unit_file = unit_dir / "voltkeeper.service"
        unit_file.write_text("[Unit]\n")

        mock_run = MagicMock(return_value=_make_subprocess_ok())
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", mock_run),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "uninstall"], input="y\n")

        assert result.exit_code == 0, result.output
        assert not unit_file.exists()

    def test_uninstall_runs_stop_disable_reload(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        (unit_dir / "voltkeeper.service").write_text("[Unit]\n")

        mock_run = MagicMock(return_value=_make_subprocess_ok())
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", mock_run),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "uninstall"], input="y\n")

        assert result.exit_code == 0, result.output
        calls = [c[0][0] for c in mock_run.call_args_list]
        cmds = [" ".join(c) for c in calls]
        assert any("stop" in c for c in cmds)
        assert any("disable" in c for c in cmds)
        assert any("daemon-reload" in c for c in cmds)

    def test_uninstall_noop_when_not_installed(self, tmp_path):
        mock_run = MagicMock(return_value=_make_subprocess_ok())
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", mock_run),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["daemon", "uninstall"])

        assert result.exit_code == 0
        assert "not installed" in result.output.lower()
        mock_run.assert_not_called()

    def test_uninstall_prompts_for_confirmation(self, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        unit_file = unit_dir / "voltkeeper.service"
        unit_file.write_text("[Unit]\n")

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("subprocess.run", return_value=_make_subprocess_ok()),
        ):
            runner = CliRunner()
            # Answer "n" to confirmation
            result = runner.invoke(cli, ["daemon", "uninstall"], input="n\n")

        assert result.exit_code == 0
        assert unit_file.exists()  # should NOT have been removed
