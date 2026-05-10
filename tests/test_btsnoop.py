# ABOUTME: Test parse_btsnoop.py against synthetic btsnoop_hci.log captures.
# ABOUTME: Unit 14 per IMPLEMENTATION_UNITS.md.

import struct
import subprocess
import sys

BTSNOOP_MAGIC = b"btsnoop\x00"
HEADER_FMT = ">II"
RECORD_HEADER_FMT = ">IIIIQ"


def _build_synthetic_log(records: list[tuple[int, int, bytes]]) -> bytes:
    """Build a valid btsnoop_hci.log binary from (timestamp_us, direction, payload) records.

    direction: 0 = sent (HOST→CTLR), 1 = received (CTLR→HOST)
    payload: raw H4 ACL packet bytes (starting with 0x02)
    """
    buf = bytearray()
    # Header
    buf += BTSNOOP_MAGIC
    buf += struct.pack(HEADER_FMT, 1, 1002)
    # Records
    for ts_us, direction, payload in records:
        # H4 ACL packets: wrap with H4 header byte
        pkt = b"\x02" + payload
        flags = direction  # bit 0 = direction
        header = struct.pack(RECORD_HEADER_FMT, len(pkt), len(pkt), flags, 0, ts_us)
        buf += header
        buf += pkt
    return bytes(buf)


def _build_acl(payload: bytes) -> bytes:
    """Build an HCI ACL data packet wrapping L2CAP/ATT payload."""
    # ACL header: handle=0x0042, PB=0b10 (start), data_length
    handle = 0x0042
    pb_bc = 0x20  # PB = 0b10 (first/continuation fragment)
    acl_hdr = struct.pack("<HH", handle | pb_bc, len(payload))
    return acl_hdr + payload


def _build_l2cap_att(cid: int, att_pdu: bytes) -> bytes:
    """Build L2CAP basic frame with ATT data."""
    l2cap = struct.pack("<HH", len(att_pdu), cid) + att_pdu
    return l2cap


def test_parse_btsnoop_read_request(tmp_path):
    """Synthetic btsnoop log with a known Modbus read request → CSV has expected row."""
    # Build a Modbus read holding registers request: func=0x03, addr=0x000A, qty=0x006E
    modbus_req = bytes([0x01, 0x03, 0x00, 0x0A, 0x00, 0x6E])
    # Append dummy CRC (2 bytes)
    modbus_req += b"\x00\x00"

    att_req = bytes([0x52, 0x02, 0xFF]) + modbus_req  # Write Command to handle 0xFF02
    l2cap = _build_l2cap_att(0x0004, att_req)
    acl = _build_acl(l2cap)

    log_path = tmp_path / "test.log"
    log_data = _build_synthetic_log([(1000000, 0, acl)])
    log_path.write_bytes(log_data)

    result = subprocess.run(
        [sys.executable, "scripts/parse_btsnoop.py", str(log_path)],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().split("\n")
    assert len(lines) >= 2  # header + data
    assert "0x03" in lines[1]
    assert ",10," in lines[1]  # register 10 (0x000A)


def test_parse_btsnoop_notify_response(tmp_path):
    """Synthetic btsnoop log with a Modbus read response notify."""
    # Build a Modbus read response: func=0x03, byte_count=4, data=[0x12, 0x34, 0x56, 0x78]
    modbus_resp = bytes([0x01, 0x03, 0x04, 0x12, 0x34, 0x56, 0x78])
    modbus_resp += b"\x00\x00"  # dummy CRC

    att_notify = bytes([0x1B, 0x01, 0xFF]) + modbus_resp  # Handle Value Notification from 0xFF01
    l2cap = _build_l2cap_att(0x0004, att_notify)
    acl = _build_acl(l2cap)

    log_path = tmp_path / "test2.log"
    log_data = _build_synthetic_log([(2000000, 1, acl)])  # direction=1=received
    log_path.write_bytes(log_data)

    result = subprocess.run(
        [sys.executable, "scripts/parse_btsnoop.py", str(log_path)],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().split("\n")
    assert len(lines) >= 2
    assert "rx" in lines[1]
    assert "0x03" in lines[1]
    assert "12345678" in lines[1] or "1234" in lines[1]  # value hex


def test_parse_btsnoop_write_single(tmp_path):
    """Synthetic btsnoop log with a Modbus write single register."""
    # Write Single Register: func=0x06, addr=0x07DB (2011), value=0x0001
    modbus_write = bytes([0x01, 0x06, 0x07, 0xDB, 0x00, 0x01])
    modbus_write += b"\x00\x00"  # dummy CRC

    att_write = bytes([0x52, 0x02, 0xFF]) + modbus_write
    l2cap = _build_l2cap_att(0x0004, att_write)
    acl = _build_acl(l2cap)

    log_path = tmp_path / "test3.log"
    log_data = _build_synthetic_log([(3000000, 0, acl)])
    log_path.write_bytes(log_data)

    result = subprocess.run(
        [sys.executable, "scripts/parse_btsnoop.py", str(log_path)],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().split("\n")
    assert len(lines) >= 2
    assert "0x06" in lines[1]
    assert ",2011," in lines[1]


def test_parse_btsnoop_no_matches(tmp_path):
    """Log with no Bluetti ATT frames → header only."""
    # Build an ACL packet not destined for 0xFF01/0xFF02
    att_other = bytes([0x1B, 0x99, 0x00]) + b"\x01\x02\x03\x04\x00\x00"
    l2cap = _build_l2cap_att(0x0004, att_other)
    acl = _build_acl(l2cap)

    log_path = tmp_path / "test_empty.log"
    log_data = _build_synthetic_log([(1000000, 1, acl)])
    log_path.write_bytes(log_data)

    result = subprocess.run(
        [sys.executable, "scripts/parse_btsnoop.py", str(log_path)],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 1  # header only
