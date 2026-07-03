# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest

from voltkeeper.core.devices.bluetti_device import BluettiDevice


class TestBluettiDeviceBase:
    def test_parse_raises_not_implemented(self):
        """Base parse() must raise NotImplementedError, not AttributeError."""
        device = BluettiDevice("00:00:00:00:00:00", "TEST", "SN")
        with pytest.raises(NotImplementedError):
            device.parse(100, b"\x00" * 4)

    def test_has_field_raises_not_implemented(self):
        device = BluettiDevice("00:00:00:00:00:00", "TEST", "SN")
        with pytest.raises(NotImplementedError):
            device.has_field("packTotalSoc")
