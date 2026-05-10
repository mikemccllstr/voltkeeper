# ABOUTME: Tests for the SN-scrub helper used by probe/annotate before YAML write.
# ABOUTME: Round-trip property: a scrubbed profile parses back to the synthetic SN.

import yaml

from src.bluetti_cli.core.devices.ac2a import AC2A
from src.bluetti_cli.scrub import (
    SN_LOCATIONS,
    SYNTHETIC_SN_BYTES,
    SYNTHETIC_SN_HEX,
    SYNTHETIC_SN_STR,
    scrub_name,
    scrub_profile,
    scrub_raw_hex,
    split_model_sn,
)

# ── scrub_name ────────────────────────────────────────────────────────


def test_scrub_name_replaces_sn_suffix():
    assert scrub_name("AC2A2339003931765") == f"AC2A{SYNTHETIC_SN_STR}"
    assert scrub_name("EB3A1234567890") == f"EB3A{SYNTHETIC_SN_STR}"
    assert scrub_name("AC200L987654321") == f"AC200L{SYNTHETIC_SN_STR}"


def test_scrub_name_idempotent():
    once = scrub_name("AC2A2339003931765")
    twice = scrub_name(once)
    assert once == twice


def test_scrub_name_unrecognized_passthrough():
    # Doesn't match the prefix+digits pattern → unchanged.
    assert scrub_name("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"
    assert scrub_name("") == ""
    assert scrub_name("AC2A") == "AC2A"  # no digits


# ── scrub_raw_hex ─────────────────────────────────────────────────────


def test_scrub_raw_hex_app_home_data():
    """V2 SN at byte 32 of APP_HOME_DATA gets replaced; rest untouched."""
    real = "00" * 32 + "9c75977f02200000" + "FF" * 30
    scrubbed = scrub_raw_hex("APP_HOME_DATA", real)
    assert scrubbed[:64] == "00" * 32
    assert scrubbed[64:80] == SYNTHETIC_SN_HEX
    assert scrubbed[80:] == "FF" * 30


def test_scrub_raw_hex_inv_base_info():
    """V2 invSN at byte 14 of INV_BASE_INFO gets replaced."""
    real = "AB" * 14 + "9c75977f02200000" + "CD" * 30
    scrubbed = scrub_raw_hex("INV_BASE_INFO", real)
    assert scrubbed[:28] == "AB" * 14
    assert scrubbed[28:44] == SYNTHETIC_SN_HEX
    assert scrubbed[44:] == "CD" * 30


def test_scrub_raw_hex_v1_base_real_data():
    """V1 SN at byte 22 of BASE_REAL_DATA gets replaced."""
    real = "00" * 22 + "deadbeefcafef00d" + "11" * 30
    scrubbed = scrub_raw_hex("BASE_REAL_DATA", real)
    assert scrubbed[:44] == "00" * 22
    assert scrubbed[44:60] == SYNTHETIC_SN_HEX
    assert scrubbed[60:] == "11" * 30


def test_scrub_raw_hex_unknown_block_passthrough():
    raw = "deadbeef" * 8
    assert scrub_raw_hex("INV_PV_INFO", raw) == raw
    assert scrub_raw_hex("UNKNOWN", raw) == raw


def test_scrub_raw_hex_short_buffer_passthrough():
    """Buffer too short to contain SN bytes → returned unchanged."""
    raw = "ab" * 10  # only 10 bytes; APP_HOME_DATA SN starts at byte 32
    assert scrub_raw_hex("APP_HOME_DATA", raw) == raw


# ── scrub_profile ─────────────────────────────────────────────────────


def test_scrub_profile_replaces_name_and_blocks():
    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "AC2A2339003931765",
        "encrypted": False,
        "blocks": {
            "APP_HOME_DATA": {"address": 100, "size": 62, "raw_hex": "00" * 32 + "9c75977f02200000" + "00" * 30},
            "INV_BASE_INFO": {"address": 1100, "size": 51, "raw_hex": "00" * 14 + "9c75977f02200000" + "00" * 30},
            "INV_PV_INFO": {"address": 1200, "size": 70, "raw_hex": "00" * 70},  # untouched
        },
    }
    scrubbed = scrub_profile(profile)

    assert scrubbed["name"] == f"AC2A{SYNTHETIC_SN_STR}"
    assert SYNTHETIC_SN_HEX in scrubbed["blocks"]["APP_HOME_DATA"]["raw_hex"]
    assert SYNTHETIC_SN_HEX in scrubbed["blocks"]["INV_BASE_INFO"]["raw_hex"]
    assert "9c75977f02200000" not in scrubbed["blocks"]["APP_HOME_DATA"]["raw_hex"]
    assert "9c75977f02200000" not in scrubbed["blocks"]["INV_BASE_INFO"]["raw_hex"]
    # PV block has no SN, untouched
    assert scrubbed["blocks"]["INV_PV_INFO"]["raw_hex"] == "00" * 70


