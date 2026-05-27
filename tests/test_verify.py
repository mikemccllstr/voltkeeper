# ABOUTME: Tests for the six-tier device verify module — pure helpers, tier runners, report builder.
# ABOUTME: Tier runner tests use FakeBluetoothClient (stateful fake, not mock) for BLE simulation.

from __future__ import annotations

import struct

import pytest

from voltkeeper.core.commands import ReadHoldingRegisters, WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.struct import BoolField, DecimalField, EnumField, UintField
from voltkeeper.core.verify import (
    FIELD_TIERS,
    SKIP_AUTO,
    TierResult,
    build_report,
    build_tier_plan,
    run_tier2,
    run_tier3,
    run_tier3_bool,
    run_tier3_enum,
    run_tier3_numeric,
    safe_default,
)

# ── FakeBluetoothClient ───────────────────────────────────────────────────────


class FakeBluetoothClient:
    """Stateful BLE client fake.

    State maps register address → raw uint16 value.  Writes update state;
    reads return current state.

    read_overrides: always return this raw uint16 for the given address
    (regardless of what was written) — used to simulate readback mismatches.

    max_writes: dict[address, N] — allow at most N writes to address before
    raising RuntimeError, used to test restore-failure paths.
    """

    def __init__(
        self,
        state: dict[int, int],
        rejected_addresses: frozenset[int] = frozenset(),
        read_overrides: dict[int, int] | None = None,
        max_writes: dict[int, int] | None = None,
    ):
        self.state = dict(state)
        self.rejected_addresses = set(rejected_addresses)
        self.read_overrides = read_overrides or {}
        self.max_writes = max_writes or {}
        self._write_counts: dict[int, int] = {}

    async def execute(self, cmd):
        if isinstance(cmd, WriteSingleRegister):
            if cmd.address in self.rejected_addresses:
                raise RuntimeError(f"write rejected for address {cmd.address}")
            count = self._write_counts.get(cmd.address, 0)
            limit = self.max_writes.get(cmd.address)
            if limit is not None and count >= limit:
                raise RuntimeError(f"write limit exceeded for address {cmd.address}")
            self._write_counts[cmd.address] = count + 1
            self.state[cmd.address] = cmd.value
            return b""
        if isinstance(cmd, ReadHoldingRegisters):
            parts = []
            for i in range(cmd.quantity):
                addr = cmd.starting_address + i
                val = self.read_overrides.get(addr, self.state.get(addr, 0))
                parts.append(struct.pack("!H", val))
            return b"".join(parts)
        raise ValueError(f"Unsupported command type: {type(cmd).__name__}")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ac2a():
    return AC2A("AA:BB:CC:DD:EE:FF", "0")


@pytest.fixture
def alarm_sound_field(ac2a):
    return next(f for f in ac2a.control_struct.fields if f.name == "alarm_sound")


@pytest.fixture
def sys_low_power_field(ac2a):
    return next(f for f in ac2a.control_struct.fields if f.name == "sys_low_power")


@pytest.fixture
def charging_mode_field(ac2a):
    return next(f for f in ac2a.control_struct.fields if f.name == "charging_mode")


# ── 5.1 build_tier_plan ───────────────────────────────────────────────────────


def test_build_tier_plan_ac_output_is_tier4(ac2a):
    plan = build_tier_plan(ac2a)
    assert "ac_output" in plan[4]
    assert "ac_output" not in plan[2]
    assert "ac_output" not in plan[6]


def test_build_tier_plan_charging_mode_is_auto(ac2a):
    plan = build_tier_plan(ac2a)
    assert "charging_mode" not in FIELD_TIERS
    assert "charging_mode" in plan[2]


def test_build_tier_plan_unknown_field_defaults_to_auto():
    """A field not in FIELD_TIERS ends up in the automatic tier."""

    class MinimalDevice:
        WRITABLE_FIELD_NAMES = ["some_new_field_not_in_tiers"]

    plan = build_tier_plan(MinimalDevice())
    assert "some_new_field_not_in_tiers" in plan[2]


def test_build_tier_plan_skip_auto_fields_excluded(ac2a):
    plan = build_tier_plan(ac2a)
    for name in SKIP_AUTO:
        if name in ac2a.WRITABLE_FIELD_NAMES:
            assert name not in plan[2]
            assert name not in plan[4]
            assert name not in plan[5]
            assert name not in plan[6]


