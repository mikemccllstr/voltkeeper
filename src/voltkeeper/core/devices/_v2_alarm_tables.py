# ABOUTME: V2 alarm/fault name tables — shared by V2 model classes (APP_HOME_DATA, PACK_MAIN_INFO).
# ABOUTME: Ported verbatim from ConnConstantsV2.kt (APK v3.0.9), resolved via values-en/strings.xml.

# Source classes (APK v3.0.9):
#   net.poweroak.bluetticloud.ui.connectv2.tools.ConnConstantsV2
#   net.poweroak.bluetticloud.ui.connectv2.tools.ProtocolParserV2.parseHomeData
#
# Alarm words are read from APP_HOME_DATA (register 100):
#   alarmInfo: byte offsets 52–59 (4 × 16-bit words)  confirmed on AC2A
#   faultInfo: byte offsets 66–77 (6 × 16-bit words)  confirmed on AC2A
#
# Pack alarm words are read from PACK_MAIN_INFO (register 6000):
#   packSysErr:         byte offsets 76–81 (3 × 16-bit words)  not yet hardware-verified
#   packHighVoltAlarm:  byte offsets 82–83 (1 × 16-bit word)   not yet hardware-verified
#
# Table shape: dict[int, list[str | None]]
#   key   = 1-based word index
#   value = list of up to 16 entries (one per bit, LSB first); None = unused position


# ── Low-power warn/fault (single-phase portables: AC2A, AC60, AC180, EL*) ───────────────────────

LOW_POWER_WARN_NAMES: dict[int, list[str | None]] = {
    1: [
        "Grid voltage high",  # typo: lowercase in APK strings.xml
        "Grid Voltage Low",
        "Grid Frequency High",
        "Grid Frequency Low",
        "Grid Oscillation",
        "Networking Operation Abnormal",
        "Grid Connection Fault",
        "Accessory Malfunction",
        "PV Configuration Error",
        "Grid 2 Voltage High",
        "Grid 2 Voltage Low",
        "Grid 2 Frequency High",
        "Grid 2 Frequency Low",
        "Grid 2 Oscillation",
        "Grid Not Connected",
    ],
    2: [
        "Battery Pack Communication Abnormal",
        "IoT Communication Error",
        "UPS Input Overvoltage",
        "UPS Input Undervoltage",
        "UPS Input Overcurrent",
        "UPS Input Overtemperature",
        "UPS Precharge Fault",
        "UPS Hardware Fault",
    ],
}

LOW_POWER_FAULT_NAMES: dict[int, list[str | None]] = {
    1: [
        "Inverter Overload",
        "Inverter Over Temperature",
        "Inverter Short Circuit",
        "Inverter Output Fault",
        "LLC Output Error",
        "Bus Over Voltage/Hardware Bus Over Voltage",
        "BUS Low Voltage",
        "Hardware Inverter Overcurrent",
        "Hardware Input Overcurrent",
        "Battery Voltage High/Hardware Battery Over Voltage",
        "Battery Voltage Low",
        "Main Relay Failure",
        "Grid Relay Failure",
        "Calibration Fail",
        "Auxiliary Battery Malfunction",
        "Fan Error",
    ],
    2: [
        "Multihost Error",  # typo: APK spells it "Multihost"
        "Phase Loss",
        "Multi-machine Communication Abnormal",
        "Multi-machine Synchronization Abnormal",
        "Multi-machine Configuration Abnormal",
        "Generator Voltage Abnormal",
        "System Initialization Failure",
        "Parallel Relay Failure",
        "Grid Input Overcurrent",
        "System Overload",
        "DC Output Overload",
        "Inverter Low Temperature",
    ],
    3: [
        "PV1 Over Voltage",
        "PV2 Over Voltage",
        "PV3 Over Voltage",
        "PV1 Overcurrent",
        "PV2 Overcurrent",
        "PV3 Overcurrent",
        "PV1 Over Temperature",
        "PV2 Over Temperature",
        "PV3 Over Temperature",
        "PV Precharge Fault",
        "PV1 Hardware Error",
        "PV2 Hardware Error",
        "PV3 Hardware Error",
        "PV Insulation Resistance Fault",
    ],
    4: [
        "PV4 Over Voltage",
        "PV4 Overcurrent",
        "PV4 Over Temperature",
        "PV4 Hardware Error",
        "PV1 Low Temperature",
        "PV2 Low Temperature",
        "PV3 Low Temperature",
        "PV4 Low Temperature",
    ],
    5: [
        "DC Output Short Circuit",
        "DC Output Voltage High",
        "DC Output Current High",
        "DC Output Over Temperature",
        "DC Output Failure",
        "BMS Communication Failure",
        "Inverter String Communication Failure",
        "RTC Error",
        "EEPROM Error",
        "BMS System Fault",
        "Controller Temperature Too High",
        "Zero Drift Abnormal (DSP)",
        "DC Output Low Temperature",
        "Leakage Current Fault",
        "Insulation Resistance Fault",
    ],
}


