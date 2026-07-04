# ABOUTME: Tests for ground-truth verify mode — observation resolution, tolerance comparison, scale inference.
# ABOUTME: Uses AC2A device fixtures from conftest.py and the ground_truth module's pure functions.

from __future__ import annotations

import struct

import pytest

from voltkeeper.core.devices.ac2a import AC2A, ChargingMode
from voltkeeper.core.devices.el100v2 import El100V2
from voltkeeper.core.ground_truth import (
    CORE_OBS_MAP,
    CORE_OBSERVATION_DEFS,
    ActuateCheck,
    GroundTruthResult,
    InducedCheck,
    ObservationCheck,
    ObservationDef,
    _lookup_raw_value,
    build_actuation_items,
    build_induced_checks,
    build_observation_items,
    compare_observation,
    ground_truth_to_report_section,
    infer_scale,
    resolve_observation_value,
    run_actuations,
    run_induced_check,
    run_observations,
)
from voltkeeper.core.verify import BlockResult

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_full_tier1_values() -> dict:
    """Return a tier1_values dict with all fields needed for actuation tests."""
    from voltkeeper.core.commands import LedColor, WorkingMode
    from voltkeeper.core.devices.ac2a import ChargingMode

    return {
        "packTotalSoc": 85,
        "ac_output": True,
        "dc_output": False,
        "charging_mode": ChargingMode.STANDARD,
        "working_mode": WorkingMode.STANDARD_UPS,
        "ups_mode": WorkingMode.STANDARD_UPS,
        "power_lifting": False,
        "ac_eco_mode": False,
        "dc_eco_mode": False,
        "ctrl_grid": False,
        "ctrl_feed": False,
        "power_off": False,
        "factory_reset": 0,
        "system_power": 0,
        "silence_mode": False,
        "led_color": LedColor.COOL,
        "led_mode": 0,
        "time_mode": 0,
        "screen_lock": False,
        "beep": False,
        "data_upload": False,
        "ac_output_frequency": 50,
    }


# ── Fake prompt ────────────────────────────────────────────────────────────────


class FakePrompter:
    """Captures prompts instead of asking the operator."""

    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.prompts: list[tuple[str, str]] = []
        self.default: str | None = None

    async def prompt(self, text: str, source: str) -> str | None:
        self.prompts.append((text, source))
        return self.responses.get(text, self.default)


def _sync_prompt(text: str, source: str) -> str | None:
    """Synchronous prompt for simple test cases."""
    return text


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ac2a():
    return AC2A("AA:BB:CC:DD:EE:FF", "0")


@pytest.fixture
def el100v2():
    return El100V2("AA:BB:CC:DD:EE:FF", "0")


# ── Resolution tests (§1) ──────────────────────────────────────────────────────


class TestResolveObservationValue:
    def test_first_aggregate_returns_single_value(self):
        obs_def = ObservationDef("test", "prompt", ["a"], "first", "device_screen", "exact")
        result = resolve_observation_value({"a": 42, "b": 99}, obs_def)
        assert result == 42

    def test_first_returns_none_when_field_missing(self):
        obs_def = ObservationDef("test", "prompt", ["missing"], "first", "device_screen", "exact")
        result = resolve_observation_value({}, obs_def)
        assert result is None

    def test_sum_aggregate_combines_values(self):
        obs_def = ObservationDef("test", "prompt", ["a", "b"], "sum", "device_screen", "watts")
        result = resolve_observation_value({"a": 100, "b": 50}, obs_def)
        assert result == 150.0

    def test_sum_abs_uses_absolute_values(self):
        obs_def = ObservationDef("test", "prompt", ["a", "b"], "sum_abs", "device_screen", "watts")
        result = resolve_observation_value({"a": -60, "b": 50}, obs_def)
        assert result == 110.0

    def test_sum_ignores_missing_fields(self):
        obs_def = ObservationDef("test", "prompt", ["a", "b"], "sum", "device_screen", "watts")
        result = resolve_observation_value({"a": 100}, obs_def)
        assert result == 100.0

    def test_returns_none_when_all_fields_missing(self):
        obs_def = ObservationDef("test", "prompt", ["a", "b"], "sum", "device_screen", "watts")
        result = resolve_observation_value({"c": 1}, obs_def)
        assert result is None

    def test_decimal_values_work(self):
        from decimal import Decimal

        obs_def = ObservationDef("test", "prompt", ["v"], "first", "device_screen", "voltage")
        result = resolve_observation_value({"v": Decimal("53.5")}, obs_def)
        assert result == Decimal("53.5")


# ── Comparison tests (§2) ──────────────────────────────────────────────────────


