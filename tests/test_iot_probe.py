# ABOUTME: Hardware probe of IoT registers (11000, 12161) on EL100V2.
# ABOUTME: Run with: uv run pytest tests/test_iot_probe.py -s

import pytest

from voltkeeper.bluetooth import lookup_scan_result
from voltkeeper.bluetooth.client import BluetoothClient
from voltkeeper.core.commands import ReadHoldingRegisters

pytestmark = pytest.mark.skip(reason="requires hardware")

DEVICE_ADDRESS = "DC:B4:D9:46:73:96"
IOT_BASE_INFO = 11000
IOT_ENABLE_INFO = 12161


# ── APK-matching parsing helpers ────────────────────────────────────────────────


def _ascii_swapped(data: bytes, offset: int, length: int) -> str:
    """getASCIIStr(data, isSwap=true): swap byte pairs, skip nulls."""
    chars = []
    for i in range(0, length, 2):
        if offset + i + 1 >= len(data):
            break
        hi = data[offset + i + 1]
        lo = data[offset + i]
        if hi:
            chars.append(chr(hi))
        if lo:
            chars.append(chr(lo))
    return "".join(chars).rstrip("\x00")


def _ascii_raw(data: bytes, offset: int, length: int) -> str:
    """getASCIIStr(data, isSwap=false): sequential bytes, skip nulls."""
    chars = []
    for i in range(length):
        if offset + i >= len(data):
            break
        b = data[offset + i]
        if b:
            chars.append(chr(b))
    return "".join(chars).rstrip("\x00")


def _device_sn(data: bytes, offset: int, length: int) -> str:
    """getDeviceSN: iterate backwards in pairs, parse as hex number."""
    hex_str = ""
    end = offset + length
    for i in range(end - 1, offset - 1, -2):
        hex_str += f"{data[i - 1]:02X}{data[i]:02X}"
    return str(int(hex_str, 16)) if hex_str else ""


def _bit32(data: bytes, offset: int) -> int:
    """bit32RegByteToNumber(unsigned): swap register halves, parse u32."""
    a, b, c, d = data[offset], data[offset + 1], data[offset + 2], data[offset + 3]
    hex_str = f"{c:02X}{d:02X}{a:02X}{b:02X}"
    return int(hex_str, 16)


def _ip(data: bytes, offset: int) -> str:
    """parseDeviceIp: swap within pairs: bytes[1].bytes[0].bytes[3].bytes[2]."""
    return f"{data[offset + 1]}.{data[offset]}.{data[offset + 3]}.{data[offset + 2]}"


def _mac(data: bytes, offset: int) -> str:
    """parseDeviceMac: swap within pairs."""
    return (
        f"{data[offset + 1]:02X}:{data[offset]:02X}:"
        f"{data[offset + 3]:02X}:{data[offset + 2]:02X}:"
        f"{data[offset + 5]:02X}:{data[offset + 4]:02X}"
    )


def _status_bits(data: bytes, offset: int) -> int:
    """Parse 16-bit status word (2 bytes = 1 register) as integer bitmask."""
    return (data[offset] << 8) | data[offset + 1]


def _signed_rssi(data: bytes, offset: int) -> int:
    """APK: parseShort('FF' + bytes[53])."""
    b = data[offset]
    return b - 256 if b > 127 else b


# ── Field description tables ───────────────────────────────────────────────────

CONN_MODE = {0: "none", 1: "WiFi", 2: "Ethernet", 3: "4G"}
BIT_LABELS = [
    ("wifiSTA", 0),
    ("wifiAP", 1),
    ("bleStatus", 2),
    ("bleMesh", 3),
    ("net4G", 4),
    ("gps", 5),
    ("mqtt", 6),
    ("wifiMesh", 7),
]


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_iot_base_info():
    """Probe IOT_BASE_INFO (11000) with APK-matching parsing."""
    print(f"\nScanning for {DEVICE_ADDRESS} ...")
    sr = await lookup_scan_result(DEVICE_ADDRESS)
    print(f"  Found: {sr.display()}")

    client = BluetoothClient(DEVICE_ADDRESS, encrypted=sr.encrypted or False)
    try:
        await client.connect()
        print(f"  Connected (encrypted={sr.encrypted})")

        cmd = ReadHoldingRegisters(IOT_BASE_INFO, 70)
        print(f"\nReading {cmd.quantity} registers from IOT_BASE_INFO ({IOT_BASE_INFO}) ...")
        raw = await client.execute(cmd)
        print(f"  Got {len(raw)} bytes\n")
        _print_iot_fields(raw)

    finally:
        await client.disconnect()
        print("\nDisconnected.")


