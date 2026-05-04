# ABOUTME: CLI tool for Bluetti power stations — scan, connect, and read data over BLE.
# ABOUTME: Uses plain Modbus RTU over BLE (no encryption; AC2A is not ESP32Encrypted).
# ABOUTME: Built with click for proper CLI affordances (help, version, subcommands).
#!/usr/bin/env python3
"""
CLI tool for Bluetti power stations over BLE.

Scan for nearby devices, connect, and read battery SOC and pack data.
"""

import asyncio
import struct
import sys

import click
from bleak import BleakClient, BleakScanner

# ── BLE GATT Identifiers ────────────────────────────────────────────────
SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"


# ═══════════════════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════════════════


def crc16_modbus(data: bytes) -> bytes:
    """CRC-16-Modbus (poly 0xA001, init 0xFFFF).

    Returns 2 bytes in little-endian order (low, high).
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b & 0xFF
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def _u16(data: bytes, offset: int) -> int:
    """Read unsigned 16-bit big-endian from byte buffer."""
    return (data[offset] << 8) | data[offset + 1]


def _s16(data: bytes, offset: int) -> int:
    """Read signed 16-bit big-endian from byte buffer."""
    val = _u16(data, offset)
    return val - 65536 if val >= 32768 else val


def _u32(data: bytes, offset: int) -> int:
    """Read unsigned 32-bit from two Modbus registers (low reg first, big-endian per reg)."""
    lo = _u16(data, offset)
    hi = _u16(data, offset + 2)
    return (hi << 16) | lo


def _s32(data: bytes, offset: int) -> int:
    """Read signed 32-bit from two Modbus registers (low reg first)."""
    val = _u32(data, offset)
    return val - 4294967296 if val >= 2147483648 else val


def _ascii(data: bytes, offset: int, length: int, byte_swap: bool = False) -> str:
    """Read ASCII string from byte buffer.

    When byte_swap=True, each 2-byte pair is reversed before decoding
    (the Modbus device stores ASCII with byte-swapped pairs).
    """
    if byte_swap and length >= 2:
        chars = []
        for i in range(0, length - 1, 2):
            chars.append(data[offset + i + 1])
            chars.append(data[offset + i])
        if length % 2:
            chars.append(data[offset + length - 1])
        raw = bytes(chars)
    else:
        raw = data[offset : offset + length]
    return raw.decode("ascii", errors="replace").rstrip("\x00").strip()


def _bcd_sn(data: bytes, offset: int, length: int) -> str:
    """Read BCD-encoded serial number from byte buffer (byte-swapped pairs).

    The Java code parses device SN by reading each byte pair in reverse order.
    """
    chars = []
    for i in range(0, length, 2):
        if offset + i + 1 < len(data):
            chars.append(f"{data[offset + i + 1]:02X}{data[offset + i]:02X}")
    return "".join(chars).lstrip("0")


def _format_version(fm_ver: int) -> str:
    """Format a firmware version integer for display.

    Mirrors DeviceConnUtilKt.deviceFmVerFormat().
    """
    s = str(fm_ver)
    if len(s) > 6:
        return f"v{s[:5]}.{s[5:7]}.{s[7:]}"
    elif len(s) > 4:
        return f"v{s[:4]}.{s[4:]}"
    return f"v{s}"


# ═══════════════════════════════════════════════════════════════════════
#  BLE Connection & Protocol
# ═══════════════════════════════════════════════════════════════════════


class BluettiAC2A:
    def __init__(self, address: str):
        self.address = address
        self.client = None  # BleakClient
        self._notifications = asyncio.Queue()

    def _on_notification(self, _sender, data: bytes):
        self._notifications.put_nowait(data)

    async def connect(self) -> None:
        click.echo(f"Connecting to {self.address} …")
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=15.0)
        click.echo("BLE connected.")

        await self.client.start_notify(NOTIFY_UUID, self._on_notification)
        click.echo("Session established.\n")

    async def read_home_data(self) -> dict:
        """Read home data (register 100, 6 registers) — baseline status."""
        return await self._read_modbus_register_parsed(100, 6, _parse_home_data)

    async def read_home_data_verbose(self) -> dict:
        """Read full home data (register 100, 62 registers) — all fields."""
        return await self._read_modbus_register_parsed(100, 62, _parse_home_data)

    async def read_inv_base_info(self) -> dict:
        """Read inverter base info (register 1100): model, SN, software, temps."""
        return await self._read_modbus_register_parsed(1100, 51, _parse_inv_base_info)

    async def read_inv_pv_info(self) -> dict:
        """Read PV/solar info (register 1200): production, per-string data."""
        return await self._read_modbus_register_parsed(1200, 70, _parse_inv_pv_info)

    async def read_inv_grid_info(self) -> dict:
        """Read grid info (register 1300): import/export, voltage, frequency."""
        return await self._read_modbus_register_parsed(1300, 31, _parse_inv_grid_info)

    async def read_inv_load_info(self) -> dict:
        """Read load info (register 1400): AC and DC loads, per-phase data."""
        return await self._read_modbus_register_parsed(1400, 48, _parse_inv_load_info)

    async def read_inv_inv_info(self) -> dict:
        """Read inverter output info (register 1500): output power, voltage, freq."""
        return await self._read_modbus_register_parsed(1500, 30, _parse_inv_inv_info)

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    async def _read_modbus_register(self, addr: int, count: int) -> bytes:
        """Send a plain Modbus RTU read request and return raw data payload."""
        frame = b"\x01\x03" + struct.pack(">H", addr) + struct.pack(">H", count)
        frame += crc16_modbus(frame)

        await self.client.write_gatt_char(WRITE_UUID, frame, response=False)

        resp = await asyncio.wait_for(self._notifications.get(), timeout=15.0)
        resp_bytes = bytes(resp)

        func = resp_bytes[1]
        if func & 0x80:
            raise RuntimeError(
                f"Modbus error: func=0x{func:02X} code=0x{resp_bytes[2]:02X}"
            )

        byte_count = resp_bytes[2]
        return resp_bytes[3 : 3 + byte_count]

    async def _read_modbus_register_parsed(self, addr: int, count: int, parser) -> dict:
        """Send Modbus read request and parse with given parser function."""
        data = await self._read_modbus_register(addr, count)
        return parser(data)


# ═══════════════════════════════════════════════════════════════════════
#  Protocol Parsers — mirror ProtocolParserV2 parse*() methods
# ═══════════════════════════════════════════════════════════════════════


def _parse_home_data(data: bytes) -> dict:
    """Parse V2 'APP_HOME_DATA' payload from register 100.

    Field layout mirrors ProtocolParserV2.parseHomeData().
    Parses all available fields; fields beyond the data length are omitted.
    """
    if len(data) < 12:
        return {}

    result: dict = {}

    # ── Base fields (always present up to byte 123) ──
    result["packTotalVoltage"] = _u16(data, 0) / 10.0
    result["packTotalCurrent"] = _u16(data, 2) / 10.0
    result["packTotalSoc"] = _u16(data, 4)
    result["packChargingStatus"] = _u16(data, 6)
    result["packChgFullTime"] = _u16(data, 8)
    result["packDsgEmptyTime"] = _u16(data, 10)

    if len(data) >= 16:
        result["packAgingInfo"] = _u16(data, 12)
        result["packCnts"] = data[14]
        result["packNumShow"] = data[15]  # offset 15, not 14 — packCnts is byte 14

    if len(data) >= 18:
        result["packOnline"] = _u16(data, 16)

    if len(data) >= 32:
        result["deviceModel"] = _ascii(data, 20, 12, byte_swap=True)

    if len(data) >= 40:
        result["deviceSN"] = _bcd_sn(data, 32, 8)

    if len(data) >= 42:
        result["invNumber"] = data[41]

    if len(data) >= 46:
        result["invPowerType"] = data[45]

    if len(data) >= 52:
        result["gridParallelSoC"] = data[51]

    # ── Power meters (32-bit) ──
    if len(data) >= 84:
        result["totalDCPower"] = _u32(data, 80)
    if len(data) >= 88:
        result["totalACPower"] = _s32(data, 84)
    if len(data) >= 92:
        result["totalPVPower"] = _u32(data, 88)
    if len(data) >= 96:
        result["totalGridPower"] = _s32(data, 92)
    if len(data) >= 100:
        result["totalInvPower"] = _s32(data, 96)

    # ── Energy totals (32-bit, /10.0) ──
    if len(data) >= 104:
        result["totalDCEnergy"] = _u32(data, 100) / 10.0
    if len(data) >= 108:
        result["totalACEnergy"] = _u32(data, 104) / 10.0
    if len(data) >= 112:
        result["totalPVChargingEnergy"] = _u32(data, 108) / 10.0
    if len(data) >= 116:
        result["totalGridChargingEnergy"] = _u32(data, 112) / 10.0
    if len(data) >= 120:
        result["totalFeedbackEnergy"] = _u32(data, 116) / 10.0

    # ── Status/mode fields ──
    if len(data) >= 122:
        result["chargingMode"] = data[121]
    if len(data) >= 124:
        result["invWorkingStatus"] = data[123]

    # ── Extended fields (size > 129) ──
    if len(data) >= 130:
        result["pvToAcEnergy"] = _u32(data, 124) / 10.0
        result["selfSufficiencyRate"] = data[129]

    # ── Further extended (size > 138) ──
    if len(data) >= 142:
        result["pvToAcPower"] = _u32(data, 130)
        result["packDsgEnergyTotal"] = _u32(data, 134) / 10.0
        result["rateVoltage"] = _u16(data, 138)
        result["rateFrequency"] = _u16(data, 140)

    return result


def _parse_inv_base_info(data: bytes) -> dict:
    """Parse V2 'INV_BASE_INFO' from register 1100.

    Field layout mirrors ProtocolParserV2.parseInvBaseInfo().
    """
    if len(data) < 26:
        return {}
    result: dict = {}
    result["invId"] = data[1]
    result["invType"] = _ascii(data, 2, 12, byte_swap=True)
    result["invSN"] = _bcd_sn(data, 14, 8)
    if len(data) >= 24:
        result["invPowerType"] = data[23]
    if len(data) >= 26:
        result["softwareNumber"] = data[25]

    # Software versions (6 slots × 6 bytes each, starting at byte 26)
    for i in range(6):
        off = 26 + i * 6
        if len(data) >= off + 6:
            mcu_type = data[off]
            version = (_u16(data, off + 2) << 16) | _u16(data, off + 4)
            if mcu_type > 0 and version > 0:
                key = f"software[{i}]"
                result[key] = f"MCU={mcu_type}  ver={_format_version(version)}"

    # Temperatures (offset varies by protocol version; we read generously)
    if len(data) >= 104:
        result["ambientTemp"] = data[102] - 40 if data[102] else None
    if len(data) >= 106:
        result["invMaxTemp"] = data[104] - 40 if data[104] else None
    if len(data) >= 108:
        result["pvDcdcMaxTemp"] = data[106] - 40 if data[106] else None

    # Rated currents (per phase)
    labels = [
        ("inputRateCurrentL1", 122),
        ("inputRateCurrentL2", 124),
        ("inputRateCurrentL3", 126),
        ("outputRateCurrentL1", 128),
        ("outputRateCurrentL2", 130),
        ("outputRateCurrentL3", 132),
        ("gridInputRateCurrentL1", 134),
        ("gridInputRateCurrentL2", 136),
        ("gridInputRateCurrentL3", 138),
    ]
    for name, off in labels:
        if len(data) >= off + 2:
            result[name] = _u16(data, off)

    return result


def _parse_inv_pv_info(data: bytes) -> dict:
    """Parse V2 'INV_PV_INFO' from register 1200.

    Field layout mirrors ProtocolParserV2.parseInvPVInfo().
    """
    if len(data) < 20:
        return {}
    result: dict = {}
    result["totalChgPower"] = _u32(data, 0)
    result["totalChgEnergy"] = _u32(data, 4) / 10.0
    if len(data) >= 20:
        result["acPvNumber"] = data[19] & 0x0F
        result["dcPvNumber"] = (data[19] >> 4) & 0x0F

    pv_count = max(result.get("acPvNumber", 0) + result.get("dcPvNumber", 0), 0)
    pv_count = min(pv_count, 5)

    for i in range(pv_count):
        off = 20 + i * 16
        if len(data) < off + 10:
            break
        prefix = f"pv[{i}]"
        result[f"{prefix}.workingStatus"] = data[off + 1]
        result[f"{prefix}.type"] = data[off + 3]
        result[f"{prefix}.inputPower"] = _u16(data, off + 4)
        result[f"{prefix}.inputVoltage"] = _u16(data, off + 6) / 10.0
        result[f"{prefix}.inputCurrent"] = _u16(data, off + 8) / 10.0

    return result


def _parse_inv_grid_info(data: bytes) -> dict:
    """Parse V2 'INV_GRID_INFO' from register 1300.

    Field layout mirrors ProtocolParserV2.parseInvGridInfo().
    """
    if len(data) < 14:
        return {}
    result: dict = {}
    result["frequency"] = _u16(data, 0) / 10.0
    result["totalChgPower"] = _s32(data, 2)
    result["totalChgEnergy"] = _u32(data, 6) / 10.0
    result["totalFeedbackEnergy"] = (
        (_u32(data, 10) << 32 | _u32(data, 14)) / 10.0 if len(data) >= 18 else 0
    )

    if len(data) >= 26:
        result["sysPhaseNumber"] = data[25]

    phases = min(result.get("sysPhaseNumber", 3), 3)
    for i in range(phases):
        off = 26 + i * 12
        if len(data) < off + 10:
            break
        prefix = f"gridPhase[{i}]"
        result[f"{prefix}.power"] = abs(_s16(data, off))
        result[f"{prefix}.voltage"] = _u16(data, off + 2) / 10.0
        result[f"{prefix}.current"] = abs(_s16(data, off + 4)) / 10.0

    return result


def _parse_inv_load_info(data: bytes) -> dict:
    """Parse V2 'INV_LOAD_INFO' from register 1400.

    Field layout mirrors ProtocolParserV2.parseInvLoadInfo().
    """
    if len(data) < 28:
        return {}
    result: dict = {}
    result["dcLoadTotalPower"] = _u32(data, 0)
    result["dcLoadTotalEnergy"] = _u32(data, 4) / 10.0
    result["dc5VPower"] = _u16(data, 8)
    result["dc5VCurrent"] = _u16(data, 10) / 10.0
    result["dc12VPower"] = _u16(data, 12)
    result["dc12VCurrent"] = _u16(data, 14) / 10.0
    result["dc24VPower"] = _u16(data, 16)
    result["dc24VCurrent"] = _u16(data, 18) / 10.0
    result["dcVoltTotal"] = _u16(data, 24) / 10.0
    result["dcCurrentTotal"] = _u16(data, 26) / 10.0

    if len(data) >= 48:
        result["acLoadTotalPower"] = _u32(data, 40)
        result["acLoadTotalEnergy"] = _u32(data, 44) / 10.0

    if len(data) >= 60:
        result["sysPhaseNumber"] = data[59]

    phases = min(result.get("sysPhaseNumber", 3), 3)
    for i in range(phases):
        off = 60 + i * 12
        if len(data) < off + 8:
            break
        prefix = f"acPhase[{i}]"
        result[f"{prefix}.power"] = _u16(data, off)
        result[f"{prefix}.voltage"] = _u16(data, off + 2) / 10.0
        result[f"{prefix}.current"] = _u16(data, off + 4) / 10.0

    return result


def _parse_inv_inv_info(data: bytes) -> dict:
    """Parse V2 'INV_INV_INFO' from register 1500.

    Field layout mirrors ProtocolParserV2.parseInvInvInfo().
    """
    if len(data) < 6:
        return {}
    result: dict = {}
    result["frequency"] = _u16(data, 0) / 10.0
    result["totalEnergy"] = _u32(data, 2) / 10.0

    if len(data) >= 18:
        result["sysPhaseNumber"] = data[17]

    phases = min(result.get("sysPhaseNumber", 3), 3)
    for i in range(phases):
        off = 18 + i * 12
        if len(data) < off + 8:
            break
        prefix = f"invPhase[{i}]"
        result[f"{prefix}.workStatus"] = data[off + 1]
        result[f"{prefix}.power"] = _u16(data, off + 2)
        result[f"{prefix}.voltage"] = _u16(data, off + 4) / 10.0
        result[f"{prefix}.current"] = _u16(data, off + 6) / 10.0

    return result


# ═══════════════════════════════════════════════════════════════════════
#  BLE Device Discovery
# ═══════════════════════════════════════════════════════════════════════


async def _scan_for_bluetti(timeout: float = 10.0) -> list[tuple[str, str]]:
    """Scan for Bluetti devices advertising the GATT service UUID.

    Returns a list of (address, name) tuples.
    """
    click.echo(f"Scanning for Bluetti devices (service {SERVICE_UUID}) …")
    devices = await BleakScanner.discover(
        timeout=timeout,
        service_uuids=[SERVICE_UUID],
        return_adv=True,
    )

    found: list[tuple[str, str]] = []
    for address, (device, adv) in devices.items():
        name = (device.name or adv.local_name or "").strip()
        if not name:
            name = "(unknown)"
        found.append((address, name))

    return sorted(found, key=lambda x: x[0])


async def _pick_address_after_scan() -> str:
    """Scan for devices and let the user pick one interactively.

    Returns the selected MAC address. Exits if none found.
    """
    devices = await _scan_for_bluetti()

    if not devices:
        click.secho("\nNo Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    if len(devices) == 1:
        address, name = devices[0]
        click.echo(f"\nFound 1 device → auto-selecting: {address} ({name})")
        return address

    click.echo(f"\nFound {len(devices)} Bluetti devices:\n")
    for i, (addr, name) in enumerate(devices, 1):
        click.echo(
            f"  [{click.style(str(i), fg='cyan')}] "
            f"{click.style(addr, fg='green')}  —  {name}"
        )

    click.echo()
    while True:
        try:
            choice = input(f"Select device (1-{len(devices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
        except (ValueError, EOFError, KeyboardInterrupt):
            click.echo()
            sys.exit(1)
        click.echo(f"Enter a number between 1 and {len(devices)}.")


# ═══════════════════════════════════════════════════════════════════════
#  Output Formatting
# ═══════════════════════════════════════════════════════════════════════


def _print_status(home: dict) -> None:
    """Print battery status in a formatted table."""
    sep = "─" * 44
    click.echo(sep)
    click.echo(f"  Battery SOC:       {home['packTotalSoc']:>5.0f} %")
    click.echo(f"  Pack Voltage:      {home['packTotalVoltage']:>5.1f} V")
    click.echo(f"  Pack Current:      {home['packTotalCurrent']:>5.1f} A")
    click.echo(f"  Charging Status:   {home['packChargingStatus']:>5.0f}")
    click.echo(f"  Time to Full:      {home['packChgFullTime']:>5.0f} min")
    click.echo(f"  Time to Empty:     {home['packDsgEmptyTime']:>5.0f} min")
    click.echo(sep)


def _print_verbose(
    home: dict, inv_base: dict, pv: dict, grid: dict, load: dict, inv_info: dict
) -> None:
    """Print all available device information in organized sections."""
    sep = "─" * 56
    click.echo(sep)
    click.echo(click.style("  BLUETTI DEVICE — FULL STATUS", bold=True))
    click.echo(sep)

    # ── Device Identity ──
    if home.get("deviceModel") or home.get("deviceSN"):
        click.echo(f"\n  Model:       {home.get('deviceModel', '?')}")
        click.echo(f"  Serial:      {home.get('deviceSN', '?')}")
    if inv_base.get("invType"):
        click.echo(f"  Inv Type:    {inv_base['invType']}")
    if inv_base.get("invSN"):
        click.echo(f"  Inv SN:      {inv_base['invSN']}")
    if home.get("invNumber", 0) > 0:
        click.echo(f"  Inverters:   {home['invNumber']}")
    if home.get("packCnts", 0) > 0:
        click.echo(f"  Packs:       {home['packCnts']}")

    # ── Battery ──
    click.echo(f"\n  {click.style('BATTERY', bold=True, fg='green')}")
    click.echo(f"    SOC:                  {home['packTotalSoc']:>5.0f} %")
    click.echo(f"    Voltage:              {home['packTotalVoltage']:>5.1f} V")
    click.echo(f"    Current:              {home['packTotalCurrent']:>5.1f} A")
    status_map = {0: "Idle", 1: "Charging", 2: "Discharging", 3: "Floating"}
    cs = home.get("packChargingStatus", 0)
    click.echo(f"    Status:               {status_map.get(cs, str(cs))} ({cs})")
    click.echo(f"    Time to Full:         {home.get('packChgFullTime', 0):>5.0f} min")
    click.echo(f"    Time to Empty:        {home.get('packDsgEmptyTime', 0):>5.0f} min")
    if "packDsgEnergyTotal" in home:
        click.echo(f"    Total Discharged:     {home['packDsgEnergyTotal']:>8.1f} Wh")

    # ── Power Meters ──
    if any(k in home for k in ("totalPVPower", "totalACPower", "totalDCPower")):
        click.echo(f"\n  {click.style('POWER (instantaneous)', bold=True, fg='cyan')}")
        if "totalPVPower" in home:
            click.echo(f"    PV Input:             {home['totalPVPower']:>5.0f} W")
        if "totalACPower" in home:
            ac = home["totalACPower"]
            click.echo(f"    AC:                   {ac:>+6.0f} W  (neg=export)")
        if "totalDCPower" in home:
            click.echo(f"    DC Load:              {home['totalDCPower']:>5.0f} W")
        if "totalGridPower" in home:
            click.echo(f"    Grid:                 {home['totalGridPower']:>+6.0f} W")
        if "pvToAcPower" in home:
            click.echo(f"    PV→AC:                {home['pvToAcPower']:>5.0f} W")

    # ── Energy Totals ──
    if any(k in home for k in ("totalPVChargingEnergy", "totalDCEnergy")):
        click.echo(f"\n  {click.style('ENERGY (lifetime)', bold=True, fg='yellow')}")
        if "totalPVChargingEnergy" in home:
            click.echo(
                f"    PV Charging:          {home['totalPVChargingEnergy']:>8.1f} Wh"
            )
        if "totalGridChargingEnergy" in home:
            click.echo(
                f"    Grid Charging:        {home['totalGridChargingEnergy']:>8.1f} Wh"
            )
        if "totalFeedbackEnergy" in home:
            click.echo(
                f"    Feed-back:            {home['totalFeedbackEnergy']:>8.1f} Wh"
            )
        if "totalDCEnergy" in home:
            click.echo(f"    DC Output:            {home['totalDCEnergy']:>8.1f} Wh")
        if "totalACEnergy" in home:
            click.echo(f"    AC Output:            {home['totalACEnergy']:>8.1f} Wh")
        if "pvToAcEnergy" in home:
            click.echo(f"    PV→AC:                {home['pvToAcEnergy']:>8.1f} Wh")

    # ── Temperatures ──
    if inv_base:
        temps = []
        for key, label in [
            ("ambientTemp", "Ambient"),
            ("invMaxTemp", "Inv.Max"),
            ("pvDcdcMaxTemp", "PV DCDC Max"),
        ]:
            val = inv_base.get(key)
            if val is not None:
                temps.append(f"{label}={val}°C")
        if temps:
            click.echo(f"\n  {click.style('TEMPERATURES', bold=True, fg='red')}")
            for t in temps:
                click.echo(f"    {t}")

    # ── Software Versions ──
    soft_keys = [k for k in inv_base if k.startswith("software[")]
    if soft_keys:
        click.echo(f"\n  {click.style('SOFTWARE VERSIONS', bold=True, fg='magenta')}")
        for k in sorted(soft_keys):
            click.echo(f"    {k}: {inv_base[k]}")

    # ── PV Details ──
    pv_keys = [
        k
        for k in pv
        if k.startswith("pv[") and k.endswith(".type") and pv.get(k, 0) != 0
    ]
    if pv_keys:
        click.echo(f"\n  {click.style('PV STRINGS', bold=True, fg='cyan')}")
        for pk in sorted(set(k.split(".")[0] for k in pv_keys)):
            pv_type = pv.get(f"{pk}.type", "?")
            pv_status = pv.get(f"{pk}.workingStatus", "?")
            pv_power = pv.get(f"{pk}.inputPower", 0)
            pv_volt = pv.get(f"{pk}.inputVoltage", 0)
            pv_curr = pv.get(f"{pk}.inputCurrent", 0)
            click.echo(
                f"    {pk}: Power={pv_power}W  V={pv_volt:.1f}V  "
                f"I={pv_curr:.1f}A  Status={pv_status}  Type={pv_type}"
            )

    # ── Grid ──
    if grid:
        click.echo(f"\n  {click.style('GRID', bold=True, fg='blue')}")
        if "frequency" in grid:
            click.echo(f"    Frequency:            {grid['frequency']:.1f} Hz")
        if "totalChgPower" in grid:
            click.echo(f"    Import Power:         {grid['totalChgPower']:>+6.0f} W")
        for i in range(3):
            pk = f"gridPhase[{i}]"
            if f"{pk}.voltage" in grid:
                click.echo(
                    f"    Phase {i + 1}:  V={grid[f'{pk}.voltage']:.1f}V  "
                    f"I={grid[f'{pk}.current']:.1f}A  P={grid[f'{pk}.power']}W"
                )

    # ── Load ──
    if load:
        click.echo(f"\n  {click.style('LOADS', bold=True, fg='blue')}")
        dc_parts = []
        for v in ("5V", "12V", "24V"):
            if f"dc{v}Power" in load:
                dc_parts.append(
                    f"DC{v}={load[f'dc{v}Power']}W/{load[f'dc{v}Current']:.1f}A"
                )
        if dc_parts:
            click.echo(f"    {'  '.join(dc_parts)}")
        if "dcLoadTotalPower" in load:
            click.echo(
                f"    DC Total:             {load['dcLoadTotalPower']}W  "
                f"({load.get('dcVoltTotal', 0):.1f}V / {load.get('dcCurrentTotal', 0):.1f}A)"
            )
        if "acLoadTotalPower" in load:
            click.echo(f"    AC Total:             {load['acLoadTotalPower']}W")
        for i in range(3):
            pk = f"acPhase[{i}]"
            if f"{pk}.voltage" in load:
                click.echo(
                    f"    Phase {i + 1}:  V={load[f'{pk}.voltage']:.1f}V  "
                    f"I={load[f'{pk}.current']:.1f}A  P={load[f'{pk}.power']}W"
                )

    # ── Inverter Output ──
    if inv_info:
        click.echo(f"\n  {click.style('INVERTER OUTPUT', bold=True, fg='yellow')}")
        if "frequency" in inv_info:
            click.echo(f"    Frequency:            {inv_info['frequency']:.1f} Hz")
        for i in range(3):
            pk = f"invPhase[{i}]"
            if f"{pk}.voltage" in inv_info:
                ws = inv_info.get(f"{pk}.workStatus", "?")
                click.echo(
                    f"    Phase {i + 1}:  V={inv_info[f'{pk}.voltage']:.1f}V  "
                    f"I={inv_info[f'{pk}.current']:.1f}A  "
                    f"P={inv_info[f'{pk}.power']}W  Status={ws}"
                )

    # ── Misc ──
    misc_parts = []
    if "chargingMode" in home:
        mode_map = {0: "Standard", 1: "Turbo", 2: "Silent"}
        misc_parts.append(
            f"Charge Mode={mode_map.get(home['chargingMode'], str(home['chargingMode']))}"
        )
    if home.get("invWorkingStatus", 0):
        misc_parts.append(f"Inv Status={home['invWorkingStatus']}")
    if home.get("packAgingInfo", 0):
        misc_parts.append(f"Pack Aging={home['packAgingInfo']}")
    if home.get("gridParallelSoC", 0):
        misc_parts.append(f"Grid Parallel SoC={home['gridParallelSoC']}%")
    if home.get("rateVoltage") or home.get("rateFrequency"):
        misc_parts.append(
            f"Rated={home.get('rateVoltage', '?')}V/{home.get('rateFrequency', '?')}Hz"
        )
    if "selfSufficiencyRate" in home:
        misc_parts.append(f"Self-Sufficiency={home['selfSufficiencyRate']}%")
    if "pvToAcEnergy" in home:
        misc_parts.append(f"PV→AC Energy={home['pvToAcEnergy']:.1f}Wh")
    if misc_parts:
        click.echo(f"\n  {click.style('MISC', bold=True)}")
        for p in misc_parts:
            click.echo(f"    {p}")

    # ── Rated Currents (inverter base info) ──
    current_fields = [k for k in inv_base if "RateCurrent" in k and inv_base.get(k, 0)]
    if current_fields:
        click.echo(f"\n  {click.style('RATED CURRENTS (A)', bold=True)}")
        for k in sorted(current_fields):
            click.echo(f"    {k}: {inv_base[k] / 10.0:.1f}A")

    click.echo(f"\n{sep}")


# ═══════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(
    version="0.1.0",
    prog_name="bluetti-cli",
    message="%(prog)s %(version)s",
)
@click.pass_context
def cli(ctx: click.Context):
    """Bluetti power station CLI — scan, connect, and read data over BLE.

    \b
    Examples:
      bluetti-cli status              # auto-scan and read battery data
      bluetti-cli status AA:BB:CC:DD:EE:FF  # connect directly
      bluetti-cli scan                # scan for nearby devices
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


