#!/usr/bin/env python3
"""
Connect to a Bluetti AC2A over BLE and read battery SOC.

Usage: python ble_read_battery.py <BLE_ADDRESS>
Example: python ble_read_battery.py AA:BB:CC:DD:EE:FF

Dependencies: bleak, cryptography
    pip install bleak cryptography
"""

import asyncio
import sys
import os
import hashlib
import struct
from bleak import BleakClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import (
    encode_dss_signature,
    decode_dss_signature,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_public_key,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ── BLE GATT Identifiers ────────────────────────────────────────────────
SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
WRITE_UUID   = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000ff01-0000-1000-8000-00805f9b34fb"
CCCD_UUID    = "00002902-0000-1000-8000-00805f9b34fb"  # descriptor for notify enable

# ── Hard-coded Cryptographic Material (identical across all installations) ─
LOCAL_AES_KEY = "459FC535808941F17091E0993EE3E93D"

# Private key L1 — used by the app to sign its ECDH public key
PRIVATE_KEY_L1_HEX = (
    "4F19A16E3E87BDD9BD24D3E5495B88041511943CBC8B969ADE9641D0F56AF337"
)
# Pre-computed public point for PRIVATE_KEY_L1 (Q = d * G on secp256r1)
PUB_KEY_L1_X = "3F29E1B8B29D8422BBB0E0F09000CF2EE2931DA13CDAC8129F8C09DEAC07F519"
PUB_KEY_L1_Y = "B5AC5509CA3F3F59B234B7777A231AE595CA5AA1745FD7A62BC4D02037117DD1"

# Public key K2 — used to verify the device's ECDH public key signature
PUBLIC_KEY_K2 = (
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
    "A73ABF5D2232C8C1C72E68304343C272495E3A8FD6F30EA96DE2F4B3CE60B251"
    "EE21AC667CF8A71E18B46B664EAEFFE3C489F24F695B6411DB7E22CCC85A8594"
)


# ═══════════════════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════════════════

def crc16_modbus(data: bytes) -> bytes:
    """CRC-16-Modbus (poly 0xA001, init 0xFFFF).
    Returns 2 bytes in little-endian order (low, high)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b & 0xFF
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def xor_hex(a: str, b: str) -> str:
    """Byte-wise XOR of two equal-length hex strings → uppercase hex."""
    return bytes(x ^ y for x, y in zip(bytes.fromhex(a), bytes.fromhex(b))).hex().upper()


def sum_hex(h: str) -> str:
    """Sum all bytes, return as 4-char uppercase hex (2 bytes)."""
    return f"{sum(bytes.fromhex(h)) & 0xFFFF:04X}"


def md5_hex(data: bytes) -> str:
    """MD5 digest → 32-char lowercase hex."""
    return hashlib.md5(data).hexdigest()


def aes_encrypt_block(plaintext: bytes, iv: bytes, key: bytes) -> bytes:
    """AES-CBC encrypt one 16-byte block.  Zero-pads short blocks to 16 B."""
    block = plaintext[:16].ljust(16, b"\x00")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    return enc.update(block) + enc.finalize()


def aes_decrypt_block(ciphertext: bytes, iv: bytes, key: bytes) -> bytes:
    """AES-CBC decrypt one 16-byte block."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    return dec.update(ciphertext) + dec.finalize()


def build_aes_cbc_cmd(plaintext_hex: str, aes_key_hex: str,
                      iv_bytes: bytes = None) -> str:
    """Encrypt a plaintext hex string for BLE transmission.

    Returns hex string with this wire format:
      <data_len_4hex>[<random_iv_8hex>]<ciphertext_blocks>

    *handshake*  (iv_bytes is set)  → omits the random‑iv field.
    *post‑handshake* (iv_bytes=None) → generates a 4‑B random IV,
      MD5‑hashes it to a 16‑B IV, and includes the 4‑B source in the
      output so the receiver can reconstruct the same IV.
    """
    key = bytes.fromhex(aes_key_hex)
    data_len = len(plaintext_hex) // 2                     # bytes, NOT hex chars
    num_blocks = (len(plaintext_hex) + 31) // 32            # 16 B = 32 hex chars

    if iv_bytes is not None:
        cur_iv = iv_bytes
        random_iv_hex = None
    else:
        rand4 = os.urandom(4)
        random_iv_hex = rand4.hex().upper()
        cur_iv = bytes.fromhex(md5_hex(rand4))

    ciphertext = ""
    for i in range(num_blocks):
        start = i * 32
        end = min(start + 32, len(plaintext_hex))
        block = bytes.fromhex(plaintext_hex[start:end])
        enc = aes_encrypt_block(block, cur_iv, key)
        ciphertext += enc.hex().upper()
        cur_iv = enc                                        # CBC: IV = prev ciphertext

    if iv_bytes is not None:
        return f"{data_len:04X}{ciphertext}"
    else:
        return f"{data_len:04X}{random_iv_hex}{ciphertext}"


def parse_aes_cbc_data(data_hex: str, aes_key_hex: str,
                       iv_bytes: bytes = None) -> str:
    """Decrypt a BLE notification.  Returns plaintext as continuous hex."""
    key = bytes.fromhex(aes_key_hex)
    data = data_hex.replace(" ", "")
    data_len = int(data[:4], 16)

    if iv_bytes is not None:
        cur_iv = iv_bytes
        ct_start = 4
    else:
        iv_source_hex = data[4:12]
        cur_iv = bytes.fromhex(md5_hex(bytes.fromhex(iv_source_hex)))
        ct_start = 12

    ciphertext = data[ct_start:]
    num_blocks = len(ciphertext) // 32

    plaintext = ""
    for i in range(num_blocks):
        block_hex = ciphertext[i * 32 : i * 32 + 32]
        block = bytes.fromhex(block_hex)
        dec = aes_decrypt_block(block, cur_iv, key)
        plaintext += dec.hex().upper()
        cur_iv = block                                     # CBC chaining

    return plaintext[:data_len * 2]                        # strip zero‑padding


# ── Crypto Key Objects (initialise once) ─────────────────────────────────

_public_key_k2 = load_der_public_key(bytes.fromhex(PUBLIC_KEY_K2))

_prk_l1_int = int(PRIVATE_KEY_L1_HEX, 16)
_private_key_l1 = ec.EllipticCurvePrivateNumbers(
    _prk_l1_int,
    ec.EllipticCurvePublicNumbers(
        int(PUB_KEY_L1_X, 16),
        int(PUB_KEY_L1_Y, 16),
        ec.SECP256R1(),
    ),
).private_key(default_backend())


# ═══════════════════════════════════════════════════════════════════════
#  BLE Connection & Protocol State Machine
# ═══════════════════════════════════════════════════════════════════════

class BluettiAC2A:
    def __init__(self, address: str):
        self.address = address
        self.client = None  # BleakClient

        # asyncio queue for notification bytes
        self._notifications = asyncio.Queue()

        # Crypto state
        self.ble_conn_aes_key = None    # 32 hex → AES-128
        self.ble_conn_share_key = None  # 64 hex → AES-256 (ECDH)
        self.random_md5 = None          # 32 hex (lowercase)
        self.ecdh_keypair = None        # ec.EllipticCurvePrivateKey

    # ── BLE callbacks ────────────────────────────────────────────────
    def _on_notification(self, _sender, data: bytes):
        self._notifications.put_nowait(data)

    # ── Public API ───────────────────────────────────────────────────
    async def connect(self) -> None:
        print(f"Connecting to {self.address} …")
        self.client = BleakClient(self.address)
        await self.client.connect(timeout=15.0)
        print("BLE connected.")

        await self.client.start_notify(NOTIFY_UUID, self._on_notification)
        await asyncio.sleep(0.5)          # emulate the app's 500 ms delay

        await self._handshake_challenge()
        await self._handshake_ecdh()

        print("Session established.\n")

    async def read_home_data(self) -> dict:
        """Read V2 home‑page data (register 100, 92 registers) and parse."""
        return await self._read_modbus_register(100, 92)

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    # ── Handshake step 1: challenge‑response ─────────────────────────
    async def _handshake_challenge(self) -> None:
        print("Waiting for device challenge …")
        data = await asyncio.wait_for(self._notifications.get(), timeout=15.0)

        if len(data) < 5 or data[:2] != b"\x2a\x2a" or data[2] != 0x01:
            raise RuntimeError(
                f"Expected 2A2A01… challenge, received: {data.hex()}"
            )

        # raw bytes: [2A, 2A, 01, 04, r0, r1, r2, r3, cksum]
        rand4 = data[4:8]                                   # 4 random bytes
        self.random_md5 = md5_hex(rand4[::-1])              # reverse → MD5

        # response packet: 2A 2A 02 04  <partial_md5>  <checksum>
        partial = self.random_md5[16:24].upper()             # positions 16‑23
        csum = sum_hex("0204" + partial)
        resp = bytes.fromhex(f"2A2A0204{partial}{csum}")

        # derive temporary AES‑128 key
        self.ble_conn_aes_key = xor_hex(self.random_md5.upper(), LOCAL_AES_KEY)

        await self.client.write_gatt_char(WRITE_UUID, resp, response=False)
        print("  Challenge response sent.")

    # ── Handshake step 2: ECDH key exchange ──────────────────────────
    async def _handshake_ecdh(self) -> None:
        # --- receive device's encrypted ECDH public key ---
        enc_data = await asyncio.wait_for(self._notifications.get(), timeout=15.0)
        iv = bytes.fromhex(self.random_md5)                  # fixed handshake IV

        dec_hex = parse_aes_cbc_data(enc_data.hex(), self.ble_conn_aes_key, iv)
        if not dec_hex.startswith("2A2A04"):
            raise RuntimeError(f"Expected 2A2A04, got: {dec_hex[:12]}")

        dec = bytes.fromhex(dec_hex)                         # 2A2A04|pubkey(64)|sig(64)|cksum

        # extract IoT public key (raw X+Y, 64 B) and ECDSA signature (64 B)
        iot_pk_bytes = dec[4:68]                             # bytes 4‑67
        sig_raw      = dec[68:-2]                            # bytes 68 … end‑2
        iot_pk_hex   = iot_pk_bytes.hex().upper()

        # verify device's signature over (iot_pk_hex || randomMd5)
        r = int.from_bytes(sig_raw[:32], "big")
        s = int.from_bytes(sig_raw[32:], "big")
        _public_key_k2.verify(
            encode_dss_signature(r, s),
            bytes.fromhex(iot_pk_hex + self.random_md5),
            ec.ECDSA(hashes.SHA256()),
        )
        print("  Device ECDSA signature verified.")

        # reconstruct device's ECDH public key (04 || X || Y)
        device_pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), b"\x04" + iot_pk_bytes
        )

        # generate ephemeral keypair
        self.ecdh_keypair = ec.generate_private_key(ec.SECP256R1())
        app_pub = self.ecdh_keypair.public_key()

        # app public key as raw X+Y (64 B, strip 04 marker)
        app_pk_hex = app_pub.public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )[1:].hex().upper()

        # sign (app_pk_hex || randomMd5) with PRIVATE_KEY_L1
        app_sig_der = _private_key_l1.sign(
            bytes.fromhex(app_pk_hex + self.random_md5),
            ec.ECDSA(hashes.SHA256()),
        )
        r2, s2 = decode_dss_signature(app_sig_der)
        sig_hex = (r2.to_bytes(32, "big") + s2.to_bytes(32, "big")).hex().upper()

        # build & encrypt ECDH response (2A2A0580 + app_pk + sig + cksum)
        csum = sum_hex("0580" + app_pk_hex + sig_hex)
        resp_hex = "2A2A0580" + app_pk_hex + sig_hex + csum
        enc_resp_hex = build_aes_cbc_cmd(resp_hex, self.ble_conn_aes_key, iv)

        await self.client.write_gatt_char(
            WRITE_UUID, bytes.fromhex(enc_resp_hex), response=False
        )
        print("  ECDH response sent.")

        # wait for acknowledgment (2A2A0600)
        ack = await asyncio.wait_for(self._notifications.get(), timeout=15.0)
        ack_dec_hex = parse_aes_cbc_data(ack.hex(), self.ble_conn_aes_key, iv)
        ack_dec = bytes.fromhex(ack_dec_hex)

        if len(ack_dec) < 5 or ack_dec[:3] != b"\x2a\x2a\x06" or ack_dec[4] != 0:
            raise RuntimeError(
                f"ECDH not acknowledged: {ack_dec_hex[:12]}"
            )

        # derive session key (AES‑256) from ECDH shared secret
        shared = self.ecdh_keypair.exchange(ec.ECDH(), device_pub)   # 32 B
        self.ble_conn_share_key = shared.hex().upper()               # 64 hex
        self.ble_conn_aes_key = None                                  # discard temp key

        print("  ECDH key exchange complete.")

    # ── Modbus read helper ───────────────────────────────────────────
    async def _read_modbus_register(self, addr: int, count: int) -> dict:
        """Build, encrypt, send and parse a single Modbus read."""
        # Modbus-RTU: slave=1, func=0x03 (read holding registers)
        frame = b"\x01\x03" + struct.pack(">H", addr) + struct.pack(">H", count)
        frame += crc16_modbus(frame)

        enc = build_aes_cbc_cmd(frame.hex().upper(), self.ble_conn_share_key)

        await self.client.write_gatt_char(
            WRITE_UUID, bytes.fromhex(enc), response=False
        )

        resp = await asyncio.wait_for(self._notifications.get(), timeout=15.0)
        dec = parse_aes_cbc_data(resp.hex(), self.ble_conn_share_key)
        resp_bytes = bytes.fromhex(dec)

        # Modbus response: [slave][func][data/count …][crc]
        func = resp_bytes[1]
        if func & 0x80:
            raise RuntimeError(
                f"Modbus error: func=0x{func:02X} code=0x{resp_bytes[2]:02X}"
            )

        byte_count = resp_bytes[2]
        data = resp_bytes[3 : 3 + byte_count]

        return self._parse_home_data(data)

    @staticmethod
    def _parse_home_data(data: bytes) -> dict:
        """Parse V2 'APP_HOME_DATA' payload.
        Field layout mirrors ProtocolParserV2.parseHomeData()."""
        return {
            "packTotalVoltage":   (data[0]  * 256 + data[1])  / 10.0,
            "packTotalCurrent":   (data[2]  * 256 + data[3])  / 10.0,
            "packTotalSoc":        data[4]  * 256 + data[5],           # 0‑100 %
            "packChargingStatus":  data[6]  * 256 + data[7],
            "packChgFullTime":     data[8]  * 256 + data[9],
            "packDsgEmptyTime":    data[10] * 256 + data[11],
        }


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

async def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <BLE_ADDRESS>")
        print(f"Example: {sys.argv[0]} AA:BB:CC:DD:EE:FF")
        sys.exit(1)

    address = sys.argv[1].upper()
    device = BluettiAC2A(address)

    try:
        await device.connect()
        home = await device.read_home_data()

        print("─" * 44)
        print(f"  Battery SOC:       {home['packTotalSoc']:>5} %")
        print(f"  Pack Voltage:      {home['packTotalVoltage']:>5.1f} V")
        print(f"  Pack Current:      {home['packTotalCurrent']:>5.1f} A")
        print(f"  Charging Status:   {home['packChargingStatus']:>5}")
        print(f"  Time to Full:      {home['packChgFullTime']:>5} min")
        print(f"  Time to Empty:     {home['packDsgEmptyTime']:>5} min")
        print("─" * 44)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        print(f"\nError: {exc}")
        raise
    finally:
        await device.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
