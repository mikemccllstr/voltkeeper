# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from click.testing import CliRunner

from voltkeeper.cli import cli


class TestMqttPublishService:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish-service", "--help"])
        assert result.exit_code == 0
        assert "--broker" in result.output
        assert "--user" in result.output
        assert "--port" in result.output
        assert "--output" in result.output
        assert "ADDRESS" in result.output

    def test_missing_broker_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish-service", "AC2A0000000"])
        assert result.exit_code != 0
        assert "broker" in result.output.lower()

    def test_generates_service_sections(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "192.168.1.100",
            ],
        )
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "WantedBy=multi-user.target" in output
        assert "Restart=always" in output

    def test_exec_start_contains_address_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "10.0.0.1",
            ],
        )
        assert result.exit_code == 0
        assert "AC2A0000000" in result.output
        assert "--broker 10.0.0.1" in result.output

    def test_respects_user_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--user",
                "root",
            ],
        )
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_port_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--port",
                "8883",
            ],
        )
        assert result.exit_code == 0
        assert "--port 8883" in result.output

    def test_respects_interval_option(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--interval",
                "30",
            ],
        )
        assert result.exit_code == 0
        assert "--interval 30" in result.output

    def test_respects_username_password(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--username",
                "mqttuser",
                "--password",
                "s3cret",
            ],
        )
        assert result.exit_code == 0
        assert "--username mqttuser" in result.output
        assert "--password 's3cret'" in result.output

    def test_respects_ha_config(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--ha-config",
                "none",
            ],
        )
        assert result.exit_code == 0
        assert "--ha-config none" in result.output

    def test_output_to_file(self, tmp_path):
        out = tmp_path / "test.service"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        content = out.read_text()
        assert "[Unit]" in content
        assert "[Service]" in content

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_exec_override(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--exec",
                "/usr/local/bin/voltkeeper",
            ],
        )
        assert result.exit_code == 0
        assert "ExecStart=/usr/local/bin/voltkeeper" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_restart_always_in_service(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "Restart=always" in result.output

    def test_restart_flag_in_mqtt_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-publish", "--help"])
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_publish_service_includes_serial(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-publish-service",
                "AC2A0000000",
                "--broker",
                "x",
                "--serial",
                "MYSERIAL",
            ],
        )
        assert result.exit_code == 0
        assert "--serial MYSERIAL" in result.output


class TestMqttListenService:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["mqtt-listen-service", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output
        assert "--shutdown-at" in result.output

    def test_generates_service_sections(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "12345",
                "--broker",
                "192.168.1.100",
            ],
        )
        assert result.exit_code == 0
        output = result.output
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "Restart=always" in output

    def test_execstart_has_serial_and_broker(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "SN123",
                "--broker",
                "10.0.0.1",
            ],
        )
        assert result.exit_code == 0
        assert "--serial SN123" in result.output
        assert "--broker 10.0.0.1" in result.output
        assert "mqtt-listen" in result.output

    def test_user_is_root_by_default(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "User=root" in result.output

    def test_respects_shutdown_at(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
                "--shutdown-at",
                "20",
            ],
        )
        assert result.exit_code == 0
        assert "--shutdown-at 20" in result.output

    def test_respects_grace_period(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
                "--grace-period",
                "120",
            ],
        )
        assert result.exit_code == 0
        assert "--grace-period 120" in result.output

    def test_restart_on_source_change_in_execstart(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "--restart-on-source-change" in result.output

    def test_install_instructions_in_comments(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "x",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "systemctl daemon-reload" in result.output
        assert "systemctl enable" in result.output

    def test_service_name_uses_serial(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--serial",
                "DEADBEEF",
                "--broker",
                "x",
            ],
        )
        assert result.exit_code == 0
        assert "voltkeeper-shutdown-DEADBEEF" in result.output

    def test_no_address_argument(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "mqtt-listen-service",
                "--help",
            ],
        )
        assert result.exit_code == 0
        assert "ADDRESS" not in result.output
