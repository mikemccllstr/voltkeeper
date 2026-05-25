# ABOUTME: Battery pack device definitions — HB500S (model 4025) and BH500E (model 4026).
# ABOUTME: TODO(hardware): verify protocol version, register layout, and data fields against physical device.

from ..commands import ReadHoldingRegisters
from ..struct import DeviceStruct
from .bluetti_device import BluettiDevice
from .v2_base import PACK_ITEM_INFO, PACK_MAIN_INFO


class BatteryPackBase(BluettiDevice):
    """Base class for battery pack devices. Uses PACK_MAIN_INFO and PACK_ITEM_INFO blocks.

    TODO(hardware): verify register layout against physical device.
    """

    has_battery_packs = True

    def __init__(self, address: str, type: str, sn: str):
        self.pack_main_struct = DeviceStruct()
        self._build_pack_main_struct()

        self.pack_item_struct = DeviceStruct()
        self._build_pack_item_struct()

        super().__init__(address, type, sn)

    def _build_pack_main_struct(self):
        s = self.pack_main_struct
        s.add_decimal_field("packVoltage", PACK_MAIN_INFO, 2)
        s.add_decimal_field("packCurrent", PACK_MAIN_INFO + 1, 2)
        s.add_uint_field("packSoc", PACK_MAIN_INFO + 2)
        s.add_temperature_field("packTemperature", PACK_MAIN_INFO + 3, 0)
        s.add_bcd_sn_field("packSerial", PACK_MAIN_INFO + 4, 4)
        s.add_uint_field("cycleCount", PACK_MAIN_INFO + 8)

    def _build_pack_item_struct(self):
        s = self.pack_item_struct
        for i in range(16):
            s.add_uint_field(f"cellVoltage{i + 1}", PACK_ITEM_INFO + i)

    def parse(self, address: int, data: bytes) -> dict:
        if PACK_MAIN_INFO <= address < PACK_ITEM_INFO:
            return self.pack_main_struct.parse(address, data)
        elif PACK_ITEM_INFO <= address < PACK_MAIN_INFO + 300:
            return self.pack_item_struct.parse(address, data)
        return {}

    @property
    def polling_commands(self) -> list[ReadHoldingRegisters]:
        return [
            ReadHoldingRegisters(PACK_MAIN_INFO, 32),
        ]

    @property
    def logging_commands(self) -> list[ReadHoldingRegisters]:
        return self.polling_commands


class HB500S(BatteryPackBase):
    """HB500S — Battery pack (model 4025)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "HB500S", sn)


class BH500E(BatteryPackBase):
    """BH500E — Battery pack (model 4026)."""

    def __init__(self, address: str, sn: str):
        super().__init__(address, "BH500E", sn)