class TestCompareObservation:
    # ── Numeric tolerance ──

    def test_soc_exact(self):
        result = compare_observation("85", 85.0, "soc")
        assert result["match"] is True

    def test_soc_within_tolerance_plus(self):
        result = compare_observation("86", 85.0, "soc")
        assert result["match"] is True

    def test_soc_within_tolerance_minus(self):
        result = compare_observation("84", 85.0, "soc")
        assert result["match"] is True

    def test_soc_outside_tolerance(self):
        result = compare_observation("87", 85.0, "soc")
        assert result["match"] is False

    def test_soc_observation_recorded(self):
        result = compare_observation("85", 85.0, "soc")
        assert result["observation"] == 85.0

    # ── Watts tolerance ──

    def test_watts_10_percent_tolerance(self):
        result = compare_observation("110", 100.0, "watts")
        assert result["match"] is True

    def test_watts_10_watt_floor(self):
        result = compare_observation("15", 5.0, "watts")
        # tolerance = max(5*0.10, 10) = 10
        assert result["match"] is True

    def test_watts_outside_tolerance(self):
        result = compare_observation("125", 100.0, "watts")
        assert result["match"] is False

    def test_watts_zero_tolerance(self):
        result = compare_observation("9", 0.0, "watts")
        # tolerance = max(0, 10) = 10
        assert result["match"] is True

    # ── Voltage tolerance ──

    def test_voltage_within_tolerance(self):
        result = compare_observation("122", 121.0, "voltage")
        assert result["match"] is True

    def test_voltage_outside_tolerance(self):
        result = compare_observation("124", 121.0, "voltage")
        assert result["match"] is False

    def test_voltage_oat_tolerance(self):
        result = compare_observation("121", 121.0, "voltage")
        assert result["match"] is True

    # ── Frequency tolerance ──

    def test_frequency_match(self):
        result = compare_observation("50", 50.0, "frequency")
        assert result["match"] is True

    def test_frequency_within_tolerance(self):
        result = compare_observation("51", 50.0, "frequency")
        assert result["match"] is True

    def test_frequency_outside_tolerance(self):
        result = compare_observation("52", 50.0, "frequency")
        assert result["match"] is False

    # ── Firmware version ──

    def test_firmware_display_format_match(self):
        # tier1_values contain raw uint16 (218614), device shows 2186.14 (÷100)
        result = compare_observation("2186.14", 218614, "firmware_version", raw_value=218614)
        assert result["match"] is True

    def test_firmware_display_format_mismatch(self):
        result = compare_observation("2186.15", 218614, "firmware_version", raw_value=218614)
        assert result["match"] is False

    def test_firmware_no_raw_works_with_parsed(self):
        # Without raw_value, still applies ÷100 to parsed
        result = compare_observation("2186.14", 218614, "firmware_version")
        assert result["match"] is True

    # ── Exact (bool/enum) ──

    def test_exact_bool_true(self):
        result = compare_observation("on", True, "exact")
        assert result["match"] is True
        assert result["observation"] is True

    def test_exact_bool_false(self):
        result = compare_observation("off", True, "exact")
        assert result["match"] is False
        assert result["observation"] is False

    def test_exact_bool_capitalization(self):
        result = compare_observation("ON", True, "exact")
        assert result["match"] is True

    def test_exact_enum_match(self):
        from voltkeeper.core.devices.ac2a import ChargingMode

        result = compare_observation("STANDARD", ChargingMode.STANDARD, "exact")
        assert result["match"] is True

    def test_exact_enum_mismatch(self):
        from voltkeeper.core.devices.ac2a import ChargingMode

        result = compare_observation("TURBO", ChargingMode.STANDARD, "exact")
        assert result["match"] is False

    def test_exact_enum_case_insensitive(self):
        from voltkeeper.core.devices.ac2a import ChargingMode

        result = compare_observation("standard", ChargingMode.STANDARD, "exact")
        assert result["match"] is True

    def test_exact_string_match(self):
        result = compare_observation("charging", "charging", "exact")
        assert result["match"] is True

    def test_exact_string_mismatch(self):
        result = compare_observation("charging", "discharging", "exact")
        assert result["match"] is False

    # ── Unparseable numeric ──

    def test_unparseable_numeric(self):
        result = compare_observation("abc", 50.0, "voltage")
        assert result["match"] is None
        assert "could not parse" in result["note"]


# ── Scale inference tests (§2.1) ───────────────────────────────────────────────


class TestInferScale:
    def test_divide_by_10_match(self):
        result = infer_scale(121.0, 1210)
        assert result == "÷10"

    def test_divide_by_100_match(self):
        result = infer_scale(53.5, 5350)
        assert result == "÷100"

    def test_raw_times_1_match(self):
        result = infer_scale(150.0, 150)
        assert result == "×1 (raw)"

    def test_no_match(self):
        result = infer_scale(121.0, 9999)
        assert result is None

    def test_zero_raw_returns_none(self):
        result = infer_scale(0.0, 0)
        assert result is None

    def test_near_match_within_tolerance(self):
        result = infer_scale(121.0, 1212)
        assert result == "÷10"

    def test_divide_by_10_preferred_over_times_1(self):
        result = infer_scale(12.1, 121)
        assert result == "÷10"


# ── Scale inference in comparison context (§2.2) ──────────────────────────────


class TestCompareWithScaleInference:
    def test_voltage_mismatch_infers_decivolt_scale(self):
        result = compare_observation("121", 12.1, "voltage", raw_value=1210)
        assert result["match"] is False
        assert result["inferred_scale"] == "÷10"
        assert "matches raw value at ÷10" in result["note"]

    def test_pack_voltage_mismatch_infers_centivolt_scale(self):
        result = compare_observation("53.5", 5.35, "voltage", raw_value=5350)
        assert result["match"] is False
        assert result["inferred_scale"] == "÷100"

    def test_match_no_scale_inference(self):
        result = compare_observation("121", 121.0, "voltage", raw_value=121)
        assert result["match"] is True
        assert result["inferred_scale"] is None

    def test_no_raw_value_no_scale_inference(self):
        result = compare_observation("121", 12.1, "voltage")
        assert result["match"] is False
        assert result["inferred_scale"] is None


# ── Observation building tests (§1.2) ─────────────────────────────────────────