@cli.command()
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds.",
)
def scan(timeout):
    """Scan for nearby Bluetti devices and display their MAC addresses."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        devices = loop.run_until_complete(_scan_for_bluetti(timeout=timeout))
    finally:
        loop.close()

    if not devices:
        click.secho("No Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    label = click.style(str(len(devices)), fg="cyan", bold=True)
    click.echo(f"\n{label} device(s) found:\n")
    for addr, name in devices:
        click.echo(f"  {click.style(addr, fg='green')}  —  {name}")

    click.echo()
    if len(devices) == 1:
        click.echo("To read data from this device:")
        click.echo(f"  {click.style(f'bluetti-cli status {devices[0][0]}', bold=True)}")
    else:
        click.echo("To read data from a specific device:")
        for addr, _ in devices:
            cmd = click.style(f"bluetti-cli status {addr}", bold=True)
            click.echo(f"  {cmd}")


@cli.command()
@click.argument("address", required=False, default=None)
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds (only used when ADDRESS is not provided).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Display all available device information (power meters, energy totals, "
    "PV strings, grid, loads, temperatures, software versions, etc.).",
)
def status(address, timeout, verbose):
    """Read battery SOC and pack data from a Bluetti device.

    If ADDRESS is not provided, scans for nearby Bluetti devices and
    lets you pick one interactively.
    """
    if not address:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            address = loop.run_until_complete(_pick_address_after_scan())
        finally:
            loop.close()
        cmd = click.style(f"bluetti-cli status {address}", bold=True)
        click.echo(f"\nTip: next time, run directly with:\n  {cmd}")
    else:
        address = address.upper()

    device = BluettiAC2A(address)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    home = None
    inv_base = {}
    pv = {}
    grid = {}
    load = {}
    inv_info = {}
    try:
        loop.run_until_complete(device.connect())

        if verbose:
            home = loop.run_until_complete(device.read_home_data_verbose())
            for label, coro_fn, target in [
                ("inverter info", device.read_inv_base_info, "inv_base"),
                ("PV info", device.read_inv_pv_info, "pv"),
                ("grid info", device.read_inv_grid_info, "grid"),
                ("load info", device.read_inv_load_info, "load"),
                ("inverter output", device.read_inv_inv_info, "inv_info"),
            ]:
                try:
                    result = loop.run_until_complete(coro_fn())
                    if target == "inv_base":
                        inv_base = result
                    elif target == "pv":
                        pv = result
                    elif target == "grid":
                        grid = result
                    elif target == "load":
                        load = result
                    elif target == "inv_info":
                        inv_info = result
                except Exception:
                    pass  # skip blocks the device doesn't support
        else:
            home = loop.run_until_complete(device.read_home_data())

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        click.secho(f"\nError: {exc}", fg="red")
        sys.exit(1)
    finally:
        loop.run_until_complete(device.disconnect())
        loop.close()
        click.echo("Disconnected.")

    if home is None:
        click.secho("No data received.", fg="red")
        sys.exit(1)

    if verbose:
        _print_verbose(home, inv_base, pv, grid, load, inv_info)
    else:
        _print_status(home)


if __name__ == "__main__":
    cli()
