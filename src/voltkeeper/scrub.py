# ABOUTME: Replace serial-number material with synthetic values before writing
# ABOUTME: profile YAML files, so contributors can share/commit them safely.

from __future__ import annotations

import copy
import re

# These bytes round-trip through BcdSerialField.parse to "1234567890123",
# which is the canonical synthetic SN used in tests/fixtures/ac2a_probe_real.yml.
SYNTHETIC_SN_BYTES = bytes.fromhex("04cb71fb011f0000")
SYNTHETIC_SN_HEX = SYNTHETIC_SN_BYTES.hex()
SYNTHETIC_SN_STR = "1234567890123"

# Where the 8-byte SN field lives within each known register block.
# Sourced from the add_bcd_sn_field calls in V1Base and V2Base; if a new
# device class adds another SN-bearing block, extend this map.
#
#   block name        → (byte_offset_within_block, byte_length)
SN_LOCATIONS: dict[str, tuple[int, int]] = {
    "BASE_REAL_DATA": (22, 8),  # V1: register 21, 4 regs (block addr 10)
    "APP_HOME_DATA": (32, 8),  # V2: register 116, 4 regs (block addr 100)
    "INV_BASE_INFO": (14, 8),  # V2: register 1107, 4 regs (block addr 1100)
}

_NAME_SN_RE = re.compile(r"^([A-Z][A-Z0-9]+?)(\d{6,})$")


def scrub_name(name: str) -> str:
    """Replace the numeric SN suffix of a BLE device name with the synthetic SN.

    Falls through unchanged if *name* doesn't match the
    ``<MODEL_PREFIX><digits>`` pattern.
    """
    m = _NAME_SN_RE.match(name)
    if m is None:
        return name
    return m[1] + SYNTHETIC_SN_STR


def scrub_raw_hex(block_name: str, raw_hex: str) -> str:
    """Splice synthetic SN bytes into the SN region of a known block.

    Returns *raw_hex* unchanged if the block name has no registered SN
    location or the buffer is shorter than expected.
    """
    loc = SN_LOCATIONS.get(block_name)
    if loc is None:
        return raw_hex
    byte_offset, byte_length = loc
    hex_offset = byte_offset * 2
    hex_length = byte_length * 2
    if len(raw_hex) < hex_offset + hex_length:
        return raw_hex
    return raw_hex[:hex_offset] + SYNTHETIC_SN_HEX + raw_hex[hex_offset + hex_length :]


def scrub_profile(profile: dict) -> dict:
    """Return a deep-copied profile with all SN material replaced.

    Touches:
      - top-level ``name`` (BLE-advertised model+SN)
      - each ``blocks[<name>].raw_hex`` for blocks listed in SN_LOCATIONS

    Idempotent: scrubbing an already-scrubbed profile is a no-op.
    Does not mutate the input.
    """
    out = copy.deepcopy(profile)
    if isinstance(out.get("name"), str):
        out["name"] = scrub_name(out["name"])
    blocks = out.get("blocks")
    if isinstance(blocks, dict):
        for block_name, info in blocks.items():
            if isinstance(info, dict) and isinstance(info.get("raw_hex"), str):
                info["raw_hex"] = scrub_raw_hex(block_name, info["raw_hex"])
    return out


def split_model_sn(name: str) -> tuple[str, str] | None:
    """Return (model_prefix, sn_digits) for a BLE name, or None if it doesn't match.

    Useful for displaying the real SN to the user before scrubbing for write.
    """
    m = _NAME_SN_RE.match(name)
    if m is None:
        return None
    return m[1], m[2]
