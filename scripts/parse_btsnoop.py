#!/usr/bin/env python3
"""Parse Android btsnoop_hci.log and extract Bluetti BLE Modbus frames.

Usage:
    python scripts/parse_btsnoop.py <btsnoop_hci.log> [--key HEX] [--iv HEX]

Outputs CSV to stdout: timestamp, direction, function_code, register, length, value_hex

Requires only stdlib + ``cryptography`` (already a project dependency).
"""
from __future__ import annotations

import argparse
import struct
import sys
from typing import Iterator


BTSNOOP_MAGIC = b"btsnoop\x00"
HEADER_FMT = ">II"
RECORD_HEADER_FMT = ">IIIIQ"

# GATT handles used by Bluetti
NOTIFY_HANDLE = 0xFF01
WRITE_HANDLE = 0xFF02

# ATT opcodes
ATT_WRITE_REQUEST = 0x12
ATT_WRITE_COMMAND = 0x52
ATT_HANDLE_VALUE_NOTIFICATION = 0x1B

# H4 types
H4_ACL = 0x02

# L2CAP channel ID for ATT
L2CAP_ATT_CID = 0x0004


# ── Btsnoop reader ────────────────────────────────────────────────────


def _read_records(path: str) -> Iterator[tuple[int, int, bytes]]:
    """Yield (timestamp_us, direction, payload) for each H4 ACL record."""
    with open(path, "rb") as f:
        magic = f.read(8)
        if magic != BTSNOOP_MAGIC:
            sys.exit(f"Not a btsnoop file (magic={magic!r})")

        version, datalink = struct.unpack(HEADER_FMT, f.read(8))
        if datalink != 1002:
            sys.exit(f"Unsupported datalink type {datalink} (expected 1002 H4)")

        while True:
            header = f.read(struct.calcsize(RECORD_HEADER_FMT))
            if not header:
                break
            if len(header) < struct.calcsize(RECORD_HEADER_FMT):
                break

            orig_len, incl_len, flags, drops, ts_us = struct.unpack(RECORD_HEADER_FMT, header)
            direction = flags & 1  # 0=Sent, 1=Received
            data = f.read(incl_len)

            if not data:
                continue

            # Only process H4 ACL data (type 0x02)
            if data[0] != H4_ACL:
                continue

            yield ts_us, direction, data


# ── ATT frame extraction ──────────────────────────────────────────────


def _extract_att(packet: bytes) -> tuple[int, int, bytes] | None:
    """Extract (opcode, handle, value) from an H4 ACL BLE packet.

    Returns None if the packet is not an ATT write/notify on the
    Bluetti GATT handles.
    """
    # Skip H4 header byte (already checked by caller)
    # ACL header: 2 bytes handle (LE), 2 bytes data length (LE)
    if len(packet) < 5:
        return None

    acl_len = packet[3] | (packet[4] << 8)
    l2cap_start = 5
    if len(packet) < l2cap_start + acl_len:
        return None

    l2cap = packet[l2cap_start : l2cap_start + acl_len]
    if len(l2cap) < 4:
        return None

    # L2CAP header: 2 bytes length, 2 bytes channel ID
    l2cap_len = l2cap[0] | (l2cap[1] << 8)
    l2cap_cid = l2cap[2] | (l2cap[3] << 8)

    if l2cap_cid != L2CAP_ATT_CID:
        return None

    att = l2cap[4 : 4 + l2cap_len]
    if len(att) < 3:
        return None

    opcode = att[0]
    handle = att[1] | (att[2] << 8)
    value = att[3:]

    if opcode in (ATT_WRITE_REQUEST, ATT_WRITE_COMMAND) and handle == WRITE_HANDLE:
        return opcode, handle, value
    if opcode == ATT_HANDLE_VALUE_NOTIFICATION and handle == NOTIFY_HANDLE:
        return opcode, handle, value
    return None


# ── Modbus frame parsing ──────────────────────────────────────────────


def _parse_modbus(data: bytes, *, is_request: bool) -> tuple[int, int, int, bytes] | None:
    """Parse a Modbus RTU frame.

    *is_request* distinguishes request frames (always 4-byte payload:
    addr + quantity/value) from response frames (variable byte_count).
    """
    if len(data) < 3:
        return None

    if data[0] != 0x01:
        return None

    func = data[1]

    if func == 0x03:  # Read Holding Registers
        if is_request:
            if len(data) < 8:
                return None
            addr = (data[2] << 8) | data[3]
            qty = (data[4] << 8) | data[5]
            return func, addr, qty, b""
        else:
            if len(data) < 5:
                return None
            byte_count = data[2]
            if len(data) < 3 + byte_count:
                byte_count = len(data) - 3
            value = data[3 : 3 + byte_count]
            return func, 0, byte_count, value

    elif func == 0x06:  # Write Single Register
        if len(data) < 8:
            return None
        addr = (data[2] << 8) | data[3]
        value = (data[4] << 8) | data[5]
        return func, addr, 2, bytes([data[4], data[5]])

    elif func == 0x10:  # Write Multiple Registers
        if len(data) < 9:
            return None
        addr = (data[2] << 8) | data[3]
        qty = (data[4] << 8) | data[5]
        byte_count = data[6]
        if len(data) < 7 + byte_count:
            byte_count = len(data) - 7
        value = data[7 : 7 + byte_count]
        return func, addr, qty, value

    return None


# ── Encryption support ────────────────────────────────────────────────


def _make_decryptor(key_hex: str | None, iv_hex: str | None):
    """Return a callable that decrypts bytes, or None if no key given."""
    if not key_hex:
        return None

    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex) if iv_hex else b"\x00" * 16
    if len(key) != 16:
        sys.exit("AES key must be 16 bytes (32 hex chars)")
    if len(iv) != 16:
        sys.exit("IV must be 16 bytes (32 hex chars)")

    cipher = Cipher(algorithms.AES128(key), modes.CBC(iv))

    def decrypt(data: bytes) -> bytes:
        # Zero-pad to block size, decrypt, return full plaintext
        pad_len = (16 - len(data) % 16) % 16
        padded = data + b"\x00" * pad_len
        dec = cipher.decryptor()
        return dec.update(padded) + dec.finalize()

    return decrypt


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Android btsnoop_hci.log for Bluetti BLE Modbus frames"
    )
    parser.add_argument("log", help="Path to btsnoop_hci.log")
    parser.add_argument("--key", help="AES-128 key (32 hex chars) for encrypted captures")
    parser.add_argument("--iv", help="Initial IV (32 hex chars), defaults to all-zero")
    args = parser.parse_args()

    decrypt = _make_decryptor(args.key, args.iv)

    print("timestamp,direction,function_code,register,length,value_hex")

    for ts_us, direction, packet in _read_records(args.log):
        att = _extract_att(packet)
        if att is None:
            continue

        opcode, handle, payload = att

        if decrypt:
            payload = decrypt(payload)

        is_request = opcode in (ATT_WRITE_REQUEST, ATT_WRITE_COMMAND)
        parsed = _parse_modbus(payload, is_request=is_request)
        if parsed is None:
            continue

        func, addr, qty, raw = parsed
        if isinstance(raw, bytes):
            val_hex = raw.hex() if raw else ""
            reg_len = len(raw) if raw else 0
        else:
            val_hex = f"{raw:04X}"
            reg_len = 2

        dir_label = "tx" if direction == 0 else "rx"
        print(f"{ts_us},{dir_label},0x{func:02X},{addr},{reg_len},{val_hex}")


if __name__ == "__main__":
    main()
