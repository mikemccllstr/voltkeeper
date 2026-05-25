# ABOUTME: TLV (Type-Length-Value) response parser for NODE_INFO — multi-sub-device topology.
# ABOUTME: Introduced in APK v3.0.9 for V2 protocol devices with parallel inverters or multiple battery packs.

from __future__ import annotations

from typing import NamedTuple

from ..bluetooth.exc import ParseError

TLV_MAGIC = bytes([0x40, 0x00, 0x04])


class TlvItem(NamedTuple):
    slave_addr: int
    reg_addr: int
    length: int
    value: bytes


class TlvParser:
    @staticmethod
    def parse(data: bytes) -> list[TlvItem]:
        if not data.startswith(TLV_MAGIC):
            return []

        items: list[TlvItem] = []
        pos = len(TLV_MAGIC)

        while pos + 6 <= len(data):
            slave_addr = data[pos]
            reg_addr_hi = data[pos + 1]
            reg_addr_lo = data[pos + 2]
            reg_addr = (reg_addr_hi << 8) | reg_addr_lo
            length_hi = data[pos + 3]
            length_lo = data[pos + 4]
            length = (length_hi << 8) | length_lo
            pos += 5

            if pos + length + 2 > len(data):
                raise ParseError(
                    f"TLV item at offset {pos - 5}: declared length {length} "
                    f"exceeds remaining data ({len(data) - pos} bytes)"
                )

            value = data[pos : pos + length]
            pos += length + 2  # skip CRC16

            items.append(TlvItem(slave_addr=slave_addr, reg_addr=reg_addr, length=length, value=value))

        return items
