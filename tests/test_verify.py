# ABOUTME: Tests for the six-tier device verify module — pure helpers, tier runners, report builder.
# ABOUTME: Tier runner tests use FakeBluetoothClient (stateful fake, not mock) for BLE simulation.

from __future__ import annotations

import struct

import pytest

from voltkeeper.core.commands import ReadHoldingRegisters, TlvReadHoldingRegisters, WriteSingleRegister
from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.struct import BoolField, DecimalField, EnumField, Uint8Field, UintField
from voltkeeper.core.verify import (
    FIELD_TIERS,
    SKIP_AUTO,
    BlockResult,
    FieldResult,
    TierResult,
    build_report,
    build_tier_plan,
    run_tier1,
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
        if isinstance(cmd, TlvReadHoldingRegisters):
            return self._build_tlv_response(cmd)
        raise ValueError(f"Unsupported command type: {type(cmd).__name__}")

    def _build_tlv_response(self, cmd: TlvReadHoldingRegisters) -> bytes:
        """Build TLV-encoded response data from current state.
        TLV format: magic(3) + per-item [slave(1) reg_addr(2BE) length(2BE) value(N) crc16(2)]
        """
        from voltkeeper.core.tlv import TLV_MAGIC

        items = bytearray()
        for addr, count in cmd.sections:
            item_value = bytearray()
            for i in range(count):
                reg_addr = addr + i
                val = self.read_overrides.get(reg_addr, self.state.get(reg_addr, 0))
                item_value.extend(struct.pack("!H", val))
            items.append(cmd.slave_addr & 0xFF)
            items.extend(struct.pack("!HH", addr, len(item_value)))
            items.extend(item_value)
            items.append(0x00)
            items.append(0x00)
        return TLV_MAGIC + bytes(items)


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
    # ChargingMode members: STANDARD=0, SILENT=1, TURBO=2 — min is 0
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
    # ChargingMode: STANDARD=0, SILENT=1, TURBO=2; current=1 (SILENT)
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
    # V2 devices expose softwareNumber (from struct) and named _version keys
    # (from _fill_software_versions). Both must be captured by firmware matching.
    t1 = TierResult(tier=1, status="pass")
    tier1_values = {"softwareNumber": 42, "arm_version": 208409, "packTotalSoc": 95}
    report = build_report(ac2a, "x", "x", [t1], tier1_values)
    assert "firmware" in report["device"]
    assert "softwareNumber" in report["device"]["firmware"]
    assert "arm_version" in report["device"]["firmware"]
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


# ── 5.A Unique-path helper ─────────────────────────────────────────────────────


def test_unique_path_non_existent_unchanged(tmp_path):
    from voltkeeper.core.verify import _unique_path

    p = tmp_path / "does_not_exist.yaml"
    result = _unique_path(str(p))
    assert result == str(p)


def test_unique_path_existing_gets_v2(tmp_path):
    from voltkeeper.core.verify import _unique_path

    p = tmp_path / "existing.yaml"
    p.write_text("old")
    result = _unique_path(str(p))
    assert result == str(tmp_path / "existing_v2.yaml")


def test_unique_path_v2_occupied_gets_v3(tmp_path):
    from voltkeeper.core.verify import _unique_path

    p = tmp_path / "collision.yaml"
    v2 = tmp_path / "collision_v2.yaml"
    v3 = tmp_path / "collision_v3.yaml"

    p.write_text("base")
    v2.write_text("v2")
    result = _unique_path(str(p))
    assert result == str(v3)


def test_unique_path_v2_open_returns_v2_skipping_higher(tmp_path):
    from voltkeeper.core.verify import _unique_path

    p = tmp_path / "base.yaml"
    v3 = tmp_path / "base_v3.yaml"

    p.write_text("base")
    v3.write_text("v3")
    result = _unique_path(str(p))
    # _v2 is free → should take _v2, not _v3 or higher
    assert result == str(tmp_path / "base_v2.yaml")


def test_write_report_returns_actual_path_and_avoids_overwrite(tmp_path):
    from voltkeeper.core.verify import write_report

    request_path = tmp_path / "rpt.yaml"

    report = {"device": {"model": "TEST"}}
    actual1 = write_report(report, str(request_path))
    assert actual1 == str(request_path)  # first write uses exact path
    assert (tmp_path / "rpt.yaml").exists()

    actual2 = write_report(report, str(request_path))
    assert actual2 == str(tmp_path / "rpt_v2.yaml")  # collision gets _v2
    assert (tmp_path / "rpt_v2.yaml").exists()

    # First file content untouched
    assert (tmp_path / "rpt.yaml").read_text()

    actual3 = write_report(report, str(request_path))
    assert actual3 == str(tmp_path / "rpt_v3.yaml")
    assert (tmp_path / "rpt_v3.yaml").exists()


# ── 5.B Default filename builder ───────────────────────────────────────────────


def test_default_filename_plain_run():
    from datetime import datetime, timezone

    from voltkeeper.core.verify import _build_default_output_path

    timestamp = datetime(2026, 7, 4, 17, 59, tzinfo=timezone.utc)
    path = _build_default_output_path("EL100V2", ground_truth=False, now=timestamp)
    assert path == "hardware-data/verify_EL100V2_2026-07-04T1759Z.yaml"


def test_default_filename_ground_truth_run():
    from datetime import datetime, timezone

    from voltkeeper.core.verify import _build_default_output_path

    timestamp = datetime(2026, 7, 4, 17, 59, tzinfo=timezone.utc)
    path = _build_default_output_path("EL100V2", ground_truth=True, now=timestamp)
    assert path == "hardware-data/verify-ground-truth_EL100V2_2026-07-04T1759Z.yaml"


def test_default_filename_timestamp_utc_minute_precision_z_suffix():
    from datetime import datetime, timezone

    from voltkeeper.core.verify import _build_default_output_path

    timestamp = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    path = _build_default_output_path("AC2A", ground_truth=False, now=timestamp)
    assert path.endswith("_2026-01-01T0005Z.yaml")


def test_default_filename_model_with_digit_suffix():
    from datetime import datetime, timezone

    from voltkeeper.core.verify import _build_default_output_path

    timestamp = datetime(2026, 7, 4, 17, 59, tzinfo=timezone.utc)
    path = _build_default_output_path("EL100V2", ground_truth=False, now=timestamp)
    # Underscore separates mode/model/timestamp; model itself contains no underscore
    # so "EL100V2" stays intact
    assert "EL100V2" in path
    assert "verify_EL100V2_" in path


def test_cli_default_output_path_uses_hardware_data_prefix():
    from datetime import datetime, timezone

    from voltkeeper.core.verify import _build_default_output_path

    timestamp = datetime(2026, 7, 4, 17, 59, tzinfo=timezone.utc)
    output = _build_default_output_path("AC2A", ground_truth=False, now=timestamp)
    assert output.startswith("hardware-data/")
    assert "verify_AC2A_" in output
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


# ── 7. Raw payload recording in tier 1 ─────────────────────────────────────────


async def test_run_tier1_plain_read_records_raw_hex(ac2a):
    ac2a._force_full_poll = True
    client = FakeBluetoothClient({})
    result, _ = await run_tier1(client, ac2a)

    for addr_key, block in result.blocks.items():
        assert block.raw is not None, f"Block {addr_key} missing raw hex"
        assert isinstance(block.raw, str), f"Block {addr_key} raw is not a str"
        assert len(block.raw) > 0, f"Block {addr_key} raw is empty"
        raw_bytes = bytes.fromhex(block.raw)
        assert len(raw_bytes) > 0, f"Block {addr_key} raw bytes are empty"


async def test_run_tier1_parse_failure_records_raw_hex(ac2a):
    ac2a._force_full_poll = True
    client = FakeBluetoothClient({})
    original_parse = ac2a.parse
    home_addr = 100

    def failing_parse(address, data):
        if address == home_addr:
            raise RuntimeError("simulated parse failure")
        return original_parse(address, data)

    ac2a.parse = failing_parse
    try:
        result, _ = await run_tier1(client, ac2a)
        home_block = result.blocks[str(home_addr)]
        assert home_block.status == "fail"
        assert home_block.raw is not None, "Failed block missing raw hex"
        assert len(home_block.raw) > 0, "Failed block raw is empty"
        assert home_block.error == "simulated parse failure"
    finally:
        ac2a.parse = original_parse


async def test_run_tier1_tlv_records_raw_per_item(ac2a):
    from unittest.mock import patch

    ac2a._force_full_poll = True
    tlv_cmds = ac2a.tlv_polling_commands
    client = FakeBluetoothClient({})
    with patch.object(type(ac2a), "polling_commands", tlv_cmds):
        result, _ = await run_tier1(client, ac2a)
        assert len(result.blocks) > 0, "No TLV blocks recorded"
        for addr_key, block in result.blocks.items():
            assert block.raw is not None, f"TLV block {addr_key} missing raw hex"
            assert isinstance(block.raw, str), f"TLV block {addr_key} raw is not a str"
            raw_bytes = bytes.fromhex(block.raw)
            assert len(raw_bytes) > 0, f"TLV block {addr_key} raw bytes are empty"


async def test_run_tier1_tlv_item_parse_failure_isolated(ac2a):
    """One item's parse failure must not discard other items' results or raw."""
    from unittest.mock import patch

    ac2a._force_full_poll = True
    tlv_cmds = ac2a.tlv_polling_commands
    client = FakeBluetoothClient({})
    original_parse = ac2a.parse

    def failing_parse(address, data):
        if address == 1100:
            raise RuntimeError("simulated item parse failure")
        return original_parse(address, data)

    ac2a.parse = failing_parse
    try:
        with patch.object(type(ac2a), "polling_commands", tlv_cmds):
            result, _ = await run_tier1(client, ac2a)
    finally:
        ac2a.parse = original_parse

    failed = result.blocks["1100"]
    assert failed.status == "fail"
    assert failed.error == "simulated item parse failure"
    assert failed.raw is not None, "Failed item should keep its own raw hex"
    assert failed.raw_is_bundle is False
    home = result.blocks["100"]
    assert home.status == "pass", "Other items must survive one item's parse failure"
    assert home.raw is not None


async def test_run_tier1_unparseable_tlv_bundle_records_bundle_raw(ac2a):
    """A bundle TlvParser can't parse is recorded as bundle-shaped raw, not per-block raw."""
    from unittest.mock import patch

    from voltkeeper.core.tlv import TLV_MAGIC

    ac2a._force_full_poll = True
    tlv_cmds = ac2a.tlv_polling_commands
    # Item header declaring a length far beyond the data => ParseError
    garbage = TLV_MAGIC + bytes([0x01, 0x00, 0x64, 0xFF, 0xFF]) + b"\x00" * 4

    class GarbageTlvClient(FakeBluetoothClient):
        def _build_tlv_response(self, cmd):
            return garbage

    client = GarbageTlvClient({})
    with patch.object(type(ac2a), "polling_commands", tlv_cmds):
        result, _ = await run_tier1(client, ac2a)

    section_addrs = [str(addr) for addr, _ in tlv_cmds[0].sections]
    for addr_key in section_addrs:
        block = result.blocks[addr_key]
        assert block.status == "fail"
        assert block.raw == garbage.hex()
        assert block.raw_is_bundle is True, "Bundle hex must be flagged as bundle-shaped"


def test_scrub_drops_unparseable_bundle_raw(ac2a):
    """Bundle-shaped raw can't be offset-scrubbed, so scrubbed reports must drop it."""
    br = BlockResult(status="fail", error="boom", raw="deadbeef", raw_is_bundle=True)
    t1 = TierResult(tier=1, status="fail", blocks={"100": br})
    report = build_report(ac2a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    block_100 = report["tier_1"]["blocks"]["100"]
    assert "raw" not in block_100
    assert "raw_bundle" not in block_100


def test_no_scrub_keeps_bundle_raw_under_distinct_key(ac2a):
    br = BlockResult(status="fail", error="boom", raw="deadbeef", raw_is_bundle=True)
    t1 = TierResult(tier=1, status="fail", blocks={"100": br})
    report = build_report(ac2a, "SN", "AA:BB:CC:DD:EE:FF", [t1], {}, scrub=False)
    block_100 = report["tier_1"]["blocks"]["100"]
    assert block_100["raw_bundle"] == "deadbeef"
    assert "raw" not in block_100


def test_tier_result_to_dict_includes_raw_in_blocks(ac2a):
    br = BlockResult(status="pass", fields_parsed=5, raw="deadbeef")
    t1 = TierResult(tier=1, status="pass", blocks={"100": br})
    report = build_report(ac2a, "x", "x", [t1], {})
    block_100 = report["tier_1"]["blocks"]["100"]
    assert block_100["status"] == "pass"
    assert block_100["fields_parsed"] == 5
    assert block_100["raw"] == "deadbeef"


def test_tier_result_to_dict_omits_raw_when_none(ac2a):
    br = BlockResult(status="fail", fields_parsed=0, error="boom")
    t1 = TierResult(tier=1, status="fail", blocks={"100": br})
    report = build_report(ac2a, "x", "x", [t1], {})
    block_100 = report["tier_1"]["blocks"]["100"]
    assert "raw" not in block_100


# ── 8. Raw payload scrubbing ──────────────────────────────────────────────────


def test_scrub_zeroes_v1_real_data_sn_bytes():
    """V1 devices keep deviceSN in real_data_struct (reg 21 of block 10) — must be scrubbed too."""
    from voltkeeper.core.devices.eb3a import EB3A

    eb3a = EB3A("00:00:00:00:00:00", "TEST")
    raw_bytes = bytes([0xAB] * 220)  # BASE_REAL_DATA block: 110 regs
    br = BlockResult(status="pass", fields_parsed=10, raw=raw_bytes.hex())
    t1 = TierResult(tier=1, status="pass", blocks={"10": br})
    report = build_report(eb3a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    scrubbed_bytes = bytes.fromhex(report["tier_1"]["blocks"]["10"]["raw"])
    # deviceSN: reg 21, 4 regs -> byte offset 2*(21-10)=22, 8 bytes
    assert scrubbed_bytes[22:30] == b"\x00" * 8, f"V1 SN bytes not zeroed: {scrubbed_bytes[22:30].hex()}"
    assert scrubbed_bytes[:22] == raw_bytes[:22]
    assert scrubbed_bytes[30:] == raw_bytes[30:]


def test_scrub_zeroes_home_sn_bytes(ac2a, ac2a_home_bytes):
    raw_hex = ac2a_home_bytes.hex()
    br = BlockResult(status="pass", fields_parsed=23, raw=raw_hex)
    t1 = TierResult(tier=1, status="pass", blocks={"100": br})
    report = build_report(ac2a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    scrubbed = report["tier_1"]["blocks"]["100"]["raw"]
    scrubbed_bytes = bytes.fromhex(scrubbed)
    original_bytes = ac2a_home_bytes
    assert len(scrubbed_bytes) == len(original_bytes)
    # SN is at byte offset 32 (reg 116), 8 bytes; verify zeroed
    assert scrubbed_bytes[32:40] == b"\x00" * 8, f"SN bytes not zeroed: {scrubbed_bytes[32:40].hex()}"
    # Non-SN bytes preserved
    assert scrubbed_bytes[:32] == original_bytes[:32], "Bytes before SN should be preserved"
    assert scrubbed_bytes[40:124] == original_bytes[40:124], "Bytes after SN should be preserved"


def test_scrub_zeroes_inv_base_sn_bytes(ac2a, ac2a_inv_base_bytes):
    raw_hex = ac2a_inv_base_bytes.hex()
    br = BlockResult(status="pass", fields_parsed=10, raw=raw_hex)
    t1 = TierResult(tier=1, status="pass", blocks={"1100": br})
    report = build_report(ac2a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    scrubbed = report["tier_1"]["blocks"]["1100"]["raw"]
    scrubbed_bytes = bytes.fromhex(scrubbed)
    original_bytes = ac2a_inv_base_bytes
    # invSN is at byte offset 14 (reg 1107), 8 bytes
    assert scrubbed_bytes[14:22] == b"\x00" * 8, f"invSN bytes not zeroed: {scrubbed_bytes[14:22].hex()}"
    assert scrubbed_bytes[:14] == original_bytes[:14]


def test_scrub_no_scrub_flag_preserves_raw_bytes(ac2a, ac2a_home_bytes):
    raw_hex = ac2a_home_bytes.hex()
    br = BlockResult(status="pass", fields_parsed=23, raw=raw_hex)
    t1 = TierResult(tier=1, status="pass", blocks={"100": br})
    report = build_report(ac2a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {}, scrub=False)
    preserved = report["tier_1"]["blocks"]["100"]["raw"]
    assert preserved == raw_hex


def test_scrubbed_home_hex_still_parses(ac2a, ac2a_home_bytes):
    raw_hex = ac2a_home_bytes.hex()
    br = BlockResult(status="pass", fields_parsed=23, raw=raw_hex)
    t1 = TierResult(tier=1, status="pass", blocks={"100": br})
    report = build_report(ac2a, "REAL-SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    scrubbed_hex = report["tier_1"]["blocks"]["100"]["raw"]
    scrubbed_bytes = bytes.fromhex(scrubbed_hex)
    parsed = ac2a.parse(100, scrubbed_bytes)
    assert parsed.get("deviceSN") == "0", f"Parsed SN should be '0', got {parsed.get('deviceSN')}"


def test_scrub_iot_block_zeros_mac_ip(ac2a):
    iot_bytes = bytes([0xAB] * 70)
    raw_hex = iot_bytes.hex()
    br = BlockResult(status="pass", fields_parsed=10, raw=raw_hex)
    t1 = TierResult(tier=1, status="pass", blocks={"11000": br})
    report = build_report(ac2a, "SN", "AA:BB:CC:DD:EE:FF", [t1], {})
    scrubbed = report["tier_1"]["blocks"]["11000"]["raw"]
    scrubbed_bytes = bytes.fromhex(scrubbed)
    # iot_sn: 12-19
    assert scrubbed_bytes[12:20] == b"\x00" * 8, "IoT module SN bytes must be zeroed"
    # wifi_ip: 40-43, wifi_gateway: 44-47, wifi_mask: 48-51
    assert scrubbed_bytes[40:52] == b"\x00" * 12
    # wifi_mac: 54-59, ble_mac: 60-65
    assert scrubbed_bytes[54:66] == b"\x00" * 12
    # Non-sensitive bytes preserved
    assert scrubbed_bytes[:12] == iot_bytes[:12]
    assert scrubbed_bytes[20:40] == iot_bytes[20:40]
    assert scrubbed_bytes[52:54] == iot_bytes[52:54]
    assert scrubbed_bytes[66:70] == iot_bytes[66:70]
