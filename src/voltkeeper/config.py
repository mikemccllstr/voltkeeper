# ABOUTME: Config file loading — YAML config search, parse, validate with typed model.
# ABOUTME: Searches ./voltkeeper.yaml, ~/.config/voltkeeper/config.yaml, /etc/voltkeeper/config.yaml.

from __future__ import annotations

import ipaddress
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _xdg_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "voltkeeper" / "config.yaml"
    return Path.home() / ".config" / "voltkeeper" / "config.yaml"


CONFIG_SEARCH_PATHS = [
    Path("voltkeeper.yaml"),
    _xdg_config_path(),
    Path("/etc/voltkeeper/config.yaml"),
]


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    api_key: str = ""
    allowed_networks: list[str] = field(default_factory=list)
    interface: str | None = None

    def normalized_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        result = []
        for cidr in self.allowed_networks:
            result.append(ipaddress.ip_network(cidr, strict=False))
        return result


@dataclass
class DeviceEntry:
    address: str
    name: str | None = None


@dataclass
class ScanConfig:
    interval: int = 60
    timeout: float = 10.0


@dataclass
class ShutdownWatchdogConfig:
    enabled: bool = False
    device: str = ""
    soc_threshold: int = 10
    grace_period: int = 60


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    devices: list[DeviceEntry] = field(default_factory=list)
    scan: ScanConfig = field(default_factory=ScanConfig)
    shutdown_watchdog: ShutdownWatchdogConfig = field(default_factory=ShutdownWatchdogConfig)


def load_config(path: Path | None = None) -> Config:
    config_path = _find_config(path)

    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        print(f"voltkeeperd: error parsing config file {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if raw is None:
        print(f"voltkeeperd: config file {config_path} is empty", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, dict):
        print(f"voltkeeperd: config file {config_path} must be a YAML mapping", file=sys.stderr)
        sys.exit(1)

    return _parse_config(raw, config_path)


def _find_config(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        if explicit_path.exists():
            return explicit_path
        print(f"voltkeeperd: config file not found: {explicit_path}", file=sys.stderr)
        sys.exit(1)

    for p in CONFIG_SEARCH_PATHS:
        if p.exists():
            return p

    paths = "\n  ".join(str(p) for p in CONFIG_SEARCH_PATHS)
    print(f"voltkeeperd: no config file found. Searched:\n  {paths}", file=sys.stderr)
    sys.exit(1)


def _parse_config(raw: dict, config_path: Path) -> Config:
    config = Config()

    if "server" in raw:
        config.server = _parse_server(raw["server"], config_path)

    if "devices" in raw:
        config.devices = _parse_devices(raw["devices"], config_path)

    if "scan" in raw:
        config.scan = _parse_scan(raw["scan"])

    if "shutdown_watchdog" in raw:
        config.shutdown_watchdog = _parse_shutdown_watchdog(raw["shutdown_watchdog"])

    return config


def _parse_server(raw: dict, config_path: Path) -> ServerConfig:
    if not isinstance(raw, dict):
        _fail("server", "must be a mapping", config_path)

    api_key = raw.get("api_key", "")
    if not api_key:
        _fail("server.api_key", "is required", config_path)

    host = raw.get("host", "127.0.0.1")
    port = raw.get("port", 8080)

    if not isinstance(port, int) or port < 1 or port > 65535:
        _fail("server.port", "must be an integer between 1 and 65535", config_path)

    allowed = raw.get("allowed_networks", [])
    if not isinstance(allowed, list):
        _fail("server.allowed_networks", "must be a list of CIDR strings", config_path)

    for cidr in allowed:
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError as e:
            _fail("server.allowed_networks", f"invalid CIDR '{cidr}': {e}", config_path)

    interface = raw.get("interface")
    if interface is not None and not isinstance(interface, str):
        _fail("server.interface", "must be a string (interface name) or null", config_path)

    return ServerConfig(
        host=str(host),
        port=int(port),
        api_key=str(api_key),
        allowed_networks=[str(a) for a in allowed],
        interface=str(interface) if interface else None,
    )


def _parse_devices(raw: list, config_path: Path) -> list[DeviceEntry]:
    if not isinstance(raw, list):
        _fail("devices", "must be a list", config_path)

    devices = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            _fail(f"devices[{i}]", "must be a mapping", config_path)
        address = entry.get("address")
        if not address:
            _fail(f"devices[{i}].address", "is required", config_path)
        devices.append(DeviceEntry(address=str(address), name=entry.get("name")))

    return devices


def _parse_scan(raw: dict) -> ScanConfig:
    interval = raw.get("interval", 60)
    timeout = raw.get("timeout", 10.0)
    return ScanConfig(interval=int(interval), timeout=float(timeout))


def _parse_shutdown_watchdog(raw: dict) -> ShutdownWatchdogConfig:
    return ShutdownWatchdogConfig(
        enabled=bool(raw.get("enabled", False)),
        device=str(raw.get("device", "")),
        soc_threshold=int(raw.get("soc_threshold", 10)),
        grace_period=int(raw.get("grace_period", 60)),
    )


def _fail(field: str, message: str, config_path: Path) -> None:
    print(f"voltkeeperd: {field} {message} (in {config_path})", file=sys.stderr)
    sys.exit(1)
