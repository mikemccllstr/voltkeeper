# ABOUTME: Utility functions for CRC16-Modbus, integer parsing, ASCII/BCD decoding, version formatting.

import struct


def crc16_modbus(data: bytes) -> bytes:
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
    return (data[offset] << 8) | data[offset + 1]


def _s16(data: bytes, offset: int) -> int:
    val = _u16(data, offset)
    return val - 65536 if val >= 32768 else val


def _u32(data: bytes, offset: int) -> int:
    lo = _u16(data, offset)
    hi = _u16(data, offset + 2)
    return (hi << 16) | lo


def _s32(data: bytes, offset: int) -> int:
    val = _u32(data, offset)
    return val - 4294967296 if val >= 2147483648 else val


def _ascii(data: bytes, offset: int, length: int, byte_swap: bool = False) -> str:
    if byte_swap and length >= 2:
        chars = []
        for i in range(0, length - 1, 2):
            chars.append(data[offset + i + 1])
            chars.append(data[offset + i])
        if length % 2:
            chars.append(data[offset + length - 1])
        raw = bytes(chars)
    else:
        raw = data[offset: offset + length]
    return raw.decode("ascii", errors="replace").rstrip("\x00").strip()


def _bcd_sn(data: bytes, offset: int, length: int) -> str:
    chars = []
    for i in range(0, length, 2):
        if offset + i + 1 < len(data):
            chars.append(f"{data[offset + i + 1]:02X}{data[offset + i]:02X}")
    return "".join(chars).lstrip("0")


def _format_version(fm_ver: int) -> str:
    s = str(fm_ver)
    if len(s) > 6:
        return f"v{s[:5]}.{s[5:7]}.{s[7:]}"
    elif len(s) > 4:
        return f"v{s[:4]}.{s[4:]}"
    return f"v{s}"
