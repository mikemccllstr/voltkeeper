# ABOUTME: Tests for probe module — YAML round-trip, protocol detection, registry shortcut.
# ABOUTME: Unit 11 per IMPLEMENTATION_UNITS.md.

from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.bluetti_cli.bluetooth.exc import BadConnectionError, ModbusError
from src.bluetti_cli.probe import (
    _detect_protocol,
    _v1_base_real_data_size,
    _v1_bms_pack_size,
    _v1_settable_data_size,
    emit_yaml,
    probe_device,
)

# ── YAML round-trip ───────────────────────────────────────────────────


def test_emit_yaml_round_trips(tmp_path):
    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "AC2A2305000",
        "encrypted": False,
        "protocol": "v2",
        "protocol_version": 2000,
        "blocks": {
            "APP_HOME_DATA": {"address": 100, "size": 62, "raw_hex": "deadbeef"},
            "INV_BASE_INFO": {"address": 1100, "size": 51, "raw_hex": "cafecafe"},
        },
    }
    out = tmp_path / "profile.yaml"
    emit_yaml(profile, out)

    with open(out) as f:
        reloaded = yaml.safe_load(f)

    assert reloaded == profile


def test_emit_yaml_empty_blocks(tmp_path):
    profile = {
        "address": "FF:FF:FF:FF:FF:FF",
        "name": "UNKNOWN999999",
        "encrypted": None,
        "protocol": "unknown",
        "protocol_version": None,
        "blocks": {},
    }
    out = tmp_path / "empty.yaml"
    emit_yaml(profile, out)

    with open(out) as f:
        reloaded = yaml.safe_load(f)

    assert reloaded == profile


def test_emit_yaml_str_output(tmp_path):
    """emit_yaml accepts a string path."""
    profile = {"address": "AA:BB:CC:DD:EE:FF", "encrypted": True, "blocks": {}}
    out = str(tmp_path / "str.yaml")
    emit_yaml(profile, out)

    with open(out) as f:
        reloaded = yaml.safe_load(f)

    assert reloaded == profile


# ── Protocol detection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_protocol_registry_shortcut_ac2a():
    """Registry hit — no Modbus read needed."""
    client = AsyncMock()
    info = await _detect_protocol(client, "AC2A2305000")
    assert info.kind == "v2"
    assert info.version == 2000
    client.connect.assert_not_awaited()
    client.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_detect_protocol_registry_shortcut_eb3a():
    client = AsyncMock()
    info = await _detect_protocol(client, "EB3A1234567")
    assert info.kind == "v1"
    assert info.version == 0
    client.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_detect_protocol_dynamic_v2():
    """Unknown prefix — read register 16, value 2036 → V2."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=b"\x07\xf4")
    info = await _detect_protocol(client, "BOGUS999999")
    assert info.kind == "v2"
    assert info.version == 2036
    client.execute.assert_awaited_once()
    args = client.execute.await_args[0]
    assert args[0].starting_address == 16
    assert args[0].quantity == 1


@pytest.mark.asyncio
async def test_detect_protocol_dynamic_v1():
    """Unknown prefix — read register 16, value 1019 → V1."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=b"\x03\xfb")
    info = await _detect_protocol(client, "BOGUS999999")
    assert info.kind == "v1"
    assert info.version == 1019


@pytest.mark.asyncio
async def test_detect_protocol_dynamic_fallback_v2():
    """V1 register 16 fails, V2 register 1100 succeeds → V2."""
    client = AsyncMock()
    # First call (reg 16) raises, second call (reg 1100) succeeds
    client.execute = AsyncMock()
    client.execute.side_effect = [
        ModbusError("no response"),
        b"\x00\x01",  # register 1100 responds
    ]
    info = await _detect_protocol(client, "BOGUS999999")
    assert info.kind == "v2"
    assert client.execute.call_count == 2


@pytest.mark.asyncio
async def test_detect_protocol_dynamic_unknown():
    """Both V1 reg 16 and V2 reg 1100 fail → unknown."""
    client = AsyncMock()
    client.execute = AsyncMock(side_effect=ModbusError("no response"))
    info = await _detect_protocol(client, "BOGUS999999")
    assert info.kind == "unknown"
    assert info.version is None
    assert client.execute.call_count == 2


# ── Resilience: connect failure ───────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_device_connect_failure_still_emits_profile():
    """Client.connect() raises → still returns unknown+empty profile."""
    with patch("src.bluetti_cli.probe.BluetoothClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=BadConnectionError("timeout"))
        MockClient.return_value = mock_client

        profile = await probe_device("AA:BB:CC:DD:EE:FF", "UNKNOWN999", encrypted=False)

    assert profile["protocol"] == "unknown"
    assert profile["protocol_version"] is None
    assert profile["blocks"] == {}
    mock_client.disconnect.assert_not_awaited()  # never connected


# ── Per-version V1 block sizing ──────────────────────────────────────


@pytest.mark.parametrize(
    "ver, expected",
    [
        (0, 53),
        (1000, 53),
        (1016, 53),
        (1017, 58),
        (1022, 58),
        (1023, 59),
        (1500, 59),
    ],
)
def test_v1_base_real_data_size(ver, expected):
    assert _v1_base_real_data_size(ver) == expected


@pytest.mark.parametrize(
    "ver, expected",
    [
        (0, 10),
        (1000, 10),
        (1016, 10),
        (1017, 115),
        (1021, 115),
        (1022, 127),
        (1500, 127),
    ],
)
def test_v1_bms_pack_size(ver, expected):
    assert _v1_bms_pack_size(ver) == expected


@pytest.mark.parametrize(
    "ver, expected",
    [
        (0, 36),
        (1000, 36),
        (1015, 36),
        (1016, 62),
        (1018, 62),
        (1019, 67),
        (1020, 67),
        (1021, 82),
        (1022, 82),
        (1023, 90),
        (1025, 90),
        (1026, 91),
    ],
)
def test_v1_settable_data_size(ver, expected):
    assert _v1_settable_data_size(ver) == expected