def test_build_tier_plan_tier2_and_tier3_same_list(ac2a):
    plan = build_tier_plan(ac2a)
    assert plan[2] is plan[3]


def test_build_tier_plan_factory_reset_is_tier6(ac2a):
    plan = build_tier_plan(ac2a)
    assert "factory_reset" in plan[6]
    assert "factory_reset" not in plan[2]


# ── 5.2 safe_default ──────────────────────────────────────────────────────────


def test_safe_default_bool_returns_zero():
    assert safe_default(BoolField("x", 100)) == 0


def test_safe_default_enum_returns_min_member():
    result = safe_default(EnumField("x", 100, ChargingMode))
    # ChargingMode members: STANDARD=0, TURBO=1, SILENT=2 — min is 0
    assert result == 0


def test_safe_default_uint_with_range_returns_range_min():
    assert safe_default(UintField("x", 100, range=(5, 100))) == 5


def test_safe_default_uint_without_range_returns_zero():
    assert safe_default(UintField("x", 100)) == 0


def test_safe_default_decimal_with_range_returns_range_min():
    # DecimalField range stores raw int bounds: scale=1, range=(10, 200) → min raw = 10
    assert safe_default(DecimalField("x", 100, scale=1, range=(10, 200))) == 10


def test_safe_default_decimal_without_range_returns_zero():
    assert safe_default(DecimalField("x", 100, scale=1)) == 0


# ── 5.3 run_tier2 — pure unit tests ──────────────────────────────────────────


async def test_run_tier2_field_present_identity_match(ac2a):
    client = FakeBluetoothClient({2066: 0})  # alarm_sound = False
    tier1 = {"alarm_sound": False}
    result = await run_tier2(client, ac2a, tier1, ["alarm_sound"])
    fr = result.fields["alarm_sound"]
    assert fr.status == "pass"
    assert fr.wrote == 0
    assert fr.readback == 0
    assert fr.match is True
    assert fr.note is None


async def test_run_tier2_field_absent_uses_safe_default(ac2a):
    client = FakeBluetoothClient({2066: 0})
    result = await run_tier2(client, ac2a, {}, ["alarm_sound"])
    fr = result.fields["alarm_sound"]
    assert fr.read is None
    assert fr.wrote == 0  # safe default for BoolField
    assert "safe default" in (fr.note or "")


async def test_run_tier2_overall_pass_when_all_match(ac2a):
    client = FakeBluetoothClient({2066: 0})
    result = await run_tier2(client, ac2a, {"alarm_sound": False}, ["alarm_sound"])
    assert result.status == "pass"


# ── 5.4 run_tier3_numeric with declared range ─────────────────────────────────


async def test_run_tier3_numeric_probe_sequence_includes_boundaries():
    # range=(1, 5): sequence = [current=3, low=1, high=5, low-1=0, high+1=6, high+2=7, 0(dup), 65535]
    # after dedup+filter: [3, 1, 5, 0, 6, 7, 65535]
    field = UintField("dc_eco_auto_off_time", 2015, range=(1, 5))
    client = FakeBluetoothClient({2015: 3})
    result = await run_tier3_numeric(client, field, 3)

    probed_values = {p.wrote for p in result.probes}
    assert 1 in probed_values  # low boundary
    assert 5 in probed_values  # high boundary
    assert 0 in probed_values  # low - 1
    assert 6 in probed_values  # high + 1
    assert 7 in probed_values  # high + 2
    assert 65535 in probed_values  # max sentinel


async def test_run_tier3_numeric_discovered_range_inferred(ac2a, sys_low_power_field):
    # sys_low_power range=(0, 100); FakeBluetoothClient accepts everything
    # Probes: [current=20, 0, 100, 0(dup), 101, 102, 0(dup), 65535]
    # After dedup+filter: [20, 0, 100, 101, 102, 65535]
    # Accepted (excluding 65535): [20, 0, 100, 101, 102]
    # discovered_range = [0, 102]
    client = FakeBluetoothClient({2022: 20})
    result = await run_tier3_numeric(client, sys_low_power_field, 20)
    assert result.discovered_range is not None
    assert result.discovered_range[0] == 0
    assert result.discovered_range[1] == 102


# ── 5.5 run_tier3_numeric range_discrepancy ───────────────────────────────────


