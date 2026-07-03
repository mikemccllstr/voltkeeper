# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

import csv
from decimal import Decimal
from io import StringIO

import pytest

import voltkeeper.load_test as lt


class TestEnergyComputation:
    def test_single_step(self):
        result = lt._compute_energy(100, 200, 3600, 0)
        assert result == pytest.approx(150.0)

    def test_zero_delta(self):
        result = lt._compute_energy(100, 200, 0, 50)
        assert result == pytest.approx(50.0)

    def test_accumulate_over_steps(self):
        e = lt._compute_energy(0, 100, 1800, 0)
        assert e == pytest.approx(25.0)
        e = lt._compute_energy(100, 200, 1800, e)
        assert e == pytest.approx(100.0)

    def test_zero_power(self):
        result = lt._compute_energy(0, 0, 3600, 10)
        assert result == pytest.approx(10.0)

    def test_small_delta(self):
        result = lt._compute_energy(50, 50, 30, 0)
        assert result == pytest.approx(50 * 30 / 3600)


class TestSocBar:
    def test_100_percent(self):
        bar = lt._soc_bar(100)
        assert "░" not in bar
        assert len(bar) == lt.SOC_BAR_WIDTH

    def test_0_percent(self):
        bar = lt._soc_bar(0)
        assert "█" not in bar
        assert len(bar) == lt.SOC_BAR_WIDTH

    def test_50_percent(self):
        bar = lt._soc_bar(50)
        assert bar.count("█") == lt.SOC_BAR_WIDTH // 2
        assert bar.count("░") == lt.SOC_BAR_WIDTH // 2

    def test_none_is_all_blank(self):
        bar = lt._soc_bar(None)
        assert bar == "░" * lt.SOC_BAR_WIDTH

    def test_negative_clamped(self):
        bar = lt._soc_bar(-10)
        assert bar == "░" * lt.SOC_BAR_WIDTH

    def test_over_100_clamped(self):
        bar = lt._soc_bar(110)
        assert bar == "█" * lt.SOC_BAR_WIDTH


class TestBuildSample:
    def test_all_fields_present(self):
        home = {
            "packTotalSoc": 85,
            "packTotalVoltage": Decimal("26.5"),
            "packTotalCurrent": Decimal("18.2"),
            "totalDCPower": 50,
            "totalACPower": 400,
            "totalPVPower": 0,
            "totalGridPower": 0,
            "packChargingStatus": 2,
            "packDsgEmptyTime": 200,
            "ambientTemp": 30,
            "invMaxTemp": 42,
            "totalDCEnergy": Decimal("1250.5"),
        }
        sample = lt._build_sample(home, 120.0, "test phase")
        assert sample["soc_pct"] == 85
        assert sample["pack_v"] == Decimal("26.5")
        assert sample["dc_power_w"] == 50
        assert sample["ac_power_w"] == 400
        assert sample["total_power_w"] == 450
        assert sample["elapsed_s"] == 120.0
        assert sample["charging_status"] == "Discharging"
        assert sample["phase"] == "test phase"

    def test_missing_fields_become_empty_strings(self):
        sample = lt._build_sample({}, 0)
        assert sample["soc_pct"] == ""
        assert sample["pack_v"] == ""
        assert sample["ambient_temp_c"] == ""
        assert sample["inv_temp_c"] == ""
        assert sample["est_remaining_min"] == ""
        assert sample["energy_register_wh"] == ""

    def test_power_defaults_to_zero(self):
        sample = lt._build_sample({}, 0)
        assert sample["dc_power_w"] == 0
        assert sample["ac_power_w"] == 0
        assert sample["total_power_w"] == 0

    def test_negative_ac_power_abs(self):
        sample = lt._build_sample({"totalACPower": -300}, 0)
        assert sample["ac_power_w"] == 300

    def test_phase_defaults_to_empty(self):
        sample = lt._build_sample({}, 0)
        assert sample["phase"] == ""


