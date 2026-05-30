# ABOUTME: Tests for the six-tier device verify module — pure helpers, tier runners, report builder.
# ABOUTME: Tier runner tests use FakeBluetoothClient (stateful fake, not mock) for BLE simulation.

from __future__ import annotations

import struct

import pytest

from voltkeeper.core.commands import ReadHoldingRegisters, WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.struct import BoolField, DecimalField, EnumField, Uint8Field, UintField
from voltkeeper.core.verify import (
    FIELD_TIERS,
    SKIP_AUTO,
    FieldResult,
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

    accepted_values: dict[address, set[int]] — only these values update state
    at that address; other writes succeed but leave state unchanged (simulates
    silent device rejection without raising an exception).

    write_log: populated on every write — list of (address, value) tuples,
    used to verify restore-skip behaviour.
    """

    def __init__(
        self,
        state: dict[int, int],
        rejected_addresses: frozenset[int] = frozenset(),
        read_overrides: dict[int, int] | None = None,
        max_writes: dict[int, int] | None = None,
        accepted_values: dict[int, set[int]] | None = None,
    ):
        self.state = dict(state)
        self.rejected_addresses = set(rejected_addresses)
        self.read_overrides = read_overrides or {}
        self.max_writes = max_writes or {}
        self.accepted_values = accepted_values
        self._write_counts: dict[int, int] = {}
        self.write_log: list[tuple[int, int]] = []

    async def execute(self, cmd):
        if isinstance(cmd, WriteSingleRegister):
            if cmd.address in self.rejected_addresses:
                raise RuntimeError(f"write rejected for address {cmd.address}")
            count = self._write_counts.get(cmd.address, 0)
            limit = self.max_writes.get(cmd.address)
            if limit is not None and count >= limit:
                raise RuntimeError(f"write limit exceeded for address {cmd.address}")
            self._write_counts[cmd.address] = count + 1
            self.write_log.append((cmd.address, cmd.value))
            if self.accepted_values is not None and cmd.address in self.accepted_values:
                if cmd.value in self.accepted_values[cmd.address]:
                    self.state[cmd.address] = cmd.value
                # else: state unchanged — device silently rejected the value
            else:
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


async def test_run_tier3_numeric_exhaustive_sweep_covers_all_values():
    # Exhaustive sweep 0–255; FakeBluetoothClient accepts everything.
    # With range=(1, 5), device accepts all values, so probe_cap_hit=True and
    # all 256 values are probed. probed_range covers [0, 255].
    field = UintField("dc_eco_auto_off_time", 2015, range=(1, 5))
    client = FakeBluetoothClient({2015: 3})
    result = await run_tier3_numeric(client, field, 3)

    assert result.probes_count == 256
    assert result.probed_range == [0, 255]
    assert result.probe_cap_hit is True


async def test_run_tier3_numeric_discovered_range_inferred(ac2a, sys_low_power_field):
    # sys_low_power range=(0, 100); FakeBluetoothClient accepts everything.
    # Exhaustive sweep accepts all 256 values → discovered_range = [0, 255].
    client = FakeBluetoothClient({2022: 20})
    result = await run_tier3_numeric(client, sys_low_power_field, 20)
    assert result.discovered_range is not None
    assert result.discovered_range == [0, 255]


# ── 5.5 run_tier3_numeric range_discrepancy ───────────────────────────────────


async def test_run_tier3_numeric_range_discrepancy_flag():
    # declared range (0, 100) but FakeBluetoothClient accepts [0, 102]
    # discovered_range = [0, 102] → discrepancy
    field = UintField("sys_low_power", 2022, range=(0, 100))
    client = FakeBluetoothClient({2022: 20})
    result = await run_tier3_numeric(client, field, 20)
    assert result.range_discrepancy is True


async def test_run_tier3_numeric_no_discrepancy_when_ranges_match():
    # range=(0, 255); FakeBluetoothClient accepts everything.
    # Exhaustive sweep accepts all 256 values → discovered_range = [0, 255] == declared → no discrepancy.
    field = UintField("x", 100, range=(0, 255))
    client = FakeBluetoothClient({100: 20})
    result = await run_tier3_numeric(client, field, 20)
    assert result.range_discrepancy is False


async def test_run_tier3_numeric_uint8_field_caps_probe_at_255():
    # Uint8Field must not probe values above 255. With the exhaustive sweep,
    # probed_range[1] == 255 and all write_log values <= 255.
    field = Uint8Field("some_byte_field", 200, word_offset=0)
    client = FakeBluetoothClient({200: 5})
    result = await run_tier3_numeric(client, field, 5)

    assert result.probed_range is not None
    assert result.probed_range[1] <= 255
    assert all(v <= 255 for (_, v) in client.write_log)


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


def test_build_tier_plan_ctrl_led_excluded(ac2a):
    plan = build_tier_plan(ac2a)
    assert "ctrl_led" not in plan[2]
    assert "ctrl_led" not in plan[4]
    assert "ctrl_led" not in plan[5]
    assert "ctrl_led" not in plan[6]


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
    # run_tier3 should dispatch to run_tier3_numeric; no probes list for numeric fields
    client = FakeBluetoothClient({2022: 20})
    tier1 = {"sys_low_power": 20}
    result = await run_tier3(client, ac2a, tier1, ["sys_low_power"])
    fr = result.fields["sys_low_power"]
    assert fr.probes is None
    assert fr.probes_count is not None and fr.probes_count > 0
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


# ── 5.15 Serialisation for numeric field summary fields ──────────────────────


def test_tier_result_to_dict_numeric_summary_fields(ac2a):
    # FieldResult with all new summary fields populated; verify the report dict matches.
    fr = FieldResult(
        status="pass",
        current_value=10,
        probes_count=23,
        probed_range=[0, 22],
        probe_cap_hit=False,
        declared_range=[3, 10],
        in_range_rejected=[7],
        discovered_range=[3, 10],
        range_discrepancy=False,
    )
    t3 = TierResult(tier=3, status="pass", fields={"some_field": fr})
    report = build_report(ac2a, "x", "x", [t3], {})
    fd = report["tier_3"]["fields"]["some_field"]

    assert fd["status"] == "pass"
    assert fd["current_value"] == 10
    assert fd["probes_count"] == 23
    assert fd["probed_range"] == [0, 22]
    assert fd["probe_cap_hit"] is False
    assert fd["declared_range"] == [3, 10]
    assert fd["in_range_rejected"] == [7]
    assert fd["discovered_range"] == [3, 10]
    assert fd["range_discrepancy"] is False
    assert "probes" not in fd


def test_tier_result_to_dict_in_range_rejected_omitted_when_empty(ac2a):
    # in_range_rejected must be omitted (not emitted as empty list) when null.
    fr = FieldResult(
        status="pass",
        current_value=5,
        probes_count=10,
        probed_range=[0, 9],
        probe_cap_hit=False,
        declared_range=[0, 5],
        in_range_rejected=None,
        discovered_range=[0, 5],
        range_discrepancy=False,
    )
    t3 = TierResult(tier=3, status="pass", fields={"f": fr})
    report = build_report(ac2a, "x", "x", [t3], {})
    fd = report["tier_3"]["fields"]["f"]
    assert "in_range_rejected" not in fd


def test_cli_default_output_path_uses_hardware_data_prefix():
    # The default output path must start with hardware-data/ so verify files
    # land in the committed hardware-data folder, not the working directory.
    import datetime

    model = "AC2A"
    today = datetime.date.today().isoformat()
    output = f"hardware-data/verify-{model}-{today}.yaml"
    assert output.startswith("hardware-data/")
    assert f"verify-{model}-" in output
    assert output.endswith(".yaml")


# ── 6. Exhaustive sweep — new TDD tests (run_tier3_numeric) ──────────────────


async def test_exhaustive_sweep_discovers_range_not_starting_at_zero():
    # Device accepts [5, 10]; sweep stops at 12 (2 consecutive post-range rejections)
    addr = 300
    field = UintField("dc_eco_power", addr)
    client = FakeBluetoothClient({addr: 7}, accepted_values={addr: set(range(5, 11))})
    result = await run_tier3_numeric(client, field, 7)

    assert result.discovered_range == [5, 10]
    assert result.probed_range == [0, 12]
    assert result.probe_cap_hit is False
    assert result.probes_count == 13
    assert result.current_value == 7
    assert result.probes is None


async def test_pre_range_never_triggers_early_termination():
    # Device only accepts values in [200, 202]; 200 consecutive pre-range
    # rejections must not cause early termination.
    addr = 301
    field = UintField("late_range_field", addr)
    client = FakeBluetoothClient({addr: 200}, accepted_values={addr: {200, 201, 202}})
    result = await run_tier3_numeric(client, field, 200)

    assert result.discovered_range is not None
    assert result.discovered_range[0] == 200
    # Sweep must have reached value 200 despite 200 consecutive pre-range rejections
    assert result.probed_range is not None
    assert result.probed_range[0] == 0


async def test_post_range_early_termination_after_2_rejections():
    # Accepted [5, 10]; after 10, values 11 and 12 are both rejected → stop at 12.
    addr = 302
    field = UintField("some_field", addr)
    client = FakeBluetoothClient({addr: 5}, accepted_values={addr: set(range(5, 11))})
    result = await run_tier3_numeric(client, field, 5)

    assert result.probed_range == [0, 12]
    assert result.probe_cap_hit is False
    # Should NOT have probed past 12
    assert result.probes_count == 13


async def test_exhaustive_sweep_declared_range_all_accepted_no_probes_list():
    # Declared range (0, 5), device accepts all 0–255 → probe_cap_hit=True, no probes list
    addr = 303
    field = UintField("capped_field", addr, range=(0, 5))
    client = FakeBluetoothClient({addr: 3})  # accepts everything (default)
    result = await run_tier3_numeric(client, field, 3)

    assert result.probes is None
    assert result.probes_count is not None
    assert result.probed_range is not None
    assert result.probe_cap_hit is not None
    assert result.declared_range == [0, 5]
    assert result.current_value == 3


async def test_in_range_rejected_values_recorded_status_remains_pass():
    # Declared range (0, 10), device rejects value 5 inside range
    addr = 304
    field = UintField("holey_field", addr, range=(0, 10))
    accepted = set(range(0, 11)) - {5}
    client = FakeBluetoothClient({addr: 3}, accepted_values={addr: accepted})
    result = await run_tier3_numeric(client, field, 3)

    assert result.in_range_rejected is not None
    assert 5 in result.in_range_rejected
    assert result.status == "pass"


async def test_full_sweep_device_accepts_all_probe_cap_hit():
    # No accepted_values restriction: all 256 values accepted → probe_cap_hit=True
    addr = 305
    field = UintField("wide_field", addr)
    client = FakeBluetoothClient({addr: 0})
    result = await run_tier3_numeric(client, field, 0)

    assert result.probe_cap_hit is True
    assert result.discovered_range == [0, 255]
    assert result.probes_count == 256


async def test_restore_skipped_when_readback_equals_current():
    # Device rejects all writes silently (rb always returns original current_int=7).
    # The restore optimisation skips the restore write when rb == current_int.
    # Total writes in write_log must equal probes_count — no extra restore writes.
    addr = 306
    field = UintField("silent_reject_field", addr)
    client = FakeBluetoothClient({addr: 7}, accepted_values={addr: set()})
    result = await run_tier3_numeric(client, field, 7)

    # One write per probe, zero restore writes.
    assert len(client.write_log) == result.probes_count


async def test_restore_failure_sets_restore_failed_and_halts_probe():
    # Device accepts only value 10. After probe of 10 is accepted, restore fails.
    # current_int=255 so probes 0-9 are rejected with rb==255==current (no restores needed).
    # Probe 10 is accepted (state→10, rb=10≠current=255 → restore needed).
    # Writes 0-10 = 11 probe writes. max_writes=11 means restore write #12 fails.
    addr = 307
    field = UintField("restore_fail_field", addr)
    client = FakeBluetoothClient(
        {addr: 255},
        accepted_values={addr: {10}},
        max_writes={addr: 11},
    )
    result = await run_tier3_numeric(client, field, 255)

    assert result.restore_failed is True
    assert result.last_known_value is not None


async def test_declared_range_and_discrepancy_when_discovered_differs():
    # Declared range (10, 20), device accepts [5, 25]
    addr = 308
    field = UintField("wide_accepted", addr, range=(10, 20))
    client = FakeBluetoothClient({addr: 10}, accepted_values={addr: set(range(5, 26))})
    result = await run_tier3_numeric(client, field, 10)

    assert result.declared_range == [10, 20]
    assert result.discovered_range == [5, 25]
    assert result.range_discrepancy is True
