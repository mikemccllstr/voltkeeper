# ABOUTME: CLI-level tests for verify --tier and --ground-truth flow control.
# ABOUTME: Uses mocked BLE stack; exercises early-exit paths that were historically untested.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voltkeeper.core.devices.ac2a import AC2A
from voltkeeper.core.ground_truth import ObservationCheck


@pytest.fixture
def ac2a():
    return AC2A("AA:BB:CC:DD:EE:FF", "0")


def test_tier1_ground_truth_section_in_report(ac2a, tmp_path):
    """--tier 1 --ground-truth must include ground_truth section in output YAML."""
    import yaml

    from voltkeeper.cli.verify import verify
    from voltkeeper.core.ground_truth import GroundTruthResult
    from voltkeeper.core.verify import TierResult

    output = str(tmp_path / "out.yaml")

    t1_result = TierResult(tier=1, status="pass", blocks={})
    tier1_vals = {"packTotalSoc": 85}
    gt_result = GroundTruthResult()
    gt_result.observations = [
        ObservationCheck(
            field="pack_voltage",
            prompt="Pack voltage",
            source="device_screen",
            status="match",
            observation=26.5,
            parsed=26.5,
        )
    ]

    async def fake_scan(addr):
        sr = MagicMock()
        sr.encrypted = False
        return sr

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    async def fake_tier1(client, device):
        return t1_result, tier1_vals

    async def fake_gt(client, device, t1v, blocks, consented):
        return gt_result

    with (
        patch("voltkeeper.cli.verify.lookup_scan_result", side_effect=fake_scan),
        patch("voltkeeper.cli.verify._device_from_scan", return_value=ac2a),
        patch("voltkeeper.cli.verify.BluetoothClient", return_value=mock_client),
        patch("voltkeeper.core.verify.run_tier1", side_effect=fake_tier1),
        patch("voltkeeper.cli.verify._run_ground_truth", side_effect=fake_gt),
    ):
        verify.callback(
            address="AA:BB:CC:DD:EE:FF",
            output=output,
            max_tier=1,
            pre_consent=False,
            no_scrub=True,
            ground_truth=True,
        )

    with open(output) as f:
        report = yaml.safe_load(f)

    assert "ground_truth" in report
    assert "observations" in report["ground_truth"]
    assert report["ground_truth"]["observations"][0]["field"] == "pack_voltage"


def test_tier1_without_ground_truth_has_no_ground_truth_section(ac2a, tmp_path):
    """--tier 1 without --ground-truth must not include ground_truth section."""
    import yaml

    from voltkeeper.cli.verify import verify
    from voltkeeper.core.verify import TierResult

    output = str(tmp_path / "out.yaml")

    t1_result = TierResult(tier=1, status="pass", blocks={})
    tier1_vals = {"packTotalSoc": 85}

    async def fake_scan(addr):
        sr = MagicMock()
        sr.encrypted = False
        return sr

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    async def fake_tier1(client, device):
        return t1_result, tier1_vals

    with (
        patch("voltkeeper.cli.verify.lookup_scan_result", side_effect=fake_scan),
        patch("voltkeeper.cli.verify._device_from_scan", return_value=ac2a),
        patch("voltkeeper.cli.verify.BluetoothClient", return_value=mock_client),
        patch("voltkeeper.core.verify.run_tier1", side_effect=fake_tier1),
    ):
        verify.callback(
            address="AA:BB:CC:DD:EE:FF",
            output=output,
            max_tier=1,
            pre_consent=False,
            no_scrub=True,
            ground_truth=False,
        )

    with open(output) as f:
        report = yaml.safe_load(f)

    assert "ground_truth" not in report