class TestPreRequisites:
    def test_all_clear(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert warnings == []

    def test_soc_too_low(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 50,
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_soc_missing(self):
        warnings = lt._check_prerequisites(
            {
                "totalGridPower": 0,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "SOC" in warnings[0]

    def test_grid_too_high(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 200,
                "totalPVPower": 0,
            }
        )
        assert len(warnings) == 1
        assert "Grid" in warnings[0]

    def test_grid_just_under_limit(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 5,
                "totalPVPower": 0,
            }
        )
        assert warnings == []

    def test_pv_too_high(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 100,
                "totalGridPower": 0,
                "totalPVPower": 20,
            }
        )
        assert len(warnings) == 1
        assert "PV" in warnings[0]

    def test_multiple_warnings(self):
        warnings = lt._check_prerequisites(
            {
                "packTotalSoc": 40,
                "totalGridPower": 100,
                "totalPVPower": 30,
            }
        )
        assert len(warnings) == 3


class TestRuntimeWarnings:
    def test_no_warnings(self):
        assert lt._check_warnings({"grid_power_w": 0, "pv_power_w": 0}) == []

    def test_grid_above_threshold(self):
        warnings = lt._check_warnings({"grid_power_w": 15, "pv_power_w": 0})
        assert len(warnings) == 1
        assert "Grid" in warnings[0]

    def test_pv_above_threshold(self):
        warnings = lt._check_warnings({"grid_power_w": 0, "pv_power_w": 20})
        assert len(warnings) == 1
        assert "PV" in warnings[0]

    def test_grid_at_threshold_ok(self):
        assert lt._check_warnings({"grid_power_w": 10, "pv_power_w": 0}) == []

    def test_pv_at_threshold_ok(self):
        assert lt._check_warnings({"grid_power_w": 0, "pv_power_w": 10}) == []

    def test_both_above(self):
        warnings = lt._check_warnings({"grid_power_w": 50, "pv_power_w": 100})
        assert len(warnings) == 2

    def test_missing_keys_no_warning(self):
        assert lt._check_warnings({}) == []


class TestCSVHeader:
    def test_header_has_required_columns(self):
        assert "timestamp" in lt.CSV_COLUMNS
        assert "elapsed_s" in lt.CSV_COLUMNS
        assert "soc_pct" in lt.CSV_COLUMNS
        assert "pack_v" in lt.CSV_COLUMNS
        assert "energy_computed_wh" in lt.CSV_COLUMNS
        assert "energy_register_wh" in lt.CSV_COLUMNS
        assert "phase" in lt.CSV_COLUMNS

    def test_csv_columns_count(self):
        assert len(lt.CSV_COLUMNS) == 17

    def test_header_comment_block(self, ac2a_device):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_header(writer, ac2a_device, "test", 100, 60)
        content = buf.getvalue()
        assert "# voltkeeper load test" in content
        assert "# Device: AC2A-TEST" in content
        assert "# Phase: test" in content
        assert "# Expected load: 100 W" in content
        assert "# Interval: 60 s" in content
        assert "timestamp,elapsed_s" in content

    def test_header_without_optional_fields(self, ac2a_device):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_header(writer, ac2a_device, None, None, 60)
        content = buf.getvalue()
        assert "# Phase" not in content
        assert "# Expected load" not in content

    def test_csv_row_writes_all_columns(self):
        buf = StringIO()
        writer = csv.writer(buf)
        data = {col: f"val_{col}" for col in lt.CSV_COLUMNS}
        lt._write_csv_row(writer, data)
        content = buf.getvalue().strip()
        assert content.count(",") == len(lt.CSV_COLUMNS) - 1

    def test_csv_row_empty_for_missing_fields(self):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_row(writer, {"timestamp": "2026-01-01T00:00:00"})
        content = buf.getvalue().strip()
        values = content.split(",")
        assert values[0] == "2026-01-01T00:00:00"
        assert all(v == "" for v in values[1:])

    def test_csv_row_decimal_handling(self):
        buf = StringIO()
        writer = csv.writer(buf)
        lt._write_csv_row(writer, {"pack_v": Decimal("27.3"), "timestamp": "t"})
        content = buf.getvalue().strip()
        values = content.split(",")
        assert values[lt.CSV_COLUMNS.index("pack_v")] == "27.3"


class TestCsvAnalysis:
    _BASIC_CSV = (
        "# voltkeeper load test\n"
        "# Device: AC2A-TEST\n"
        "#\n"
        "timestamp,elapsed_s,soc_pct,pack_v,pack_a,total_power_w,energy_computed_wh,energy_register_wh,est_remaining_min,ambient_temp_c,inv_temp_c\n"
        "2026-01-01T00:00:00,0,100,27.0,0,0,0,1000.0,500,25,30\n"
        "2026-01-01T00:01:00,60,99,26.9,18,500,8.3,1008.3,490,26,31\n"
        "2026-01-01T00:02:00,120,98,26.8,18,500,16.7,1016.7,480,27,32\n"
        "2026-01-01T00:03:00,180,97,26.7,18,500,25.0,1025.0,470,28,33\n"
        "2026-01-01T00:04:00,240,96,26.6,18,500,33.3,1033.3,460,29,34\n"
    )

    def _write_csv(self, tmp_path, content=_BASIC_CSV):
        path = tmp_path / "test.csv"
        path.write_text(content)
        return str(path)

    def test_returns_none_for_short_csv(self, tmp_path):
        path = self._write_csv(tmp_path, "a,b\n1,2\n3,4\n5,6\n")
        assert lt._analyze_csv(path) is None

    def test_capacity_is_last_energy_computed(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["capacity_wh"] == pytest.approx(33.3)

    def test_register_delta(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["register_delta_wh"] == pytest.approx(1033.3 - 1000.0)

    def test_avg_and_peak_load(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["avg_load_w"] == pytest.approx(400)  # (0+500+500+500+500)/5
        assert result["peak_load_w"] == pytest.approx(500)

    def test_efficiency(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        # pack power: 0*0=0, 26.9*18=484.2, 26.8*18=482.4, 26.7*18=480.6, 26.6*18=478.8
        # avg pack = 385.2, avg out = 400, eff = 400/385.2*100 ≈ 103.8
        assert result["efficiency_pct"] is not None
        assert result["efficiency_pct"] > 0

    def test_voltage_at_soc_milestones(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        v = result["voltage_at_soc"]
        assert "100%" in v
        assert v["100%"] == pytest.approx(27.0)
        # 96% SOC is the lowest we have, should be recorded at some milestone
        assert v.get("75%") is None  # never reached 75%

    def test_bms_accuracy_at_50pct(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        # SOC never drops to 50% in this data, so no BMS accuracy
        assert result["bms_accuracy"] is None

    def test_bms_with_crossing_50(self, tmp_path):
        content = (
            "# test\n"
            "timestamp,elapsed_s,soc_pct,total_power_w,est_remaining_min,energy_computed_wh\n"
            "t0,0,100,0,600,0\n"
            "t1,600,60,500,300,100\n"
            "t2,1200,55,500,290,200\n"
            "t3,1800,49,500,240,300\n"
            "t4,2400,45,500,200,400\n"
            "t5,3000,0,500,0,500\n"
        )
        path = self._write_csv(tmp_path, content)
        result = lt._analyze_csv(path)
        # First row with SOC ≤ 50 is t3 (49%)
        assert result["bms_accuracy"] == pytest.approx(240)
        # total runtime = 3000s, t3 elapsed = 1800s, remaining = 1200s = 20 min
        assert result["actual_remaining_at_50pct"] == pytest.approx(20.0)

    def test_max_temperatures(self, tmp_path):
        path = self._write_csv(tmp_path)
        result = lt._analyze_csv(path)
        assert result["max_ambient_c"] == 29
        assert result["max_inverter_c"] == 34

    def test_missing_optional_columns(self, tmp_path):
        content = (
            "# test\n"
            "timestamp,elapsed_s,soc_pct,total_power_w,energy_computed_wh\n"
            "t0,0,100,0,0\n"
            "t1,60,99,500,8.3\n"
            "t2,120,98,500,16.7\n"
            "t3,180,97,500,25.0\n"
            "t4,240,96,500,33.3\n"
            "t5,300,0,500,50.0\n"
        )
        path = self._write_csv(tmp_path, content)
        result = lt._analyze_csv(path)
        assert result["capacity_wh"] == pytest.approx(50.0)
        assert result["register_delta_wh"] is None
        assert result["efficiency_pct"] is None
        assert result["voltage_at_soc"] == {}
        assert result["bms_accuracy"] is None
        assert result["max_ambient_c"] is None