async def test_run_tier3_numeric_range_discrepancy_flag():
    # declared range (0, 100) but FakeBluetoothClient accepts [0, 102]
    # discovered_range = [0, 102] → discrepancy
    field = UintField("sys_low_power", 2022, range=(0, 100))
    client = FakeBluetoothClient({2022: 20})
    result = await run_tier3_numeric(client, field, 20)
    assert result.range_discrepancy is True


async def test_run_tier3_numeric_no_discrepancy_when_ranges_match():
    # With range=(0, 102): sequence = [20, 0, 102, -1(skip), 103, 104, 0(dup), 65535]
    # After dedup+filter: [20, 0, 102, 103, 104, 65535]
    # All accepted → discovered_range = [0, 104] — still a discrepancy
    # To get no discrepancy we need a range that encompasses all probe values.
    # With range=(0, 65534): probes include [20, 0, 65534, -1(skip), 65535, 65536(skip), 0(dup), 65535(dup)]
    # After dedup+filter: [20, 0, 65534, 65535]
    # range_vals (excl 65535): [20, 0, 65534]
    # discovered_range = [0, 65534], declared_range = (0, 65534) → no discrepancy
    field = UintField("x", 100, range=(0, 65534))
    client = FakeBluetoothClient({100: 20})
    result = await run_tier3_numeric(client, field, 20)
    assert result.range_discrepancy is False


# ── 5.6 run_tier3_bool ────────────────────────────────────────────────────────


async def test_run_tier3_bool_toggle_and_restore(alarm_sound_field):
    client = FakeBluetoothClient({2066: 0})  # alarm_sound = False
    result = await run_tier3_bool(client, alarm_sound_field, 0)

    assert result.status == "pass"
    assert result.restore_failed is False
    assert result.probes is not None
    assert len(result.probes) == 1
    assert result.probes[0].wrote == 1  # toggled to True
    assert result.probes[0].readback == 1
    assert result.probes[0].result == "accepted"
    # State should be restored to 0
    assert client.state[2066] == 0


async def test_run_tier3_bool_restore_failed(alarm_sound_field):
    # Allow 1 write (the toggle), then reject the restore
    client = FakeBluetoothClient({2066: 0}, max_writes={2066: 1})
    result = await run_tier3_bool(client, alarm_sound_field, 0)

    assert result.restore_failed is True
    assert result.last_known_value is not None
    assert result.status == "fail"


# ── 5.7 run_tier3_enum ────────────────────────────────────────────────────────


async def test_run_tier3_enum_cycles_all_members(charging_mode_field):
    # ChargingMode: STANDARD=0, TURBO=1, SILENT=2; current=1 (TURBO)
    client = FakeBluetoothClient({2020: 1})
    result = await run_tier3_enum(client, charging_mode_field, 1)

    assert result.status == "pass"
    assert result.restore_failed is False
    assert result.probes is not None
    # One probe per member
    assert len(result.probes) == len(list(ChargingMode))
    probed_values = {p.wrote for p in result.probes}
    assert probed_values == {m.value for m in ChargingMode}
    # State should be restored to original
    assert client.state[2020] == 1


async def test_run_tier3_enum_each_member_restored(charging_mode_field):
    client = FakeBluetoothClient({2020: 0})
    result = await run_tier3_enum(client, charging_mode_field, 0)
    # All probes accepted; field restored to original after each non-current probe
    assert all(p.result == "accepted" for p in result.probes)
    assert client.state[2020] == 0


# ── 5.8 report scrubbing ──────────────────────────────────────────────────────


def test_build_report_scrubs_sn(ac2a):
    t1 = TierResult(tier=1, status="pass")
    report = build_report(ac2a, "REAL-SN-99999", "DE:AD:BE:EF:00:01", [t1], {})
    assert report["device"]["sn"] == "VKTEST000000"
    assert "REAL-SN-99999" not in str(report)


def test_build_report_scrubs_ble_address(ac2a):
    t1 = TierResult(tier=1, status="pass")
    report = build_report(ac2a, "x", "DE:AD:BE:EF:00:01", [t1], {})
    assert report["device"]["ble_address"] == "AA:BB:CC:DD:EE:FF"
    assert "DE:AD:BE:EF:00:01" not in str(report)


def test_build_report_no_scrub_preserves_values(ac2a):
    t1 = TierResult(tier=1, status="pass")
    report = build_report(ac2a, "REAL-SN-99999", "DE:AD:BE:EF:00:01", [t1], {}, scrub=False)
    assert report["device"]["sn"] == "REAL-SN-99999"
    assert report["device"]["ble_address"] == "DE:AD:BE:EF:00:01"