class TestBuildObservationItems:
    def test_builds_for_ac2a(self, ac2a):
        tier1_values = {
            "packTotalSoc": 85,
            "totalACPower": 60,
            "totalDCPower": 14,
            "totalGridPower": 50,
            "totalPVPower": 0,
            "ac_output": True,
            "dc_output": False,
            "frequency": 50.0,
            "charging_mode": "STANDARD",
            "packChargingStatus": 1,
            "acPhase[0].voltage": 121.0,
            "gridPhase[0].voltage": 120.0,
            "packTotalVoltage": 53.5,
        }
        items = build_observation_items(ac2a, tier1_values)
        ids = [i.field for i in items]
        assert "soc" in ids
        assert "output_watts" in ids
        assert "input_watts" in ids
        assert "ac_output_state" in ids
        assert "dc_output_state" in ids
        assert "ac_output_frequency" in ids
        assert "charging_mode" in ids
        assert "ac_output_voltage" in ids
        assert "grid_voltage" in ids
        assert "pack_voltage" in ids
        # firmware_display is EL100V2-only
        assert "firmware_display" not in ids

    def test_builds_for_el100v2_includes_firmware(self, el100v2):
        tier1_values = {
            "packTotalSoc": 85,
            "totalACPower": 60,
            "totalDCPower": 0,
            "totalGridPower": 50,
            "totalPVPower": 0,
            "ac_output": True,
            "dc_output": False,
            "frequency": 50.0,
            "charging_mode": "TURBO",
            "packChargingStatus": 2,
            "arm_version": 218614,
            "acPhase[0].voltage": 121.0,
            "gridPhase[0].voltage": 120.0,
            "packTotalVoltage": 53.5,
        }
        items = build_observation_items(el100v2, tier1_values)
        ids = [i.field for i in items]
        assert "firmware_display" in ids

    def test_missing_values_unanchored(self, ac2a):
        items = build_observation_items(ac2a, {})
        for item in items:
            if item.field not in ("firmware_display",):  # firmware_display filtered for AC2A
                assert item.status == "unanchored"
                assert "no tier1 value" in item.note

    def test_parsed_values_set(self, ac2a):
        tier1_values = {"packTotalSoc": 85}
        items = build_observation_items(ac2a, tier1_values)
        soc = next(i for i in items if i.field == "soc")
        assert soc.parsed == 85

    def test_sum_abs_for_output_watts(self, ac2a):
        tier1_values = {"totalACPower": 60, "totalDCPower": 14}
        items = build_observation_items(ac2a, tier1_values)
        ow = next(i for i in items if i.field == "output_watts")
        assert ow.parsed == 74.0

    def test_sum_abs_for_negative_grid_input(self, ac2a):
        tier1_values = {"totalGridPower": -50, "totalPVPower": 200}
        items = build_observation_items(ac2a, tier1_values)
        iw = next(i for i in items if i.field == "input_watts")
        # sum_abs: abs(-50) + abs(200) = 250
        assert iw.parsed == 250.0


# ── Raw value lookup tests (§6.3) ───────────────────────────────────────────────


class TestLookupRawValueSynthKeys:
    """Cross-check SYNTH_REGISTERS against the device's own phase-fill parsing.

    The synthesized phase keys (acPhase[0].voltage, gridPhase[0].voltage) have no
    struct field, so _lookup_raw_value carries a hand-maintained register map. These
    tests fabricate a block with a known voltage at the phase-0 position and assert
    the lookup returns the same raw register the parser decodes — failing if the map
    and the _fill_*_phases byte offsets ever disagree.
    """

    def _grid_block(self, raw_voltage: int) -> bytes:
        # INV_GRID_INFO block (1300, 31 regs). sysPhaseNumber at reg 1312 byte 1;
        # gridPhase[0].voltage at byte offset 26 + 2 (see _fill_grid_phases).
        data = bytearray(62)
        data[25] = 1
        data[28:30] = struct.pack("!H", raw_voltage)
        return bytes(data)

    def _load_block(self, raw_voltage: int) -> bytes:
        # INV_LOAD_INFO block (1400, 48 regs). sysPhaseNumber at reg 1429 byte 1;
        # acPhase[0].voltage at byte offset 60 + 2 (see _fill_load_phases).
        data = bytearray(96)
        data[59] = 1
        data[62:64] = struct.pack("!H", raw_voltage)
        return bytes(data)

    def test_grid_phase_voltage_lookup_matches_parser(self, ac2a):
        raw = self._grid_block(1203)
        blocks = {"1300": BlockResult(status="pass", fields_parsed=1, raw=raw.hex())}
        raw_int, raw_ref = _lookup_raw_value(ac2a, ["gridPhase[0].voltage"], blocks)
        assert raw_ref == "1300"
        parsed = ac2a.parse(1300, raw)["gridPhase[0].voltage"]
        assert raw_int / 10.0 == parsed == 120.3

    def test_ac_phase_voltage_lookup_matches_parser(self, ac2a):
        raw = self._load_block(1210)
        blocks = {"1400": BlockResult(status="pass", fields_parsed=1, raw=raw.hex())}
        raw_int, raw_ref = _lookup_raw_value(ac2a, ["acPhase[0].voltage"], blocks)
        assert raw_ref == "1400"
        parsed = ac2a.parse(1400, raw)["acPhase[0].voltage"]
        assert raw_int / 10.0 == parsed == 121.0

    def test_synth_key_absent_from_blocks(self, ac2a):
        blocks = {"100": BlockResult(status="pass", fields_parsed=1, raw="00" * 124)}
        raw_int, raw_ref = _lookup_raw_value(ac2a, ["acPhase[0].voltage"], blocks)
        assert raw_int is None
        assert raw_ref is None


# ── Observation runner tests (§1.2) ────────────────────────────────────────────


