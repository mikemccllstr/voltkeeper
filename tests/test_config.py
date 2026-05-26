# ABOUTME: Unit tests for config loading — valid config, missing file, invalid YAML, missing fields.

from pathlib import Path

import pytest

from voltkeeper.config import (
    Config,
    DeviceEntry,
    ScanConfig,
    ServerConfig,
    load_config,
    write_config,
)


def _write_config(tmpdir: Path, content: str) -> Path:
    p = tmpdir / "config.yaml"
    p.write_text(content)
    return p


class TestLoadConfig:
    def test_valid_minimal_config(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "test-key-123"
""",
        )
        config = load_config(config_path)
        assert isinstance(config, Config)
        assert config.server.api_key == "test-key-123"
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 8080
        assert config.devices == []
        assert config.scan.interval == 60
        assert config.shutdown_watchdog.enabled is False

    def test_full_config(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  host: "127.0.0.1"
  port: 9090
  api_key: "secret"
  allowed_networks: ["192.168.1.0/24", "10.0.0.0/8"]
  interface: "eth0"

devices:
  - address: "AA:BB:CC:DD:EE:FF"
    name: "Living Room AC2A"
  - address: "11:22:33:44:55:66"

scan:
  interval: 30
  timeout: 5.0

shutdown_watchdog:
  enabled: true
  device: "AA:BB:CC:DD:EE:FF"
  soc_threshold: 15
  grace_period: 120
""",
        )
        config = load_config(config_path)

        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9090
        assert config.server.api_key == "secret"
        assert config.server.allowed_networks == ["192.168.1.0/24", "10.0.0.0/8"]
        assert config.server.interface == "eth0"
        assert len(config.server.normalized_networks()) == 2

        assert len(config.devices) == 2
        assert config.devices[0].address == "AA:BB:CC:DD:EE:FF"
        assert config.devices[0].name == "Living Room AC2A"
        assert config.devices[1].address == "11:22:33:44:55:66"
        assert config.devices[1].name is None

        assert config.scan.interval == 30
        assert config.scan.timeout == 5.0

        assert config.shutdown_watchdog.enabled is True
        assert config.shutdown_watchdog.device == "AA:BB:CC:DD:EE:FF"
        assert config.shutdown_watchdog.soc_threshold == 15
        assert config.shutdown_watchdog.grace_period == 120

    def test_missing_api_key(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  host: "0.0.0.0"
""",
        )
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_missing_file_explicit_path(self, tmp_path):
        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(SystemExit):
            load_config(nonexistent)

    def test_invalid_yaml(self, tmp_path):
        config_path = _write_config(tmp_path, "not: valid: yaml: [")
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_empty_file(self, tmp_path):
        config_path = _write_config(tmp_path, "")
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_config_not_a_mapping(self, tmp_path):
        config_path = _write_config(tmp_path, "- list item\n- another")
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_invalid_port(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
  port: 99999
""",
        )
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_invalid_cidr(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
  allowed_networks: ["not-a-cidr"]
""",
        )
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_devices_not_a_list(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
devices: "not-a-list"
""",
        )
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_device_missing_address(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
devices:
  - name: "No Address Device"
""",
        )
        with pytest.raises(SystemExit):
            load_config(config_path)

    def test_empty_devices_ok(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
devices: []
""",
        )
        config = load_config(config_path)
        assert config.devices == []

    def test_ipv6_cidr(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
  allowed_networks: ["::1/128"]
""",
        )
        config = load_config(config_path)
        nets = config.server.normalized_networks()
        assert len(nets) == 1

    def test_default_config_values(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            """server:
  api_key: "key"
devices:
  - address: "AA:BB:CC:DD:EE:FF"
""",
        )
        config = load_config(config_path)
        assert config.scan.interval == 60
        assert config.scan.timeout == 10.0
        assert config.shutdown_watchdog.enabled is False
        assert config.shutdown_watchdog.soc_threshold == 10
        assert config.shutdown_watchdog.grace_period == 60


class TestConfigDataclasses:
    def test_server_config_defaults(self):
        s = ServerConfig(api_key="test")
        assert s.host == "127.0.0.1"
        assert s.port == 8080
        assert s.allowed_networks == []
        assert s.interface is None
        assert s.mdns is False

    def test_device_entry_without_name(self):
        d = DeviceEntry(address="AA:BB:CC:DD:EE:FF")
        assert d.address == "AA:BB:CC:DD:EE:FF"
        assert d.name is None

    def test_normalized_networks_empty(self):
        s = ServerConfig(api_key="test")
        assert s.normalized_networks() == []

    def test_normalized_networks_invalid_raises(self):
        s = ServerConfig(api_key="test", allowed_networks=["not-cidr"])
        with pytest.raises(ValueError):
            s.normalized_networks()


class TestWriteConfig:
    def test_write_and_reload(self, tmp_path):
        path = tmp_path / "config.yaml"
        config = Config(
            server=ServerConfig(api_key="mykey", host="0.0.0.0", port=9090),
            devices=[DeviceEntry(address="AA:BB:CC:DD:EE:FF", name="Test")],
            scan=ScanConfig(interval=30, timeout=5.0),
        )
        write_config(config, path)
        reloaded = load_config(path)
        assert reloaded.server.api_key == "mykey"
        assert reloaded.server.host == "0.0.0.0"
        assert reloaded.server.port == 9090
        assert len(reloaded.devices) == 1
        assert reloaded.devices[0].address == "AA:BB:CC:DD:EE:FF"
        assert reloaded.devices[0].name == "Test"
        assert reloaded.scan.interval == 30
        assert reloaded.scan.timeout == 5.0

    def test_comment_preservation(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(
            "# My voltkeeper config\n"
            "server:\n"
            "  api_key: oldkey  # keep this\n"
            "  host: 127.0.0.1\n"
            "  port: 8080\n"
            "devices: []\n"
            "scan:\n"
            "  interval: 60\n"
            "  timeout: 10.0\n"
        )
        config = load_config(path)
        config.scan.interval = 120
        write_config(config, path)
        written = path.read_text()
        assert "# My voltkeeper config" in written
        assert "# keep this" in written
        assert "120" in written

    def test_write_creates_file(self, tmp_path):
        path = tmp_path / "new.yaml"
        config = Config(server=ServerConfig(api_key="k"))
        write_config(config, path)
        assert path.exists()
        reloaded = load_config(path)
        assert reloaded.server.api_key == "k"

    def test_write_mdns_true(self, tmp_path):
        path = tmp_path / "config.yaml"
        config = Config(server=ServerConfig(api_key="k", host="0.0.0.0", mdns=True))
        write_config(config, path)
        reloaded = load_config(path)
        assert reloaded.server.mdns is True

    def test_write_mdns_false_omits_key(self, tmp_path):
        path = tmp_path / "config.yaml"
        config = Config(server=ServerConfig(api_key="k"))
        write_config(config, path)
        text = path.read_text()
        assert "mdns" not in text


class TestMdnsConfig:
    def test_mdns_defaults_to_false(self, tmp_path):
        config_path = _write_config(tmp_path, 'server:\n  api_key: "key"\n')
        config = load_config(config_path)
        assert config.server.mdns is False

    def test_mdns_true(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            'server:\n  api_key: "key"\n  mdns: true\n',
        )
        config = load_config(config_path)
        assert config.server.mdns is True

    def test_mdns_invalid_type(self, tmp_path):
        config_path = _write_config(
            tmp_path,
            'server:\n  api_key: "key"\n  mdns: "yes"\n',
        )
        with pytest.raises(SystemExit):
            load_config(config_path)