@pytest.mark.asyncio
async def test_probe_iot_enable_info():
    """Probe IOT_ENABLE_INFO (12161) for enable/disable flags."""
    print(f"\nScanning for {DEVICE_ADDRESS} ...")
    sr = await lookup_scan_result(DEVICE_ADDRESS)
    print(f"  Found: {sr.display()}")

    client = BluetoothClient(DEVICE_ADDRESS, encrypted=sr.encrypted or False)
    try:
        await client.connect()
        print(f"  Connected (encrypted={sr.encrypted})")

        cmd = ReadHoldingRegisters(IOT_ENABLE_INFO, 4)
        print(f"\nReading {cmd.quantity} registers from IOT_ENABLE_INFO ({IOT_ENABLE_INFO}) ...")
        raw = await client.execute(cmd)
        print(f"  Got {len(raw)} bytes\n")
        _print_enable_fields(raw)

    finally:
        await client.disconnect()
        print("\nDisconnected.")


# ── Output helpers ─────────────────────────────────────────────────────────────


def _print_iot_fields(data: bytes):
    """Print all parsed fields from IOT_BASE_INFO response."""
    if len(data) < 70 * 2:
        print(f"  Response too short: {len(data)} bytes (expected {70 * 2})")
        return

    print("  ┌───────────────────────────────────────────────────┐")
    print("  │  IOT_BASE_INFO (11000)                             │")
    print("  ├───────────────────────────────────────────────────┤")

    model = _ascii_swapped(data, 0, 12)
    print(f"  │  iotModel          : {model:<30} │")

    sn = _device_sn(data, 12, 8)
    print(f"  │  iotSn             : {sn:<30} │")

    sw_ver = _bit32(data, 28)
    print(f"  │  iotSoftwareVer    : {sw_ver:<30} │")

    rf_ver = _bit32(data, 32)
    print(f"  │  rfVer             : {rf_ver:<30} │")

    # Connection status bits
    status_word = _status_bits(data, 36)
    print(f"  │  status word @36-37: 0x{status_word:04X}                        │")
    for label, bit in BIT_LABELS:
        val = (status_word >> bit) & 1
        print(f"  │    {label:<19}: {val:<30} │")

    wifi_ip = _ip(data, 40)
    print(f"  │  wifiIp            : {wifi_ip:<30} │")

    wifi_gw = _ip(data, 44)
    print(f"  │  wifiGateway       : {wifi_gw:<30} │")

    wifi_mask = _ip(data, 48)
    print(f"  │  wifiMask          : {wifi_mask:<30} │")

    rssi = _signed_rssi(data, 53)
    print(f"  │  networkRssi       : {rssi} dBm                             │")

    wifi_mac = _mac(data, 54)
    print(f"  │  wifiMac           : {wifi_mac:<30} │")

    ble_mac = _mac(data, 60)
    print(f"  │  bleMac            : {ble_mac:<30} │")

    if len(data) > 69:
        mode = data[69]
        label = CONN_MODE.get(mode, f"unknown({mode})")
        print(f"  │  networkConnMode   : {mode} ({label})                      │")

    if len(data) >= 90:
        ip4g = _ip(data, 82) if len(data) > 85 else "n/a"
        ip_eth = _ip(data, 86) if len(data) > 89 else "n/a"
        print(f"  │  ip4g              : {ip4g:<30} │")
        print(f"  │  ipEthernet        : {ip_eth:<30} │")

    if len(data) > 94:
        sim = data[94] & 1
        print(f"  │  simOnline         : {bool(sim)}                                     │")

    print("  └───────────────────────────────────────────────────┘")


def _print_enable_fields(data: bytes):
    """Parse IOT_ENABLE_INFO (12161) — 4-byte enable bitfield."""
    if len(data) < 8:
        print(f"  Response too short: {len(data)} bytes (expected 8)")
        return

    word0 = _status_bits(data, 0)
    word1 = _status_bits(data, 2)

    print("  ┌───────────────────────────────────────────────────┐")
    print("  │  IOT_ENABLE_INFO (12161)                           │")
    print("  ├───────────────────────────────────────────────────┤")
    print(f"  │  word0 (bytes 0-1) : 0x{word0:04X}                       │")
    print(f"  │  word1 (bytes 2-3) : 0x{word1:04X}                       │")

    # APK: hexStrToEnableList(hex, step=2) — chunk bits into pairs, reverse each pair
    def _paired(bits: int) -> list[int]:
        vals = []
        for pair_start in range(0, 16, 2):
            lo = (bits >> pair_start) & 1
            hi = (bits >> (pair_start + 1)) & 1
            vals.append((hi << 1) | lo)
        return vals

    en1 = _paired(word0)
    en2 = _paired(word1)

    print(f"  │  wifiSTA           : {en1[0]}  (0=off, 1=on, 2=auto, 3=reserved)    │")
    print(f"  │  enable4G          : {en1[6]}                                        │")
    print(f"  │  ethernetEnable    : {en2[0]}                                        │")
    print(f"  │  wifiMeshEnable    : {en2[1]}                                        │")
    print(f"  │  defaultMode       : {en2[3]}                                        │")
    print(f"  │  bleMatchMode      : {en2[5]}                                        │")
    print("  └───────────────────────────────────────────────────┘")
