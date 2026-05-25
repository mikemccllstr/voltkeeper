# ABOUTME: AC500 larger inverter — V1 protocol (minProtocolVer=0 in Android, uses V1 writable regs).
# ABOUTME: NOTE(divergence): Unit 10 plan lists AC500 as V2Base, but the Android
# ABOUTME:   DeviceConnUtil.java sets minProtocolVer=0 and uses V1 writable
# ABOUTME:   register addresses (3000-3099). Follows Android source.
# ABOUTME: TODO(AC500): verify against hardware.

from enum import Enum, unique
from typing import List

from ..commands import ReadHoldingRegisters
from .v1_base import (
    AC_ECO_POWER,
    AC_SWITCH,
    CHARGING_MODE,
    CTRL_AC_ECO_MODE,
    DC_ECO_POWER,
    DC_SWITCH,
    ECO_AUTO_OFF,
    ECO_CONTROL,
    FEED_SWITCH,
    GRID_CHARGING_SWITCH,
    GRID_PLUS_MODE,
    HIGH_POWER_SETTINGS,
    INVERTER_FREQUENCY,
    LOW_POWER_SETTINGS,
    MACHINE_ADDRESS,
    MACHINE_MODE,
    MAX_CHARGING_CURRENT_OF_GRID,
    MAX_CHARGING_POWER,
    MAX_DISCHARGE_POWER,
    MAX_DISCHARGING_CURRENT,
    MAX_PV_CHARGE_CURRENT,
    OUTPUT_VOLTAGE,
    POWER_LIFTING_MODE,
    PV_CONTROL,
    SET_SYSTEM_FACTORY_RESET,
    SETTABLE_DATA,
    SYS_SWITCH_RECOVERY,
    SYSTEM_POWER_OFF,
    SYSTEM_TIME,
    WORKING_TIME,
    V1Base,
)


@unique
class ChargingMode(Enum):
    STANDARD = 0
    TURBO = 1
    SILENT = 2


@unique
class InverterFrequency(Enum):
    HZ50 = 50
    HZ60 = 60


class AC500(V1Base):
    """AC500 larger inverter. V1 protocol."""

    # Uses V1Base default ALARM_NAMES/FAULT_NAMES (ConnectConstants).

    WRITABLE_FIELD_NAMES = [
        "ac_output",
        "dc_output",
        "pv_control",
        "feed_switch",
        "grid_charging",
        "grid_plus_mode",
        "charging_mode",
        "power_lifting",
        "dc_eco_mode",
        "ac_eco_mode",
        "eco_off_time",
        "eco_auto_off",
        "dc_eco_power",
        "ac_eco_power",
        "system_power_off",
        "factory_reset",
        "inv_frequency",
        "output_voltage",
        "sys_switch_recovery",
        "machine_mode",
        "machine_address",
        "max_pv_charge_current",
        "low_power_settings",
        "high_power_settings",
        "max_discharging_current",
        "max_charging_current_of_grid",
        "system_time",
        "working_time",
        "max_charging_power",
        "max_discharge_power",
    ]

    def __init__(self, address: str, sn: str):
        super().__init__(address, "AC500", sn)
        self._build_control_struct()

    def _build_control_struct(self):
        s = self.control_struct
        s.add_bool_field("ac_output", AC_SWITCH)
        s.add_bool_field("dc_output", DC_SWITCH)
        s.add_bool_field("pv_control", PV_CONTROL)
        s.add_bool_field("feed_switch", FEED_SWITCH)
        s.add_bool_field("grid_charging", GRID_CHARGING_SWITCH)
        s.add_bool_field("grid_plus_mode", GRID_PLUS_MODE)
        s.add_enum_field("charging_mode", CHARGING_MODE, ChargingMode)
        s.add_bool_field("power_lifting", POWER_LIFTING_MODE)
        s.add_bool_field("dc_eco_mode", ECO_CONTROL)
        s.add_bool_field("ac_eco_mode", CTRL_AC_ECO_MODE)
        s.add_uint_field("eco_off_time", ECO_CONTROL + 1)
        s.add_uint_field("eco_auto_off", ECO_AUTO_OFF)
        s.add_uint_field("dc_eco_power", DC_ECO_POWER)
        s.add_uint_field("ac_eco_power", AC_ECO_POWER)
        s.add_bool_field("system_power_off", SYSTEM_POWER_OFF)
        s.add_bool_field("factory_reset", SET_SYSTEM_FACTORY_RESET)
        s.add_enum_field("inv_frequency", INVERTER_FREQUENCY, InverterFrequency)
        s.add_uint_field("output_voltage", OUTPUT_VOLTAGE)
        s.add_bool_field("sys_switch_recovery", SYS_SWITCH_RECOVERY)
        s.add_uint_field("machine_mode", MACHINE_MODE)
        s.add_uint_field("machine_address", MACHINE_ADDRESS)
        s.add_uint_field("max_pv_charge_current", MAX_PV_CHARGE_CURRENT)
        s.add_uint_field("low_power_settings", LOW_POWER_SETTINGS)
        s.add_uint_field("high_power_settings", HIGH_POWER_SETTINGS)
        s.add_uint_field("max_discharging_current", MAX_DISCHARGING_CURRENT)
        s.add_uint_field("max_charging_current_of_grid", MAX_CHARGING_CURRENT_OF_GRID)
        s.add_uint32_field("system_time", SYSTEM_TIME)
        s.add_uint_field("working_time", WORKING_TIME)
        s.add_uint_field("max_charging_power", MAX_CHARGING_POWER)
        s.add_uint_field("max_discharge_power", MAX_DISCHARGE_POWER)

    @property
    def control_commands(self) -> List[ReadHoldingRegisters]:
        return [ReadHoldingRegisters(SETTABLE_DATA, 100)]
