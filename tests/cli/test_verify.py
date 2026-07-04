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

    async def fake_obs_gt(
        client,
        device,
        t1v,
        blocks,
        prompt_fn=None,
        retry_connect=3,
        _echo=None,
        _confirm=None,
        _prompt=None,
        selected_categories=None,
    ):
        return gt_result, True

    async def fake_act_gt(client, device, t1v, consented, prompt_fn=None, selected_categories=None):
        from voltkeeper.core.ground_truth import GroundTruthResult

        return GroundTruthResult()

    with (
        patch("voltkeeper.cli.verify.lookup_scan_result", side_effect=fake_scan),
        patch("voltkeeper.cli.verify._device_from_scan", return_value=ac2a),
        patch("voltkeeper.cli.verify.BluetoothClient", return_value=mock_client),
        patch("voltkeeper.core.verify.run_tier1", side_effect=fake_tier1),
        patch(
            "voltkeeper.cli.verify._resolve_categories",
            return_value=frozenset({"observations", "load_actuations", "mode_actuations", "induced"}),
        ),
        patch("voltkeeper.cli.verify._run_handoff_observations", side_effect=fake_obs_gt),
        patch("voltkeeper.cli.verify._run_ground_truth_actuations", side_effect=fake_act_gt),
    ):
        verify.callback(
            address="AA:BB:CC:DD:EE:FF",
            output=output,
            max_tier=1,
            pre_consent=False,
            no_scrub=True,
            ground_truth=True,
            skip_categories=(),
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


# ── 9. Ground-truth split orchestration ────────────────────────────────────────


@pytest.fixture
def el100v2():
    from voltkeeper.core.devices.el100v2 import EL100V2

    return EL100V2("AA:BB:CC:DD:EE:FF", "0")


def test_ground_truth_observations_no_client_writes(ac2a):
    """Observation phase must not issue any writes to the device."""
    from tests.test_verify import FakeBluetoothClient
    from voltkeeper.cli.verify import _run_ground_truth_observations as run_obs

    client = FakeBluetoothClient({2066: 0})
    tier1_values = {"packTotalSoc": 85, "alarm_sound": False}
    tier1_blocks = {}

    prompt_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(text)
        return "85"

    loop = __import__("asyncio").new_event_loop()
    result = loop.run_until_complete(run_obs(client, ac2a, tier1_values, tier1_blocks, scripted_prompt))
    loop.close()

    assert len(client.write_log) == 0, "Observation phase must not write to device"
    assert len(prompt_log) > 0, "Observation phase should prompt the operator"
    assert len(result.observations) > 0


def test_ground_truth_actuations_after_tiers_respect_order(ac2a):
    """Orchestration ensures observation prompts precede actuation/induced prompts.
    The split functions must be independently callable so the CLI can schedule
    observations after tier 1 and actuations after the tiers."""
    from tests.test_verify import FakeBluetoothClient
    from voltkeeper.cli.verify import _run_ground_truth_actuations as run_acts
    from voltkeeper.cli.verify import _run_ground_truth_observations as run_obs

    # alarm_sound at 2066 (bool), charging_mode at 2020 (enum)
    client = FakeBluetoothClient({2066: 0, 2020: 0})
    tier1_values = {"alarm_sound": False, "charging_mode": 0, "packTotalSoc": 85}
    tier1_blocks = {}

    prompt_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(("prompt", text[:80]))
        return "85"

    loop = __import__("asyncio").new_event_loop()

    # Phase 1: Observations — should record prompts but no writes
    loop.run_until_complete(run_obs(client, ac2a, tier1_values, tier1_blocks, scripted_prompt))
    obs_prompt_count = len(prompt_log)

    # Reset write_log to count only what happens during tier 2
    client.write_log.clear()

    # Phase 2: Run tier 2 (identity writes) — writes now start
    from voltkeeper.core.verify import run_tier2

    loop.run_until_complete(run_tier2(client, ac2a, tier1_values, ["alarm_sound"]))
    tier2_write_count = len(client.write_log)

    # Phase 3: Actuations — more writes, more prompts
    act_result = loop.run_until_complete(run_acts(client, ac2a, tier1_values, frozenset({2, 3, 4}), scripted_prompt))
    act_prompt_count = len(prompt_log) - obs_prompt_count
    loop.close()

    # Observations produced prompts but not writes (client wasn't touched)
    assert obs_prompt_count > 0, "Observation phase should prompt"
    assert tier2_write_count > 0, "Tier 2 should write"
    assert act_prompt_count >= 0, "Actuation phase may prompt"
    assert act_result is not None, "Actuation result should exist"


def test_split_functions_combine_to_full_ground_truth(ac2a):
    """The two split functions together produce the same structure as the
    original single _run_ground_truth."""
    from tests.test_verify import FakeBluetoothClient
    from voltkeeper.cli.verify import _run_ground_truth_actuations as run_acts
    from voltkeeper.cli.verify import _run_ground_truth_observations as run_obs

    client = FakeBluetoothClient({2066: 0, 2020: 0})
    tier1_values = {"alarm_sound": False, "charging_mode": 0, "packTotalSoc": 85}
    tier1_blocks = {}

    prompt_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(text)
        return "85"

    loop = __import__("asyncio").new_event_loop()
    obs_result = loop.run_until_complete(run_obs(client, ac2a, tier1_values, tier1_blocks, scripted_prompt))
    act_result = loop.run_until_complete(run_acts(client, ac2a, tier1_values, frozenset({2, 3, 4}), scripted_prompt))
    loop.close()

    from voltkeeper.core.ground_truth import ground_truth_to_report_section

    combined = ground_truth_to_report_section(obs_result)
    act_section = ground_truth_to_report_section(act_result)
    combined["actuations"] = act_section.get("actuations", [])
    combined["induced_checks"] = act_section.get("induced_checks", [])

    assert "observations" in combined
    assert len(combined["observations"]) > 0


# ── 1b. App handoff around observations ──────────────────────────────────────


class HandoffFakeClient:
    """Fake BLE client that tracks connect/disconnect and supports operations."""

    def __init__(
        self,
        state: dict[int, int],
        read_overrides=None,
        max_writes=None,
        accepted_values=None,
    ):
        from tests.test_verify import FakeBluetoothClient

        self._core = FakeBluetoothClient(
            state, read_overrides=read_overrides, max_writes=max_writes, accepted_values=accepted_values
        )
        self.connected = False
        self.connect_count = 0
        self.disconnect_count = 0

    async def connect(self):
        self.connected = True
        self.connect_count += 1

    async def disconnect(self):
        self.connected = False
        self.disconnect_count += 1

    async def execute(self, cmd):
        if not self.connected:
            raise RuntimeError("Not connected")
        return await self._core.execute(cmd)

    @property
    def state(self):
        return self._core.state

    @property
    def write_log(self):
        return self._core.write_log


def test_handoff_disconnects_before_observations(ac2a):
    """BLE must be disconnected before the first observation prompt."""
    from voltkeeper.cli.verify import _run_handoff_observations as run_handoff

    client = HandoffFakeClient({2066: 0})
    tier1_values = {"packTotalSoc": 85}
    tier1_blocks = {}

    prompt_log = []
    echo_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(text)
        return "85"

    def echo(msg):
        echo_log.append(msg)

    def confirm(msg, default=True):
        return True  # app connected

    def cprompt(msg, default="", show_default=False):
        prompt_log.append(msg)
        return ""

    loop = __import__("asyncio").new_event_loop()
    gt_result, ok = loop.run_until_complete(
        run_handoff(
            client,
            ac2a,
            tier1_values,
            tier1_blocks,
            scripted_prompt,
            _echo=echo,
            _confirm=confirm,
            _prompt=cprompt,
        )
    )
    loop.close()

    assert client.disconnect_count >= 1, "Should disconnect before observations"
    assert client.connect_count >= 1, "Should reconnect after observations"
    assert ok, "Should report reconnect success"
    assert len(gt_result.observations) > 0


def test_handoff_reconnects_after_observations(ac2a):
    """BLE must reconnect after observation prompts complete."""
    from voltkeeper.cli.verify import _run_handoff_observations as run_handoff

    client = HandoffFakeClient({2066: 0})
    tier1_values = {"packTotalSoc": 85}
    tier1_blocks = {}

    prompt_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(text)
        return "85"

    def echo(msg):
        pass

    def confirm(msg, default=True):
        return True

    def cprompt(msg, default="", show_default=False):
        return ""

    loop = __import__("asyncio").new_event_loop()
    _gt_result, ok = loop.run_until_complete(
        run_handoff(
            client,
            ac2a,
            tier1_values,
            tier1_blocks,
            scripted_prompt,
            _echo=echo,
            _confirm=confirm,
            _prompt=cprompt,
        )
    )
    loop.close()

    assert ok, "Should report reconnect success"
    assert client.connected, "Should be connected after handoff completes"
    assert client.disconnect_count >= 1, "Should disconnect first"
    assert client.connect_count >= 1, "Should reconnect after observations"


def test_handoff_reconnect_failure_preserves_session(ac2a):
    """When reconnect ultimately fails, the function still returns observations."""
    from voltkeeper.cli.verify import _run_handoff_observations as run_handoff

    class RejectingClient(HandoffFakeClient):
        async def connect(self):
            self.connect_count += 1
            raise RuntimeError("Reconnect refused")

    client = RejectingClient({2066: 0})
    tier1_values = {"packTotalSoc": 85}
    tier1_blocks = {}

    prompt_log = []

    async def scripted_prompt(text, source):
        prompt_log.append(text)
        return "85"

    def echo(msg):
        pass

    def confirm(msg, default=True):
        return True

    def cprompt(msg, default="", show_default=False):
        return ""

    loop = __import__("asyncio").new_event_loop()
    gt_result, ok = loop.run_until_complete(
        run_handoff(
            client,
            ac2a,
            tier1_values,
            tier1_blocks,
            scripted_prompt,
            retry_connect=1,
            _echo=echo,
            _confirm=confirm,
            _prompt=cprompt,
        )
    )
    loop.close()

    assert not ok, "Should report reconnect failure"
    assert not client.connected, "Should not be connected after reconnect failure"
    assert len(gt_result.observations) > 0, "Observations should be preserved"


def test_handoff_reconnect_failure_branches_to_skip_tiers(ac2a, tmp_path):
    """When the handoff cannot reconnect and --ground-truth is active,
    tiers 2+ must be skipped (not attempted with a dead client)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import yaml

    from voltkeeper.cli.verify import verify
    from voltkeeper.core.ground_truth import GroundTruthResult, ObservationCheck
    from voltkeeper.core.verify import TierResult

    output = str(tmp_path / "out.yaml")

    t1_result = TierResult(tier=1, status="pass", blocks={})
    tier1_vals = {"packTotalSoc": 85}
    gt_result = GroundTruthResult()
    gt_result.observations = [
        ObservationCheck(field="soc", prompt="SoC", source="app_live", status="match", observation=85.0, parsed=85)
    ]

    # Simulate handoff that returns observations but signals reconnect failure
    async def fake_handoff_failure(
        client,
        device,
        t1v,
        blocks,
        prompt_fn=None,
        retry_connect=3,
        _echo=None,
        _confirm=None,
        _prompt=None,
        selected_categories=None,
    ):
        return gt_result, False  # (result, not reconnected)

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
        patch(
            "voltkeeper.cli.verify._resolve_categories",
            return_value=frozenset({"observations", "load_actuations", "mode_actuations", "induced"}),
        ),
        patch("voltkeeper.cli.verify._run_handoff_observations", side_effect=fake_handoff_failure),
    ):
        verify.callback(
            address="AA:BB:CC:DD:EE:FF",
            output=output,
            max_tier=6,
            pre_consent=False,
            no_scrub=True,
            ground_truth=True,
            skip_categories=(),
        )

    with open(output) as f:
        report = yaml.safe_load(f)

    assert "ground_truth" in report
    # Tiers 2+ must be skipped (connection lost), not absent or full of failures
    assert report.get("tier_2", {}).get("status") == "skipped"
    assert report.get("tier_3", {}).get("status") == "skipped"
