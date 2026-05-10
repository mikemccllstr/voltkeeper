# ABOUTME: Regression test against a real AC2A probe capture (synthetic SN).
# ABOUTME: Locks the BcdSerialField APK-equivalent dispatch so future drift
# ABOUTME: in deviceSN / invSN parsing surfaces immediately.

from pathlib import Path

import yaml

from src.bluetti_cli.core.devices.ac2a import AC2A
from src.bluetti_cli.core.struct import BcdSerialField

FIXTURE = Path(__file__).parent / "fixtures" / "ac2a_probe_real.yml"

# The fixture's raw_hex was captured from a real AC2A; the SN bytes were
# substituted with values that the APK getDeviceSN algorithm decodes back
# to this synthetic 13-digit number (matches the BLE-name suffix in the
# fixture).
EXPECTED_SN = "1234567890123"


def _load_profile() -> dict:
    return yaml.safe_load(FIXTURE.read_text())


def _parse_block(device: AC2A, block_info: dict) -> dict:
    return device.parse(block_info["address"], bytes.fromhex(block_info["raw_hex"]))


def test_bcd_sn_field_apk_equivalent_roundtrip():
    """BcdSerialField mirrors the APK getDeviceSN algorithm.

    Walks byte pairs end-to-start, appends each pair in original byte
    order (not swapped), parses concatenated hex as a ULong, returns
    decimal. See ProtocolParse.getDeviceSN in the decompiled APK.
    """
    f = BcdSerialField("sn", 116, 4)
    # Bytes produced by encoding 1234567890123 the way the APK reads it.
    assert f.parse(bytes.fromhex("04cb71fb011f0000")) == "1234567890123"
    # All-zero input parses to "0" (integer zero stringified).
    assert f.parse(bytes(8)) == "0"


def test_ac2a_probe_real_device_sn():
    """Live AC2A APP_HOME_DATA parses to the synthetic SN."""
    profile = _load_profile()
    device = AC2A(profile["address"], "0")
    parsed = _parse_block(device, profile["blocks"]["APP_HOME_DATA"])
    assert parsed["deviceSN"] == EXPECTED_SN
    assert parsed["deviceModel"] == "AC2A"


def test_ac2a_probe_real_inv_sn():
    """Live AC2A INV_BASE_INFO parses to the same SN as APP_HOME_DATA."""
    profile = _load_profile()
    device = AC2A(profile["address"], "0")
    parsed = _parse_block(device, profile["blocks"]["INV_BASE_INFO"])
    assert parsed["invSN"] == EXPECTED_SN
    assert parsed["invType"] == "AC2A"


def test_ac2a_probe_real_pack_voltage_scale():
    """÷100 voltage-scale override produces a plausible 8S LiFePO4 pack reading."""
    profile = _load_profile()
    device = AC2A(profile["address"], "0")
    parsed = _parse_block(device, profile["blocks"]["APP_HOME_DATA"])
    # Captured from a charged AC2A; expect 25.0–30.0 V (8S LiFePO4 nominal 25.6).
    voltage = float(parsed["packTotalVoltage"])
    assert 25.0 <= voltage <= 30.0, f"packTotalVoltage={voltage} outside plausible range"
    assert parsed["packTotalSoc"] == 100


def test_ac2a_probe_real_full_validate_no_errors():
    """validate-profile against the fixture must report zero errors.

    Mirrors the Unit 12 done-when criterion ('AC2A's probe output
    validates with zero ERROR entries'), pinned to a specific capture.
    """
    from src.bluetti_cli.validate import validate_profile

    verdicts = validate_profile(str(FIXTURE))
    errors = [v for v in verdicts if v.status == "error"]
    assert errors == [], f"unexpected parse errors: {errors}"
