# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.struct import UintField


class TestUintFieldUnit:
    def test_unit_stored_when_provided(self):
        f = UintField("eco_time", 2015, unit="h")
        assert f.unit == "h"

    def test_unit_none_by_default(self):
        f = UintField("lcd_timeout", 2067)
        assert f.unit is None

    def test_unit_does_not_affect_range(self):
        f = UintField("sys_low_power", 2022, range=(0, 100), unit="%")
        assert f.in_range(50)
        assert not f.in_range(150)
