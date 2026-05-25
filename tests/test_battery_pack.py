# ABOUTME: Tests for battery pack register parsing in V2Base.

from decimal import Decimal

from voltkeeper.core.devices.v2_base import PACK_ITEM_INFO, PACK_MAIN_INFO, V2Base


class TestPackMainStruct:
    def test_parses_voltage_current_soc(self):
        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")

        data = bytearray(20)
        data[0:2] = (2560).to_bytes(2, "big")  # packVoltage: 2560 → 25.60 V
        data[2:4] = (1500).to_bytes(2, "big")  # packCurrent: 1500 → 15.00 A
        data[4:6] = (85).to_bytes(2, "big")  # packSoc: 85%
        data[6] = 65  # packTemperature: 65 → 25 °C (65-40)

        parsed = v2.pack_main_struct.parse(PACK_MAIN_INFO, bytes(data))

        assert parsed["packVoltage"] == Decimal("25.60")
        assert parsed["packCurrent"] == Decimal("15.00")
        assert parsed["packSoc"] == 85
        assert parsed["packTemperature"] == 25

    def test_temperature_zero_returns_none(self):
        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        data = bytearray(8)
        # temperature raw = 0 → None (not valid)

        parsed = v2.pack_main_struct.parse(PACK_MAIN_INFO, bytes(data))
        assert parsed.get("packTemperature") is None


class TestPackItemStruct:
    def test_parses_cell_voltages(self):
        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")

        data = bytearray(32)
        data[0:2] = (3200).to_bytes(2, "big")  # cell 1: 3200 mV
        data[2:4] = (3210).to_bytes(2, "big")  # cell 2: 3210 mV
        data[4:6] = (3180).to_bytes(2, "big")  # cell 3: 3180 mV
        data[6:8] = (3220).to_bytes(2, "big")  # cell 4: 3220 mV

        parsed = v2.pack_item_struct.parse(PACK_ITEM_INFO, bytes(data))

        assert parsed["cellVoltage1"] == 3200
        assert parsed["cellVoltage2"] == 3210
        assert parsed["cellVoltage3"] == 3180
        assert parsed["cellVoltage4"] == 3220


class TestV2PollingCommands:
    def test_ac2a_excludes_pack_by_default(self):
        from voltkeeper.core.devices.ac2a import AC2A

        d = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
        addrs = {cmd.starting_address for cmd in d.polling_commands}
        assert PACK_MAIN_INFO not in addrs

    def test_v2_with_packs_includes_pack_registers(self):
        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.has_battery_packs = True
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert PACK_MAIN_INFO in addrs

    def test_v2_with_sub_devices_includes_node_info(self):
        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.has_sub_devices = True
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 21000 in addrs
