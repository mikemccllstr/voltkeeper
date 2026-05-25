# ABOUTME: Tests for TLV protocol parser — magic byte detection, item parsing, error handling.

import pytest

from voltkeeper.bluetooth.exc import ParseError
from voltkeeper.core.tlv import TLV_MAGIC, TlvItem, TlvParser


def _build_tlv_item(slave_addr: int, reg_addr: int, value: bytes) -> bytes:
    length = len(value)
    header = bytes([slave_addr, (reg_addr >> 8) & 0xFF, reg_addr & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    crc = bytes([0x00, 0x00])
    return header + value + crc


def test_parses_single_tlv_item():
    item_data = _build_tlv_item(41, 6000, b"\x01\x02\x03\x04")
    data = TLV_MAGIC + item_data

    items = TlvParser.parse(data)
    assert len(items) == 1
    assert items[0] == TlvItem(slave_addr=41, reg_addr=6000, length=4, value=b"\x01\x02\x03\x04")


def test_parses_multiple_items():
    item1 = _build_tlv_item(41, 6000, b"\xaa\xbb")
    item2 = _build_tlv_item(42, 6100, b"\x11\x22\x33")
    data = TLV_MAGIC + item1 + item2

    items = TlvParser.parse(data)
    assert len(items) == 2
    assert items[0].slave_addr == 41
    assert items[0].reg_addr == 6000
    assert items[1].slave_addr == 42
    assert items[1].reg_addr == 6100


def test_raises_on_truncated_tlv():
    item_data = _build_tlv_item(41, 6000, b"\xaa\xbb\xcc\xdd")
    data = TLV_MAGIC + item_data[:7]  # truncated

    with pytest.raises(ParseError, match="declared length"):
        TlvParser.parse(data)


def test_non_tlv_response_returns_empty():
    data = b"\x00\x00\x00\x00\x01\x02\x03"
    items = TlvParser.parse(data)
    assert items == []


def test_empty_data_returns_empty():
    assert TlvParser.parse(b"") == []


def test_only_magic_bytes_returns_empty():
    assert TlvParser.parse(TLV_MAGIC) == []
