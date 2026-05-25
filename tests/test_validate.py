# ABOUTME: Tests for validate module — FieldVerdict, assess_field, validate_profile.


from voltkeeper.validate import FieldVerdict, assess_field, validate_profile

# ── assess_field unit tests ───────────────────────────────────────────


def test_assess_field_ok():
    v = assess_field("batterySOC", 75)
    assert v.name == "batterySOC"
    assert v.value == 75
    assert v.status == "ok"
    assert v.note == ""


def test_assess_field_stuck_at_zero():
    v = assess_field("totalPVPower", 0)
    assert v.status == "suspect"
    assert v.note == "stuck-at value"


def test_assess_field_stuck_at_0xFFFF():
    v = assess_field("rateVoltage", 0xFFFF)
    assert v.status == "suspect"
    assert v.note == "stuck-at value"


def test_assess_field_stuck_at_0xFFFFFFFF():
    v = assess_field("totalEnergy", 0xFFFFFFFF)
    assert v.status == "suspect"
    assert v.note == "stuck-at value"


def test_assess_field_nonzero_ok():
    v = assess_field("rateVoltage", 230)
    assert v.status == "ok"


def test_assess_field_with_range_in_range():
    v = assess_field("batterySOC", 50, expected_range=(0, 100))
    assert v.status == "ok"


def test_assess_field_with_range_out_of_range():
    v = assess_field("batterySOC", 150, expected_range=(0, 100))
    assert v.status == "suspect"
    assert "out of" in v.note


def test_assess_field_float_value():
    v = assess_field("voltage", 25.6)
    assert v.status == "ok"
    assert v.value == 25.6


def test_assess_field_string_value():
    v = assess_field("deviceModel", "AC2A")
    assert v.status == "ok"
    assert v.value == "AC2A"


def test_assess_field_boolean_true_not_suspect():
    v = assess_field("ac_output", True)
    assert v.status == "ok"


def test_assess_field_string_not_stuck_at():
    v = assess_field("deviceModel", "")
    assert v.status == "ok"  # empty string is valid, not a stuck-at signal


# ── validate_profile ──────────────────────────────────────────────────


def test_validate_profile_empty_yaml(tmp_path):
    """Empty blocks YAML → no verdicts."""
    import yaml

    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "UNKNOWN999",
        "encrypted": False,
        "protocol": "unknown",
        "protocol_version": None,
        "blocks": {},
    }
    yaml_path = tmp_path / "empty.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(profile, f)

    verdicts = validate_profile(str(yaml_path))
    assert verdicts == []


def test_validate_profile_unknown_device_no_parse(tmp_path):
    """Unknown model → raw hex comparison, no field-level parsing."""
    import yaml

    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "BOGUS999999",
        "encrypted": False,
        "protocol": "v1",
        "protocol_version": 1019,
        "blocks": {
            "BASE_REAL_DATA": {
                "address": 10,
                "size": 53,
                "raw_hex": "0000" * 53,
            }
        },
    }
    yaml_path = tmp_path / "bogus.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(profile, f)

    verdicts = validate_profile(str(yaml_path))
    # Unknown model: no field-level verdicts, just raw blocks recorded
    assert len(verdicts) == 0


def test_validate_profile_known_device_parses_fields(tmp_path):
    """AC2A profile → parse fields and assess each one."""
    import yaml

    # All-zero register data — most fields will be stuck-at 0 (suspect).
    zero53 = "00" * (53 * 2)
    zero70 = "00" * (70 * 2)

    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "AC2A2305000",
        "encrypted": False,
        "protocol": "v2",
        "protocol_version": 2000,
        "blocks": {
            "APP_HOME_DATA": {"address": 100, "size": 62, "raw_hex": "00" * (62 * 2)},
            "INV_BASE_INFO": {"address": 1100, "size": 51, "raw_hex": zero53},
            "INV_PV_INFO": {"address": 1200, "size": 70, "raw_hex": zero70},
            "INV_GRID_INFO": {"address": 1300, "size": 31, "raw_hex": "00" * (31 * 2)},
            "INV_LOAD_INFO": {"address": 1400, "size": 48, "raw_hex": "00" * (48 * 2)},
            "INV_INV_INFO": {"address": 1500, "size": 30, "raw_hex": "00" * (30 * 2)},
            "INV_BASE_SETTINGS": {"address": 2000, "size": 54, "raw_hex": "00" * (54 * 2)},
        },
    }
    yaml_path = tmp_path / "ac2a.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(profile, f)

    verdicts = validate_profile(str(yaml_path))

    names = {v.name for v in verdicts}
    assert "packTotalVoltage" in names
    assert any("packTotalSoc" in v.name for v in verdicts)

    for v in verdicts:
        assert v.status in ("ok", "suspect"), f"{v.name}: unexpected status {v.status}"


def test_field_verdict_repr():
    v = FieldVerdict("test", 42, "ok")
    assert repr(v) == "FieldVerdict(name='test', value=42, status='ok')"
