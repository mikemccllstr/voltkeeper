# ABOUTME: Unit tests for voltkeeper.bluetooth module — registry dispatch, build_device, scan classification.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voltkeeper.bluetooth import (
    PREFIX_ENCRYPTED,
    PREFIX_PLAINTEXT,
    ScanResult,
    _classify,
    build_device,
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
