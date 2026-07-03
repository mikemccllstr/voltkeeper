# ABOUTME: Unit tests for voltkeeper.bluetooth module — registry dispatch, build_device, scan classification.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voltkeeper.bluetooth import (
    _DEVICE_NAME_SN_RE,
    PREFIX_ENCRYPTED,
    PREFIX_PLAINTEXT,
    ScanResult,
    _classify,
    build_device,
    contribution_hint,
    lookup_scan_result,
)


def test_build_device_rejects_unknown():
    with pytest.raises(ValueError, match="Unsupported device model"):
        build_device("AA:BB:CC:DD:EE:FF", "BOGUS999999")


class TestClassify:
    def test_plaintext(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: PREFIX_PLAINTEXT + b"\x00\x01\x02"}
        assert _classify(adv) is False

    def test_encrypted_bluette(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: PREFIX_ENCRYPTED[0] + b"\xaa\xbb"}
        assert _classify(adv) is True

    def test_encrypted_bluettf(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: PREFIX_ENCRYPTED[1] + b"\xcc\xdd"}
        assert _classify(adv) is True

    def test_unknown_empty(self):
        adv = MagicMock()
        adv.manufacturer_data = {}
        assert _classify(adv) is None

    def test_unknown_garbage(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: b"\xde\xad\xbe\xef"}
        assert _classify(adv) is None


class TestScanResult:
    def test_display_plaintext(self):
        r = ScanResult("AA:BB:CC:DD:EE:FF", "AC2A1234567", False)
        assert "[plaintext]" in r.display()

    def test_display_encrypted(self):
        r = ScanResult("AA:BB:CC:DD:EE:FF", "EP6001234567", True)
        assert "[encrypted]" in r.display()

    def test_display_unknown(self):
        r = ScanResult("AA:BB:CC:DD:EE:FF", "SomeDevice", None)
        assert "[unknown]" in r.display()


class TestLookupScanResult:
    @pytest.mark.asyncio
    async def test_encrypted(self):
        name = "EP6001234567"
        addr = "AA:BB:CC:DD:EE:FF"
        dev = MagicMock()
        dev.name = name
        adv = MagicMock()
        adv.local_name = name
        adv.manufacturer_data = {0xFFFF: PREFIX_ENCRYPTED[0] + b"\xaa\xbb"}
        with patch("voltkeeper.bluetooth.BleakScanner.discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = {addr: (dev, adv)}
            sr = await lookup_scan_result(addr)
            assert sr.address == addr
            assert sr.name == name
            assert sr.encrypted is True

    @pytest.mark.asyncio
    async def test_plaintext(self):
        name = "AC2A1234567"
        addr = "AA:BB:CC:DD:EE:FF"
        dev = MagicMock()
        dev.name = name
        adv = MagicMock()
        adv.local_name = name
        adv.manufacturer_data = {0xFFFF: PREFIX_PLAINTEXT + b"\x00\x01\x02"}
        with patch("voltkeeper.bluetooth.BleakScanner.discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = {addr: (dev, adv)}
            sr = await lookup_scan_result(addr)
            assert sr.address == addr
            assert sr.encrypted is False

    @pytest.mark.asyncio
    async def test_unknown(self):
        addr = "AA:BB:CC:DD:EE:FF"
        dev = MagicMock()
        dev.name = ""
        adv = MagicMock()
        adv.local_name = ""
        adv.manufacturer_data = {}
        with patch("voltkeeper.bluetooth.BleakScanner.discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = {addr: (dev, adv)}
            sr = await lookup_scan_result(addr)
            assert sr.address == addr
            assert sr.encrypted is None

    @pytest.mark.asyncio
    async def test_not_found_returns_default(self):
        addr = "AA:BB:CC:DD:EE:FF"
        with patch("voltkeeper.bluetooth.BleakScanner.discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = {}
            sr = await lookup_scan_result(addr)
            assert sr.address == addr
            assert sr.name == addr
            assert sr.encrypted is None


class TestDeviceNameRegex:
    def test_extracts_trailing_digits(self):
        assert _DEVICE_NAME_SN_RE.search("AC2A2305000")[0] == "2305000"
        assert _DEVICE_NAME_SN_RE.search("EB3A1234567")[0] == "1234567"
        assert _DEVICE_NAME_SN_RE.search("AC200L2305000")[0] == "2305000"
        assert _DEVICE_NAME_SN_RE.search("AC602305000")[0] == "602305000"

    def test_short_serial_matches(self):
        m = _DEVICE_NAME_SN_RE.search("EB3A1")
        assert m is not None
        assert m[0] == "1"

        m = _DEVICE_NAME_SN_RE.search("AC2A12")
        assert m is not None
        assert m[0] == "12"

    def test_new_model_sn_extraction(self):
        assert _DEVICE_NAME_SN_RE.search("HB500S1234567890123")[0] == "1234567890123"
        assert _DEVICE_NAME_SN_RE.search("BH500E1234567890123")[0] == "1234567890123"
        assert _DEVICE_NAME_SN_RE.search("AORA100_MINI20250101001")[0] == "20250101001"
        assert _DEVICE_NAME_SN_RE.search("AORA30_MINI123456789")[0] == "123456789"

    def test_non_matching_strings(self):
        assert _DEVICE_NAME_SN_RE.search("AA:BB:CC:DD:EE:FF") is None
        assert _DEVICE_NAME_SN_RE.search("AC2A") is None  # no digits
        assert _DEVICE_NAME_SN_RE.search("") is None

    def test_new_models_build_device(self):
        d = build_device("AA:BB:CC:DD:EE:FF", "AORA100_MINI20250101001")
        assert d.type == "AORA100_MINI"
        assert d.sn == "20250101001"

        d = build_device("AA:BB:CC:DD:EE:FF", "HB500S1234567890123")
        assert d.type == "HB500S"
        assert d.sn == "1234567890123"


class TestScanResultTier:
    def test_display_with_tier_verified(self):
        from voltkeeper.core.devices.bluetti_device import SupportTier

        r = ScanResult("AA:BB:CC:DD:EE:FF", "AC2A1234567", False)
        out = r.display(tier=SupportTier.HARDWARE_VERIFIED)
        assert "[plaintext]" in out
        assert "[hardware_verified]" in out

    def test_display_with_tier_apk_derived(self):
        from voltkeeper.core.devices.bluetti_device import SupportTier

        r = ScanResult("AA:BB:CC:DD:EE:FF", "EB3A1234567", False)
        out = r.display(tier=SupportTier.APK_DERIVED)
        assert "[plaintext]" in out
        assert "[apk_derived]" in out

    def test_display_without_tier_unknown_prefix(self):
        r = ScanResult("AA:BB:CC:DD:EE:FF", "BOGUS999999", None)
        out = r.display()
        assert "[unknown]" in out
        assert "hardware" not in out.lower()
        assert "apk" not in out.lower()

    def test_display_no_tier_no_exception(self):
        r = ScanResult("AA:BB:CC:DD:EE:FF", "AC2A1234567", False)
        out = r.display()
        assert "[plaintext]" in out

    def test_contribution_hint_non_verified(self):
        from voltkeeper.core.devices.bluetti_device import SupportTier

        hint = contribution_hint({SupportTier.APK_DERIVED, SupportTier.HARDWARE_VERIFIED})
        assert "test-your-device" in hint

    def test_contribution_hint_all_verified(self):
        from voltkeeper.core.devices.bluetti_device import SupportTier

        hint = contribution_hint({SupportTier.HARDWARE_VERIFIED})
        assert hint == ""

    def test_contribution_hint_empty(self):
        hint = contribution_hint(set())
        assert hint == ""