def test_scrub_profile_does_not_mutate_input():
    profile = {
        "name": "AC2A2339003931765",
        "blocks": {
            "APP_HOME_DATA": {"address": 100, "size": 62, "raw_hex": "00" * 32 + "9c75977f02200000" + "00" * 30},
        },
    }
    snapshot = yaml.safe_dump(profile)
    _ = scrub_profile(profile)
    assert yaml.safe_dump(profile) == snapshot


def test_scrub_profile_idempotent():
    profile = {
        "name": "AC2A2339003931765",
        "blocks": {
            "APP_HOME_DATA": {"address": 100, "size": 62, "raw_hex": "00" * 32 + "9c75977f02200000" + "00" * 30},
        },
    }
    once = scrub_profile(profile)
    twice = scrub_profile(once)
    assert once == twice


def test_scrub_profile_handles_missing_blocks():
    """Annotate-style profile (no `blocks` key) gets name scrubbed only."""
    profile = {"name": "AC2A2339003931765", "annotations": []}
    scrubbed = scrub_profile(profile)
    assert scrubbed["name"] == f"AC2A{SYNTHETIC_SN_STR}"
    assert scrubbed["annotations"] == []


# ── End-to-end: scrubbed profile parses back to synthetic SN ─────────


def test_scrubbed_profile_parses_to_synthetic_sn():
    """The whole point: parsing a scrubbed profile yields SYNTHETIC_SN_STR.

    Locks the round-trip property between the SN bytes the scrubber
    splices in and the BcdSerialField parser.
    """
    # Synthesize a probe-shaped profile with real-looking SN bytes
    profile = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "AC2A2339003931765",
        "blocks": {
            "APP_HOME_DATA": {
                "address": 100,
                "size": 62,
                # all-zero except the SN region
                "raw_hex": ("00" * 32) + "9c75977f02200000" + ("00" * 30),
            },
            "INV_BASE_INFO": {
                "address": 1100,
                "size": 51,
                "raw_hex": ("00" * 14) + "9c75977f02200000" + ("00" * 80),
            },
        },
    }

    scrubbed = scrub_profile(profile)
    device = AC2A("00:00:00:00:00:00", "0")

    home = device.parse(100, bytes.fromhex(scrubbed["blocks"]["APP_HOME_DATA"]["raw_hex"]))
    assert home["deviceSN"] == SYNTHETIC_SN_STR

    inv = device.parse(1100, bytes.fromhex(scrubbed["blocks"]["INV_BASE_INFO"]["raw_hex"]))
    assert inv["invSN"] == SYNTHETIC_SN_STR


# ── split_model_sn helper ────────────────────────────────────────────


def test_split_model_sn():
    assert split_model_sn("AC2A2339003931765") == ("AC2A", "2339003931765")
    assert split_model_sn("EB3A0000123456") == ("EB3A", "0000123456")
    assert split_model_sn("AC200PL987654321") == ("AC200PL", "987654321")
    assert split_model_sn("AA:BB:CC:DD:EE:FF") is None
    assert split_model_sn("") is None


# ── Constants sanity ─────────────────────────────────────────────────


def test_synthetic_sn_constants_consistent():
    """SYNTHETIC_SN_BYTES, _HEX, and _STR all describe the same SN."""
    assert SYNTHETIC_SN_BYTES.hex() == SYNTHETIC_SN_HEX
    # All three known SN locations are 8 bytes long.
    for block_name, (_, length) in SN_LOCATIONS.items():
        assert length == 8, f"{block_name}: expected 8-byte SN, got {length}"