# ── High-power warn/fault (3-phase home-power: EP600) ─────────────────────────────────────────

HIGH_POWER_WARN_NAMES: dict[int, list[str | None]] = {
    1: [
        "Grid Voltage High",
        "Grid Voltage Low",
        "Grid Frequency High",
        "Grid Frequency Low",
        "Grid Oscillation",
        "Grid Loss",
        "PV1 Voltage Low",
        "PV2 Voltage Low",
        "PV3 Voltage Low",
        "Generator Voltage Abnormal",
        "DSP_Debug CAN Communication Failure",
        "DSP_Debug RS485 Communication Failure",
        "Abnormal Grid Reconnection",
        "PV4 Voltage Low",
    ],
    # word 2: empty in APK (CollectionsKt.emptyList())
    3: [
        "EEPROM read error",  # typo: lowercase in APK strings.xml
        "Grid Voltage High-ARM",
        "Grid Voltage Low-ARM",
        "Grid Frequency High-ARM",
        "Grid Frequency Low-ARM",
        "USB Disk Format Error",
        "USB Disk Upgrade Error",
        "AFCI Error",
        "USB Communication Exception",
        "No USB Upgrade File",
        "CT Cable Direction Error",
        "AC PV Meter Communication Abnormal",
        "Arc module self-test failed",  # typo: lowercase in APK strings.xml
        "Arc module no communication",  # typo: lowercase in APK strings.xml
        "Data Deletion",
        "Loss of communication with WiFi module",  # typo: lowercase in APK strings.xml
    ],
    4: [
        "WiFi module network configuration failed",  # typo: lowercase in APK strings.xml
        "Frequent relay switching during the day",  # typo: lowercase in APK strings.xml
        "Frequent relay switching at present",  # typo: lowercase in APK strings.xml
        "WiFi not connected to server",  # typo: lowercase in APK strings.xml
        "Grid Meter Communication Abnormal",
        "Disable Battery Charging",
        "Disable Battery Discharging",
        "DRMS Shutdown",
        "Relay Status Alarm",
    ],
}

HIGH_POWER_FAULT_NAMES: dict[int, list[str | None]] = {
    1: [
        "Bus Over Voltage",
        "BUS2 Over Voltage",
        "BUS Low Voltage",
        "BUS2 Low Voltage",
        "Hardware Bus Over Voltage",
        "Hardware Bus2 Over Voltage",
        "Hardware Battery Over Voltage",
        "Hardware Inverter Over Current",
        "Hardware Inverter2 Over Current",
        "LLC1 Hardware Input Overcurrent",
        "LLC2 Hardware Input Overcurrent",
        "Balanced Circuit Input Overcurrent",
        "Auxiliary Power Voltage Low",
        "DC Component Error",
        "Relay Error",
        "PV Cable Direction Error",
    ],
    2: [
        "PV1 Overcurrent",
        "PV2 Overcurrent",
        "PV3 Overcurrent",
        "PV1 Voltage High",
        "PV2 Voltage High",
        "PV3 Voltage High",
        "PV ISO Error",
        "PV2 ISO Error",
        "PV3 ISO Error",
        "PV1 Hardware Error",
        "PV2 Hardware Error",
        "PV3 Hardware Error",
        "GFCI Hardware Circuit Error",
        "GFCI Error",
        "Phase Error",
        "Fan Error",
    ],
    3: [
        "Calibration Fail",
        "Hardware Input Over Current",
        "DC Input Voltage Low",
        "DC Input Voltage High",
        "DC Input Overcurrent",
        "LLC1 Output Overvoltage",
        "LLC1 Output Overvoltage",  # typo: APK maps fault3_07 to same EN string as fault3_06 (should be LLC2)
        "Inverter Over Load",
        "Inverter2 Over Load",
        "Inverter3 Over Load",
        "Inverter Output Failure",
        "Inverter2 Output Failure",
        "Inverter3 Output Failure",
        "Temperature Over High",
        "Communication failure",  # typo: lowercase in APK strings.xml
        "Low Temperature Protection",
    ],
    4: [
        "DSP Communication Interrupted",
        "BMS Communication Interrupted",
        "IoT Communication Interrupted",
        "Calibration Fail-ARM",
        "RTC Read Error",
        "Inverter Leakage Current High",
        "Operating Ambient Temperature Anomaly",
        "Temperature 1",
        "Temperature 2",
        "Temperature 3",
        "Temperature 4",
        "BMS Charging Protection",
        "BMS Discharging Protection",
        "BMS System Fault",
        "Parallel Connection Abnormal",
        "Battery Grounding Failure",
    ],
    5: [
        "PV Overvoltage",
        "LLC Output Voltage Low",
        "BUS Soft Startup Abnormal",
        "Connection error",  # typo: lowercase in APK strings.xml
        "Communication lost",  # typo: lowercase in APK strings.xml
        "PV4 Overcurrent",
        "PV4 Voltage High",
        "PV4 ISO Fault",
        "Hardware PV4 Fault",
        "AC Pre-charge Timeout",
        "Grid Connection Prohibited",
        "PV1 Reverse Polarity",
        "PV2 Reverse Polarity",
        "PV3 Reverse Polarity",
        "PV4 Reverse Polarity",
        "IGBT Fault",
    ],
    6: [
        "DC-DC Circuit Fault",
        "BUS Sampling Error",
        "Parallel Wiring Error",
        "Bus Voltage Imbalance",
        "Grid Overcurrent",
    ],
}


