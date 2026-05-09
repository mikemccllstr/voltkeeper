# ABOUTME: Unit tests for bluetti_cli.bluetooth module — registry dispatch, build_device, scan classification.
# ABOUTME: Units 1 and 3 per IMPLEMENTATION_UNITS.md.

from unittest.mock import MagicMock

import pytest

from src.bluetti_cli.bluetooth import _PREFIX_ENCRYPTED, PREFIX_PLAINTEXT, ScanResult, _classify, build_device


def test_build_device_rejects_unknown():
    with pytest.raises(ValueError, match="Unsupported device model"):
        build_device("AA:BB:CC:DD:EE:FF", "EP600123456")


class TestClassify:
    def test_plaintext(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: PREFIX_PLAINTEXT + b"\x00\x01\x02"}
        assert _classify(adv) is False

    def test_encrypted_bluette(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: _PREFIX_ENCRYPTED[0] + b"\xaa\xbb"}
        assert _classify(adv) is True

    def test_encrypted_bluettf(self):
        adv = MagicMock()
        adv.manufacturer_data = {0xFFFF: _PREFIX_ENCRYPTED[1] + b"\xcc\xdd"}
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