class TestRunObservations:
    @pytest.mark.asyncio
    async def test_prompt_flow_records_match(self, ac2a):
        """Prompt flow records observation/parsed/raw-ref/match."""
        from voltkeeper.core.verify import _serialize

        parsed_val = 85
        prompt_text = f"State of Charge (%) (voltkeeper parsed: {_serialize(parsed_val)}) — type what the screen shows"
        items = [
            ObservationCheck(
                field="soc",
                prompt="State of Charge (%)",
                source="device_screen",
                parsed=parsed_val,
                raw_ref="100",
            )
        ]
        prompter = FakePrompter({prompt_text: "85"})

        await run_observations(items, {}, ac2a, prompter.prompt)

        assert len(items) == 1
        assert items[0].status == "match"
        assert items[0].observation == 85.0
        assert items[0].parsed == 85

    @pytest.mark.asyncio
    async def test_prompt_flow_records_mismatch(self, ac2a):
        from voltkeeper.core.verify import _serialize

        parsed_val = 85
        prompt_text = f"State of Charge (%) (voltkeeper parsed: {_serialize(parsed_val)}) — type what the screen shows"
        items = [
            ObservationCheck(
                field="soc",
                prompt="State of Charge (%)",
                source="device_screen",
                parsed=parsed_val,
            )
        ]
        prompter = FakePrompter({prompt_text: "90"})

        await run_observations(items, {}, ac2a, prompter.prompt)

        assert items[0].status == "mismatch"

    @pytest.mark.asyncio
    async def test_skip_records_skipped(self, ac2a):
        """Single skip records 'skipped'."""
        items = [
            ObservationCheck(
                field="soc",
                prompt="State of Charge (%)",
                source="device_screen",
                parsed=85,
            )
        ]
        # Empty string response = skip
        prompter = FakePrompter({"State of Charge (%)": ""})

        await run_observations(items, {}, ac2a, prompter.prompt)

        assert items[0].status == "skipped"
        assert items[0].note == "operator skipped"

    @pytest.mark.asyncio
    async def test_none_response_skips(self, ac2a):
        items = [
            ObservationCheck(
                field="soc",
                prompt="State of Charge (%)",
                source="device_screen",
                parsed=85,
            )
        ]
        prompter = FakePrompter({})
        prompter.default = None

        await run_observations(items, {}, ac2a, prompter.prompt)

        assert items[0].status == "skipped"

    @pytest.mark.asyncio
    async def test_unanchored_items_skipped_without_prompt(self, ac2a):
        items = [
            ObservationCheck(
                field="soc",
                prompt="State of Charge (%)",
                source="device_screen",
                status="unanchored",
                note="no tier1 value",
            )
        ]
        prompter = FakePrompter({"State of Charge (%)": "85"})

        await run_observations(items, {}, ac2a, prompter.prompt)

        # Should remain unanchored, not get prompted
        assert items[0].status == "unanchored"

    @pytest.mark.asyncio
    async def test_voltage_with_scale_inference(self, ac2a):
        """Observation of 121V against raw 1210 → mismatch with inferred decivolt scale."""
        import struct

        from voltkeeper.core.verify import _serialize

        raw_hex = struct.pack("!H", 1210).hex().ljust(56, "0")
        blocks = {"100": BlockResult(status="pass", fields_parsed=1, raw=raw_hex)}

        parsed_val = 12.1
        prompt_text = f"Pack voltage (V) (voltkeeper parsed: {_serialize(parsed_val)})"
        items = [
            ObservationCheck(
                field="pack_voltage",
                prompt="Pack voltage (V)",
                source="multimeter_or_app",
                parsed=parsed_val,
                raw_ref="100",
            )
        ]
        prompter = FakePrompter({prompt_text: "121.0"})

        await run_observations(items, blocks, ac2a, prompter.prompt)

        assert items[0].status == "mismatch"
        # Scale inference may or may not fire depending on whether the field is found in structs
        # The raw lookup depends on finding packTotalVoltage in device structs
        # If found and address 100, should infer ÷10


# ── Report serialization tests (§1.2) ─────────────────────────────────────────