# ── Micro-inverter warn/fault (BalconySolar / micro-inverter family) ────────────────────────────

MICRO_INV_WARN_NAMES: dict[int, list[str | None]] = {
    1: [
        "PV array insulation impedance ISO anomaly",
    ],
}

MICRO_INV_FAULT_NAMES: dict[int, list[str | None]] = {
    1: [
        "Battery overvoltage",
        "Battery undervoltage",
        "Battery overcurrent",
        "Bus overvoltage",
        "Bus undervoltage",
        "Bus overcurrent",
        "Relay Error",
        "Poor contact with battery connection",
        "DC side relay open",
        "DC side relay short",
        "Grid relay open",
        "Grid relay short",
        "AC Relay Open Circuit",
        "AC Relay Short Circuit",
        "System temperature high",
        "System temperature low",
    ],
    2: [
        "AC overvoltage",
        "AC undervoltage",
        "AC overfrequency",
        "AC underfrequency",
        "AC reverse phase",
        "Auxiliary Power Supply Failure",
        "VDC Sampling Abnormal",
        "Pre-charge Abnormal",
        "Abnormal off-grid voltage",
        "Abnormal off-grid frequency",
        "AC output overload",
        "AC Output Overload Timeout",
        "AC phase lock failure",
        "AC soft start failure",
        "HW-OCPOVP Fault 1",
        "HW-OCPOVP Fault 2",
    ],
    3: [
        # Mixes device_low_power_fault3_* and micro_inv_fault3_* strings per APK
        "PV1 Over Voltage",  # device_low_power_fault3_01
        "PV2 Over Voltage",  # device_low_power_fault3_02
        "PV3 Over Voltage",  # device_low_power_fault3_03
        "PV4 Over Voltage",  # micro_inv_fault3_04
        "PV1 Overcurrent",  # device_low_power_fault3_04
        "PV2 Overcurrent",  # device_low_power_fault3_05
        "PV3 Overcurrent",  # device_low_power_fault3_06
        "PV4 Overcurrent",  # micro_inv_fault3_08
        "PV1 Over Temperature",  # device_low_power_fault3_07
        "PV2 Over Temperature",  # device_low_power_fault3_08
        "PV3 Over Temperature",  # device_low_power_fault3_09
        "PV4 Over Temperature",  # micro_inv_fault3_12
        "Current Sensor 1 Failure",  # micro_inv_fault3_13
        "Current Sensor 2 Failure",  # micro_inv_fault3_14
    ],
    4: [
        "Abnormal sampling zero reading",
        "Abnormal calibration parameter reading",
        "Wrong DSP software version",
        "Parameter Initialization Failed.",  # typo: trailing period in APK strings.xml
        "Parameter setting conflict",
        "Module number overrun",
        "Module number conflict",
        None,  # bit 7: unused (0 in APK)
        "RS485 Communication Monitoring Failure",
        "CAN Communication Monitoring Failure",
        "Parallel System CAN Communication Failure",
        "Internal SPI Communication Failure",
        "Utility frequency synchronization failure",  # typo: lowercase in APK strings.xml
        "Carrier wave synchronization failure",  # typo: lowercase in APK strings.xml
        "Module Fan Malfunction",
    ],
    5: [
        "DC Output Sampling Abnormal",  # micro_inv_fault5_01
        None,  # bit 1: unused (0 in APK)
        None,  # bit 2: unused (0 in APK)
        "DSP communication failure",  # typo: lowercase in APK strings.xml
        "External FLASH error",  # typo: lowercase in APK strings.xml
        "BMS Communication Failure",
        "Inverter String Communication Failure",
        "RTC Error",
        "EEPROM Error",
        "BMS System Fault",
        "DC Output Sampling Abnormal",  # bits 10–15: APK maps _11 through _16 to same EN string
        "DC Output Sampling Abnormal",
        "DC Output Sampling Abnormal",
        "DC Output Sampling Abnormal",
        "DC Output Sampling Abnormal",
        "DC Output Sampling Abnormal",
    ],
}