# ── 5.9 skipped tier in report ────────────────────────────────────────────────


def test_build_report_skipped_tier_present_not_omitted(ac2a):
    skipped = TierResult(tier=4, status="skipped", reason="user declined")
    report = build_report(ac2a, "x", "x", [skipped], {})
    assert "tier_4" in report
    assert report["tier_4"]["status"] == "skipped"
    assert report["tier_4"]["reason"] == "user declined"
    assert "fields" in report["tier_4"]


def test_build_report_includes_firmware_fields(ac2a):
    t1 = TierResult(tier=1, status="pass")
    tier1_values = {"arm_version": "1.2.3", "dsp_version": "4.5.6", "battery_level": 80}
    report = build_report(ac2a, "x", "x", [t1], tier1_values)
    assert "firmware" in report["device"]
    assert "arm_version" in report["device"]["firmware"]
    assert "battery_level" not in report["device"]["firmware"]


def test_build_report_firmware_includes_v2_software_number(ac2a):
    # V2 devices expose softwareNumber, not arm_version/dsp_version.
    # The "software" substring must be in _FIRMWARE_FIELD_SUBSTRINGS.
    t1 = TierResult(tier=1, status="pass")
    tier1_values = {"softwareNumber": 42, "packTotalSoc": 95}
    report = build_report(ac2a, "x", "x", [t1], tier1_values)
    assert "firmware" in report["device"]
    assert "softwareNumber" in report["device"]["firmware"]
    assert "packTotalSoc" not in report["device"]["firmware"]


def test_build_tier_plan_ja12_enable_excluded(ac2a):
    plan = build_tier_plan(ac2a)
    assert "ja12_enable" not in plan[2]
    assert "ja12_enable" not in plan[4]
    assert "ja12_enable" not in plan[5]
    assert "ja12_enable" not in plan[6]


# ── 5.10–5.12 Tier-2 roundtrip and mismatch via FakeBluetoothClient ──────────


async def test_tier2_roundtrip_fake_client(ac2a):
    # alarm_sound=False at address 2066; identity write should match
    client = FakeBluetoothClient({2066: 0})
    result = await run_tier2(client, ac2a, {"alarm_sound": False}, ["alarm_sound"])
    fr = result.fields["alarm_sound"]
    assert fr.match is True
    assert fr.status == "pass"
    assert fr.wrote == 0
    assert fr.readback == 0


async def test_tier2_mismatch_path_fake_client(ac2a):
    # read_overrides forces readback=1 regardless of what we write
    client = FakeBluetoothClient({2066: 0}, read_overrides={2066: 1})
    result = await run_tier2(client, ac2a, {"alarm_sound": False}, ["alarm_sound"])
    fr = result.fields["alarm_sound"]
    assert fr.match is False
    assert fr.status == "fail"
    assert result.status == "fail"


# ── 5.13 Tier-3 range probe via FakeBluetoothClient ──────────────────────────


async def test_tier3_range_probe_via_fake_client(ac2a):
    # sys_low_power at 2022, range=(0, 100), current=20
    # run_tier3 should dispatch to run_tier3_numeric
    client = FakeBluetoothClient({2022: 20})
    tier1 = {"sys_low_power": 20}
    result = await run_tier3(client, ac2a, tier1, ["sys_low_power"])
    fr = result.fields["sys_low_power"]
    assert fr.probes is not None
    assert len(fr.probes) > 0
    assert fr.discovered_range is not None
    assert fr.restore_failed is False
    # Restored to original
    assert client.state[2022] == 20


# ── 5.14 Restore-failure path via FakeBluetoothClient ────────────────────────


async def test_tier3_restore_failure_continues_next_field(ac2a):
    # alarm_sound at 2066: allow 1 write (toggle), reject restore
    # sys_low_power at 2022: should still be tested after alarm_sound restore fails
    client = FakeBluetoothClient({2066: 0, 2022: 20}, max_writes={2066: 1})
    tier1 = {"alarm_sound": False, "sys_low_power": 20}
    result = await run_tier3(client, ac2a, tier1, ["alarm_sound", "sys_low_power"])

    assert result.fields["alarm_sound"].restore_failed is True
    # sys_low_power should have been tested despite alarm_sound restore failure
    assert "sys_low_power" in result.fields
    assert result.fields["sys_low_power"].status in ("pass", "fail")
    assert result.fields["sys_low_power"].probes is not None