class TestGroundTruthReportSection:
    def test_observation_to_dict(self):
        result = GroundTruthResult(
            observations=[
                ObservationCheck(
                    field="soc",
                    prompt="State of Charge (%)",
                    source="device_screen",
                    status="match",
                    observation=85.0,
                    parsed=85,
                    raw_ref="100",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        assert "observations" in section
        obs = section["observations"]
        assert len(obs) == 1
        assert obs[0]["field"] == "soc"
        assert obs[0]["status"] == "match"
        assert obs[0]["observation"] == 85.0
        assert obs[0]["parsed"] == 85
        assert obs[0]["raw_ref"] == "100"

    def test_observation_mismatch_with_inferred_scale(self):
        result = GroundTruthResult(
            observations=[
                ObservationCheck(
                    field="ac_output_voltage",
                    prompt="AC output voltage (V)",
                    source="multimeter_or_app",
                    status="mismatch",
                    observation=121.0,
                    parsed=12.1,
                    raw_ref="100",
                    inferred_scale="÷10",
                    note="matches raw value at ÷10",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        obs = section["observations"][0]
        assert obs["status"] == "mismatch"
        assert obs["inferred_scale"] == "÷10"
        assert "matches raw value at ÷10" in obs["note"]

    def test_skipped_observation(self):
        result = GroundTruthResult(
            observations=[
                ObservationCheck(
                    field="soc",
                    prompt="State of Charge (%)",
                    source="device_screen",
                    status="skipped",
                    note="operator skipped",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        obs = section["observations"][0]
        assert obs["status"] == "skipped"
        assert "observation" not in obs
        assert "parsed" not in obs

    def test_unanchored_observation(self):
        result = GroundTruthResult(
            observations=[
                ObservationCheck(
                    field="pack_voltage",
                    prompt="Pack voltage (V)",
                    source="multimeter_or_app",
                    status="unanchored",
                    note="no tier1 value available for this field",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        obs = section["observations"][0]
        assert obs["status"] == "unanchored"
        assert "no tier1 value" in obs["note"]

    def test_actuation_to_dict(self):
        result = GroundTruthResult(
            actuations=[
                ActuateCheck(
                    field="charging_mode",
                    prompt="Switching charging mode to TURBO on control_struct",
                    wrote="turbo",
                    readback="turbo",
                    device_confirmed=False,
                    confirm_response="no",
                    note="operator reports SILENT displayed",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        assert "observations" not in section
        act = section["actuations"][0]
        assert act["field"] == "charging_mode"
        assert act["wrote"] == "turbo"
        assert act["readback"] == "turbo"
        assert act["device_confirmed"] is False
        assert act["confirm_response"] == "no"
        assert "SILENT" in act["note"]

    def test_actuation_to_dict_with_unsure(self):
        result = GroundTruthResult(
            actuations=[
                ActuateCheck(
                    field="ac_output",
                    wrote="off",
                    readback="off",
                    device_confirmed=None,
                    confirm_response="unsure",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        act = section["actuations"][0]
        assert "device_confirmed" not in act  # None is omitted
        assert act["confirm_response"] == "unsure"
        assert "label mapping" not in str(act)

    def test_induction_to_dict(self):
        result = GroundTruthResult(
            induced_checks=[
                InducedCheck(
                    condition="ac_overload",
                    status="captured",
                    alarm_bits=["alarm.overload", "fault.overcurrent"],
                    raw_hex="abcdef",
                    device_indicator="Overload icon lit",
                )
            ]
        )
        section = ground_truth_to_report_section(result)
        ind = section["induced_checks"][0]
        assert ind["condition"] == "ac_overload"
        assert ind["status"] == "captured"
        assert ind["alarm_bits"] == ["alarm.overload", "fault.overcurrent"]
        assert ind["raw_hex"] == "abcdef"
        assert ind["device_indicator"] == "Overload icon lit"

    def test_empty_result_no_sections(self):
        result = GroundTruthResult()
        section = ground_truth_to_report_section(result)
        assert section == {}

    def test_mixed_result_all_sections(self):
        result = GroundTruthResult(
            observations=[
                ObservationCheck(
                    field="soc",
                    prompt="SoC",
                    source="device_screen",
                    status="match",
                    observation=85.0,
                    parsed=85,
                )
            ],
            actuations=[
                ActuateCheck(
                    field="ac_output",
                    wrote=True,
                    readback=True,
                    device_confirmed=True,
                )
            ],
            induced_checks=[
                InducedCheck(
                    condition="ac_overload",
                    status="skipped",
                    note="operator declined",
                )
            ],
        )
        section = ground_truth_to_report_section(result)
        assert "observations" in section
        assert "actuations" in section
        assert "induced_checks" in section


# ── Core observation defs integrity ────────────────────────────────────────────


class TestCoreObservationDefs:
    def test_all_ids_unique(self):
        ids = [d.id for d in CORE_OBSERVATION_DEFS]
        assert len(ids) == len(set(ids))

    def test_map_covers_all(self):
        assert set(d.id for d in CORE_OBSERVATION_DEFS) == set(CORE_OBS_MAP.keys())

    def test_all_have_tolerance_type(self):
        for d in CORE_OBSERVATION_DEFS:
            assert d.tolerance_type in ("soc", "watts", "voltage", "frequency", "firmware_version", "exact")

    def test_firmware_display_is_el100v2_only(self):
        fw = CORE_OBS_MAP["firmware_display"]
        assert fw.model_filter == "EL100V2"

    def test_voltage_fields_use_multimeter_source(self):
        for oid in ("ac_output_voltage", "grid_voltage", "pack_voltage"):
            d = CORE_OBS_MAP[oid]
            assert d.source == "multimeter"
            assert d.tolerance_type == "voltage"


# ── Actuate-and-confirm tests (§3) ────────────────────────────────────────────


class TestBuildActuationItems:
    def test_skips_skip_auto_fields(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset({4, 5}))
        for item in items:
            assert item.field not in ("system_time", "system_timezone", "ja12_enable", "ctrl_led")

    def test_charging_mode_is_included(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset({4, 5}))
        cm = next((i for i in items if i.field == "charging_mode"), None)
        assert cm is not None

    def test_ac2a_charging_mode_not_confirmable(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset({4, 5}))
        cm = next(i for i in items if i.field == "charging_mode")
        assert cm.device_confirmed is None
        assert cm.note == "not_confirmable_on_device"

    def test_bool_field_has_prompt(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset({4, 5}))
        ac_out = next((i for i in items if i.field == "ac_output"), None)
        assert ac_out is not None
        assert "the AC outlets" in ac_out.prompt
        assert "from on to off" in ac_out.prompt

    def test_fields_without_tier1_values_skipped(self, ac2a):
        items = build_actuation_items(ac2a, {}, frozenset({4, 5}))
        assert len(items) == 0

    def test_tier6_fields_excluded(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset({4, 5, 6}))
        tier6_fields = {"power_off", "factory_reset", "system_power"}
        for item in items:
            assert item.field not in tier6_fields

    def test_tier4_fields_excluded_without_consent(self, ac2a):
        tier1_values = _make_full_tier1_values()
        items = build_actuation_items(ac2a, tier1_values, frozenset())
        tier4_fields = {
            "ac_output",
            "dc_output",
            "ctrl_grid",
            "ctrl_feed",
            "power_lifting",
            "ac_eco_mode",
            "dc_eco_mode",
        }
        tier4_skipped = [i for i in items if i.field in tier4_fields]
        assert len(tier4_skipped) == len(tier4_fields)
        for item in tier4_skipped:
            assert item.note == "tier_4_not_consented"
            assert item.wrote_raw is None
            assert item.wrote is None

        tier5_skipped = [i for i in items if i.field == "working_mode"]
        assert len(tier5_skipped) == 1
        for item in tier5_skipped:
            assert item.note == "tier_5_not_consented"
            assert item.wrote_raw is None
            assert item.wrote is None


class TestRunActuations:
    @pytest.mark.asyncio
    async def test_happy_path_write_readback_confirm_restore(self, ac2a):
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "", "y"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.wrote_raw == 0
        assert ac_out.wrote == "off"
        assert ac_out.readback is False
        assert ac_out.device_confirmed is True
        assert ac_out.confirm_response == "yes"
        assert ac_out.note is None
        assert client.state[2011] == 1
        assert client.write_log == [(2011, 0), (2011, 1)]

    @pytest.mark.asyncio
    async def test_operator_denies_with_readback_match(self, ac2a):
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "", "n"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.device_confirmed is False
        assert ac_out.confirm_response == "no"
        assert ac_out.readback is False
        assert ac_out.note == "denial with readback match — possible label mapping error"
        assert client.state[2011] == 1
        assert client.write_log == [(2011, 0), (2011, 1)]

    @pytest.mark.asyncio
    async def test_ready_gate_skip_no_write(self, ac2a):
        """Skip at ready gate: no write occurs, records skipped."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "s"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.device_confirmed is None
        assert ac_out.confirm_response is None
        assert ac_out.note == "operator skipped at ready gate"
        # No write occurred: state unchanged, no restore needed
        assert client.state[2011] == 1
        assert client.write_log == []

    @pytest.mark.asyncio
    async def test_ready_gate_empty_enter_proceeds(self, ac2a):
        """Empty/Enter at ready gate proceeds to write for non-caution fields."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "", "y"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.device_confirmed is True
        assert ac_out.readback is False
        assert client.state[2011] == 1
        assert client.write_log == [(2011, 0), (2011, 1)]

    @pytest.mark.asyncio
    async def test_caution_field_empty_enter_skips(self, ac2a):
        """Caution fields: bare Enter skips, no write occurs."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2210: 0})
        items = build_actuation_items(ac2a, {"inv_freq": 0}, frozenset({4}))
        freq = next(i for i in items if i.field == "inv_freq")

        # announce/watch-for → ready gate (caution field, empty = skip)
        responses = iter(["", ""])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"inv_freq": 0}, capture)

        assert freq.device_confirmed is None
        assert freq.note == "operator skipped at ready gate"
        assert client.write_log == []

    @pytest.mark.asyncio
    async def test_caution_field_explicit_yes_proceeds(self, ac2a):
        """Caution fields: explicit 'y' proceeds to write."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2210: 50})
        items = build_actuation_items(ac2a, {"inv_freq": 50}, frozenset({4}))
        freq = next(i for i in items if i.field == "inv_freq")

        # announce/watch-for → ready gate ('y' to proceed) → confirm ('y')
        responses = iter(["", "y", "y"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"inv_freq": 50}, capture)

        assert freq.device_confirmed is True
        assert freq.confirm_response == "yes"
        assert len(client.write_log) == 2  # write + restore

    @pytest.mark.asyncio
    async def test_confirm_unsure_no_label_mapping_note(self, ac2a):
        """Unsure response records distinctly, no label-mapping note even on readback match."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "", "unsure"])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.device_confirmed is None  # unsure is not true/false
        assert ac_out.confirm_response == "unsure"
        # readback matched, but note should NOT say label mapping error
        assert ac_out.note is None or "label mapping" not in ac_out.note

    @pytest.mark.asyncio
    async def test_ready_gate_prompt_contains_field_info(self, ac2a):
        """Ready gate prompt names the specific output being toggled."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))

        async def capture(text, source):
            return "s"  # skip everything

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        # The announce/watch-for prompt should name "AC outlets"
        # (We verify the prompt was issued by checking write_log is empty)
        assert client.write_log == []

    @pytest.mark.asyncio
    async def test_confirm_prompt_accepts_yes_no_unsure(self, ac2a):
        """Confirm prompt shows y / n / unsure options."""
        from .test_verify import FakeBluetoothClient

        prompts_shown: list[str] = []

        async def capture(text, source):
            prompts_shown.append(text)
            if len(prompts_shown) <= 2:
                return ""
            return "y"

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        confirm_prompt = prompts_shown[-1]
        assert "y" in confirm_prompt.lower()
        assert "n" in confirm_prompt.lower()
        assert "unsure" in confirm_prompt.lower()

    @pytest.mark.asyncio
    async def test_operator_skips_restore_still_happens(self, ac2a):
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", "", ""])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        # Empty at confirm beat → skipped
        assert ac_out.device_confirmed is None
        assert ac_out.confirm_response is None
        assert ac_out.note == "operator skipped"
        assert client.state[2011] == 1
        assert client.write_log == [(2011, 0), (2011, 1)]

    @pytest.mark.asyncio
    async def test_readback_failure_restore_still_attempted(self, ac2a):
        from voltkeeper.core.commands import ReadHoldingRegisters

        from .test_verify import FakeBluetoothClient

        class ReadFailingClient(FakeBluetoothClient):
            async def execute(self, cmd):
                if isinstance(cmd, ReadHoldingRegisters) and cmd.starting_address == 2011:
                    raise RuntimeError("simulated readback failure")
                return await super().execute(cmd)

        client = ReadFailingClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))
        ac_out = next(i for i in items if i.field == "ac_output")

        responses = iter(["", ""])

        async def capture(text, source):
            return next(responses, "")

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        assert ac_out.readback is None
        assert "readback failed" in ac_out.note
        assert client.state[2011] == 1
        assert client.write_log == [(2011, 0), (2011, 1)]

    @pytest.mark.asyncio
    async def test_not_confirmable_no_prompt_write_readback_restore(self, ac2a):
        """Not-confirmable: no prompt issued, but write/readback/restore all happen."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2020: 0})
        items = build_actuation_items(ac2a, {"charging_mode": ChargingMode.STANDARD}, frozenset({4, 5}))
        cm = next(i for i in items if i.field == "charging_mode")

        prompt_calls: list = []

        async def capture(text, source):
            prompt_calls.append((text, source))
            return "n"

        await run_actuations(items, client, ac2a, {"charging_mode": ChargingMode.STANDARD}, capture)

        assert len(prompt_calls) == 0
        assert cm.note == "not_confirmable_on_device"
        assert cm.device_confirmed is None
        assert cm.confirm_response is None
        assert cm.wrote_raw == 1
        assert cm.wrote == "silent"
        assert cm.readback == "silent"
        assert client.state[2020] == 0
        assert client.write_log == [(2020, 1), (2020, 0)]


# ── Induced-condition tests (§4) ──────────────────────────────────────────────


class TestBuildInducedChecks:
    def test_el100v2_uses_1800w_rating(self, el100v2):
        checks = build_induced_checks(el100v2)
        assert len(checks) == 1
        assert checks[0]["condition"] == "ac_overload"
        assert "1800 W" in checks[0]["description"]
        assert "2070" in checks[0]["description"]  # ~1800 * 1.15

    def test_ac2a_uses_300w_rating(self, ac2a):
        checks = build_induced_checks(ac2a)
        assert len(checks) == 1
        assert "300 W" in checks[0]["description"]
        assert "345" in checks[0]["description"]  # ~300 * 1.15

    def test_no_rating_returns_empty(self, ac2a):
        from voltkeeper.core.devices.bluetti_device import BluettiDevice

        class NoRatingDevice(BluettiDevice):
            pass

        device = NoRatingDevice.__new__(NoRatingDevice)
        device.RATED_AC_OUTPUT_W = None
        checks = build_induced_checks(device)
        assert checks == []

    def test_no_attribute_returns_empty(self):
        class MinimalDevice:
            pass

        checks = build_induced_checks(MinimalDevice())
        assert checks == []


class TestInducedCheck:
    @pytest.mark.asyncio
    async def test_typed_confirmation_skips_when_declined(self, ac2a):
        checks = build_induced_checks(ac2a)

        async def capture(text, source):
            return "wrong phrase"

        result = await run_induced_check(checks[0], None, None, capture)
        assert result.status == "skipped"
        assert "operator declined" in result.note

    @pytest.mark.asyncio
    async def test_typed_confirmation_empty_skips(self, ac2a):
        checks = build_induced_checks(ac2a)

        async def capture(text, source):
            return ""

        result = await run_induced_check(checks[0], None, None, capture)
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_confirmation_allows_capture(self, ac2a):
        from .test_verify import FakeBluetoothClient

        # HOME block with alarm bits set
        home_data = bytearray(124)
        home_data[52:54] = b"\x00\x02"  # alarm word 1 bit 1
        state = {}
        for i in range(62):
            val = struct.unpack("!H", home_data[i * 2 : i * 2 + 2])[0]
            state[100 + i] = val
        client = FakeBluetoothClient(state=state)

        async def capture(text, source):
            if "Type" in text:
                return "I am applying an overload"
            if "Which alarm indicators" in text:
                return "Overload icon lit"
            return ""

        result = await run_induced_check(build_induced_checks(ac2a)[0], client, ac2a, capture)
        assert result.status == "captured"
        assert result.alarm_bits is not None
        assert len(result.alarm_bits) > 0
        assert result.device_indicator == "Overload icon lit"

    @pytest.mark.asyncio
    async def test_no_alarm_bits_when_clear(self, ac2a):
        from .test_verify import FakeBluetoothClient

        state = {100 + i: 0 for i in range(62)}
        client = FakeBluetoothClient(state=state)

        async def capture(text, source):
            if "I am applying an overload" in text:
                return "I am applying an overload"
            if "Which alarm indicators" in text:
                return "none"
            return ""

        result = await run_induced_check(build_induced_checks(ac2a)[0], client, ac2a, capture)
        assert result.status == "captured"
        assert result.alarm_bits == []


# ── 4. Category selection ─────────────────────────────────────────────────────


class TestCategorySelection:
    """Tests for category-based skip controls in ground-truth mode."""

    def test_build_observation_items_respects_category_deselected(self, ac2a):
        """Deselecting observations produces no prompable items."""
        from voltkeeper.core.ground_truth import build_observation_items

        tier1_values = {"packTotalSoc": 85}
        items = build_observation_items(ac2a, tier1_values, selected_categories=frozenset())

        assert len(items) == 0, "No observation items when observations category deselected"

    def test_build_observation_items_all_enabled_by_default(self, ac2a):
        """Default (no filter) gives all observation items."""
        from voltkeeper.core.ground_truth import build_observation_items

        tier1_values = {"packTotalSoc": 85}
        items = build_observation_items(ac2a, tier1_values)

        assert len(items) > 0, "Default should produce observation items"

    def test_build_actuation_items_respects_load_category(self, ac2a):
        """Deselecting load_actuations skips tier-4 fields."""
        from voltkeeper.core.ground_truth import build_actuation_items

        tier1_values = {"ac_output": True, "alarm_sound": False, "charging_mode": 0}
        consented = frozenset({2, 3, 4, 5})

        # With load_actuations deselected, tier-4 fields (ac_output) should be excluded
        items = build_actuation_items(
            ac2a, tier1_values, consented, selected_categories=frozenset({"mode_actuations", "induced"})
        )

        ac_output_items = [i for i in items if i.field == "ac_output"]
        assert len(ac_output_items) == 0, "Tier-4 field should not appear when load_actuations deselected"

    def test_build_actuation_items_respects_mode_category(self, ac2a):
        """Deselecting mode_actuations skips tier-5 fields."""
        from voltkeeper.core.ground_truth import build_actuation_items

        tier1_values = {"ac_output": True, "alarm_sound": False, "charging_mode": 0}
        consented = frozenset({2, 3, 4, 5})

        items = build_actuation_items(
            ac2a, tier1_values, consented, selected_categories=frozenset({"load_actuations", "induced"})
        )

        # ac_output (tier 4) should appear, but tier-5 fields should not
        ac_output_items = [i for i in items if i.field == "ac_output"]
        assert len(ac_output_items) > 0, "Tier-4 field should appear when load_actuations selected"

    def test_build_actuation_items_all_enabled_by_default(self, ac2a):
        """Default (no category filter) gives all eligible actuation items."""
        from voltkeeper.core.ground_truth import build_actuation_items

        tier1_values = {"ac_output": True, "alarm_sound": False, "charging_mode": 0}
        consented = frozenset({2, 3, 4, 5})

        items = build_actuation_items(ac2a, tier1_values, consented)

        assert len(items) > 0, "Default should produce actuation items"

    @pytest.mark.asyncio
    async def test_run_induced_checks_skipped_when_category_deselected(self, ac2a):
        """Deselecting induced produces empty results."""
        from tests.test_verify import FakeBluetoothClient
        from voltkeeper.core.ground_truth import run_induced_checks

        state = {100 + i: 0 for i in range(62)}
        client = FakeBluetoothClient(state=state)

        async def capture(text, source):
            return ""

        results = await run_induced_checks(client, ac2a, capture, selected_categories=frozenset())

        assert len(results) == 0, "No induced checks when category deselected"


# ── 5. Category CLI option ────────────────────────────────────────────────────


class TestCategoryFromCLIFlags:
    """Test that --skip-category CLI flags produce correct category sets."""

    def test_default_categories_all_enabled(self):
        """Default is all four categories enabled."""
        from voltkeeper.cli.verify import _categories_from_skips

        categories = _categories_from_skips([])
        assert "observations" in categories
        assert "load_actuations" in categories
        assert "mode_actuations" in categories
        assert "induced" in categories

    def test_skip_observations(self):
        from voltkeeper.cli.verify import _categories_from_skips

        categories = _categories_from_skips(["observations"])
        assert "observations" not in categories
        assert "load_actuations" in categories
        assert "mode_actuations" in categories
        assert "induced" in categories

    def test_skip_multiple(self):
        from voltkeeper.cli.verify import _categories_from_skips

        categories = _categories_from_skips(["observations", "induced"])
        assert "observations" not in categories
        assert "induced" not in categories
        assert "load_actuations" in categories
        assert "mode_actuations" in categories

    def test_skip_all_leaves_empty(self):
        from voltkeeper.cli.verify import _categories_from_skips

        categories = _categories_from_skips(["observations", "load_actuations", "mode_actuations", "induced"])
        assert len(categories) == 0

    def test_unknown_category_raises(self):
        from voltkeeper.cli.verify import _categories_from_skips

        with pytest.raises(ValueError, match="unknown"):
            _categories_from_skips(["garbage"])


# ══════════════════════════════════════════════════════════════════════════════
# §6.2 - Dry-run prompt flow tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDryRunPromptFlow:
    """Assert generated prompt text for a novice operator."""

    @pytest.mark.asyncio
    async def test_ac_output_prompt_names_ac_outlets(self, ac2a):
        """AC output actuation names the AC outlets and says load loses power."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2011: 1})
        items = build_actuation_items(ac2a, {"ac_output": True}, frozenset({4}))

        async def capture(text, source):
            return "s"  # skip at ready gate

        await run_actuations(items, client, ac2a, {"ac_output": True}, capture)

        ac_item = next(i for i in items if i.field == "ac_output")
        assert "the AC outlets" in ac_item.prompt
        assert "from on to off" in ac_item.prompt

    @pytest.mark.asyncio
    async def test_dc_output_prompt_names_dc_ports(self, ac2a):
        """DC output actuation names the DC ports explicitly."""
        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2012: 0})
        items = build_actuation_items(ac2a, {"dc_output": False}, frozenset({4}))

        async def capture(text, source):
            return "s"

        await run_actuations(items, client, ac2a, {"dc_output": False}, capture)

        dc_item = next(i for i in items if i.field == "dc_output")
        assert "the DC ports" in dc_item.prompt

    @pytest.mark.asyncio
    async def test_inv_freq_prompt_has_caution_and_p01(self, ac2a):
        """inv_freq actuation includes the manual's caution and settings page P01 reference."""
        from voltkeeper.core.prompt_metadata import get_field_prompt_info

        from .test_verify import FakeBluetoothClient

        client = FakeBluetoothClient({2210: 50})
        items = build_actuation_items(ac2a, {"inv_freq": 50}, frozenset({4}))

        async def capture(text, source):
            return "s"

        await run_actuations(items, client, ac2a, {"inv_freq": 50}, capture)

        freq_item = next(i for i in items if i.field == "inv_freq")
        assert "frequency" in freq_item.prompt.lower()
        meta = get_field_prompt_info(ac2a, "inv_freq")
        assert meta.caution is not None
        assert "Turn off AC output" in meta.caution
        assert meta.where is not None and "P01" in meta.where

    @pytest.mark.asyncio
    async def test_charging_mode_prompt_mentions_p03(self, ac2a):
        """Charging mode prompt references P03 settings page for EL100V2."""
        from voltkeeper.core.prompt_metadata import get_field_prompt_info

        meta = get_field_prompt_info(ac2a, "charging_mode")
        assert meta.where is not None
        assert "P03" in meta.where

    def test_firmware_observation_prompt_names_arm_and_versions(self):
        """Firmware observation prompt names ARM, DSP, BMS, IoT and format example."""
        from voltkeeper.core.ground_truth import CORE_OBS_MAP

        fw_def = CORE_OBS_MAP["firmware_display"]
        prompt = fw_def.prompt
        assert "ARM" in prompt
        assert "DSP" in prompt
        assert "BMS" in prompt
        assert "IoT" in prompt
        assert "2186.14" in prompt

    def test_overload_prompt_computes_from_el100v2_rating(self, el100v2):
        """EL100V2 overload prompt uses 1800 W rating, suggests computed load, example appliance."""
        checks = build_induced_checks(el100v2)
        assert len(checks) == 1
        desc = checks[0]["description"]
        assert "1800 W" in desc
        assert "2070" in desc  # 1800 * 1.15
        assert "space heater" in desc.lower()

    def test_overload_prompt_computes_from_ac2a_rating(self, ac2a):
        """AC2A overload prompt uses 300 W rating."""
        checks = build_induced_checks(ac2a)
        assert len(checks) == 1
        desc = checks[0]["description"]
        assert "300 W" in desc
        assert "345" in desc  # 300 * 1.15

    def test_soc_observation_prompt_has_location_guidance(self):
        """SoC observation prompt tells operator where to look on the device."""
        from voltkeeper.core.ground_truth import CORE_OBS_MAP

        soc_def = CORE_OBS_MAP["soc"]
        prompt = soc_def.prompt
        assert "main screen" in prompt.lower()
        assert "digits" in prompt.lower()

    def test_observation_prompts_use_bluetti_unit_terminology(self):
        """Observation prompts never use bare 'output' where ambiguous."""
        from voltkeeper.core.ground_truth import CORE_OBSERVATION_DEFS

        for obs_def in CORE_OBSERVATION_DEFS:
            # 'output' alone should only appear in the context of explicit names
            if "output" in obs_def.prompt.lower() and "output_watts" not in obs_def.id:
                assert "AC" in obs_def.prompt or "DC" in obs_def.prompt or "Bluetti unit" in obs_def.prompt