# ── High-voltage pack alarm/error (B500K, BH500E — devices with PACK_ALARM_PROFILE="high_volt") ─

PACK_HIGH_VOLT_ALARM_NAMES: dict[int, list[str | None]] = {
    1: [
        "Overall Overvoltage Alarm",
        "Charge temperature high",  # typo: lowercase in APK strings.xml
        "Single cell voltage high",  # typo: lowercase in APK strings.xml
        "Charge temperature low",  # typo: lowercase in APK strings.xml
        "Discharge temperature high",  # typo: lowercase in APK strings.xml
        "Overall Undervoltage Alarm",
        "Discharge temperature low",  # typo: lowercase in APK strings.xml
        "Single cell voltage low",  # typo: lowercase in APK strings.xml
        "Low Battery",
        "USB Output Alert",
    ],
}

PACK_HIGH_VOLT_ERROR_NAMES: dict[int, list[str | None]] = {
    1: [
        "Single Cell Dropout Voltage Error",
        "Cell Temperature Difference Fault",
        "Single Cell Failure",
        "Low Temperature",
        "Battery Pack Short Circuit",
        "Insulation Leakage",
        "Main Relay Adhesion",
        "Main Relay Open Circuit Failure",
        "Precharge Failed",
        "Power Off Failed",
        "FUSE Open Circuit",
        "Relay Driver Short Circuit",
        "HIVL Error",
        "BMU Communication Error",
        "Power Cable Disconnected",
        "Balance MOS Failure",
    ],
    2: [
        "Balance Failure",
        "BMU Supply Error",
        "Address Exception",
        "Parameter Initialization Failed.",  # typo: trailing period in APK strings.xml
        "MCU Communication Error",
        "High-voltage PCB Communication Error",
        "Breaker Error",
        "MCU Tripped",
        "Reverse Connection Error",
        "PCS Communication Error",
        "Busbar Voltage Calibration Error",
        "5V Detection Point Error",
        "Heater Failure",
        "Current Sampling Error",
        "Precharge Failure 2",
        "Master-slave Communication Failure",
    ],
    3: [
        "System-12V Abnormal",
        "Supercapacitor Fault",
        "AFE Abnormal Detected",
        "Multiple Resets of Computing Core",
        "BMU Addressing Failed",
        "No Input at AC Input Port",
        "No Output at AC Output Port",
        "Battery Controller Bus Bar Overtemperature",
        "Battery Pack Bus Bar Overtemperature",
        "Battery Controller Bus Bar Temperature Failure",
        "Self-Test Fault",
    ],
}


# ── BMU-level warnings (PACK_BMU_INFO, register 7200) ───────────────────────────────────────────
# Not currently decoded (PACK_BMU_INFO not in the standard poll); defined for completeness.

BMU_WARN_NAMES: dict[int, list[str | None]] = {
    1: [
        "Cell Sampling Disconnected",
        "Temperature Sampling Disconnected",
        "Balancing MOS Failure",
        "BMU 6V Power Supply Abnormal",
        "BMU 3.3V Power Supply Abnormal",
        "BMU-AFE Damaged",
        "Heater Control Circuit Failure - Switch Stuck",
        "Heater Control Circuit Failure - Switch Open Circuit",
        "Battery NTC Failure 1",
        "Battery NTC Failure 2",
        "Heating Film Failure",
        "Cell Failure",
        "Module Balancer Failure - AC Input Disconnected or Fuse Blown",
        "Module Balancer Failure - MOS Short Circuit",
        "Module Balancer Failure - Current Control Circuit Abnormal",
        "AFE Communication Abnormal",
        "Module Fuse Failure",
        "BMU Busbar Temperature Sensor Failure (Short Circuit/Open Circuit)",
        "AFE Power Supply Abnormal",
    ],
}
