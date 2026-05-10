# ABOUTME: Interactive annotate REPL — live polling, register-change detection, field-name prompts.
# ABOUTME: Unit 13 per IMPLEMENTATION_UNITS.md.

from __future__ import annotations

import asyncio
from pathlib import Path

import click
import yaml

from .bluetooth.client import BluetoothClient
from .core.commands import ReadHoldingRegisters
from .probe import V1_BLOCKS, V2_BLOCKS, _detect_protocol
from .scrub import SYNTHETIC_SN_STR, scrub_profile, split_model_sn

# ── Diff helper ───────────────────────────────────────────────────────


def _diff(prev: bytes | None, curr: bytes) -> list[tuple[int, int, int]]:
    """Compare two byte sequences, return (offset, old_byte, new_byte) for each change.

    If *prev* is None (first read), returns empty list.
    Diffs only up to the shorter of the two lengths.
    """
    if prev is None:
        return []
    length = min(len(prev), len(curr))
    changes: list[tuple[int, int, int]] = []
    for i in range(length):
        if prev[i] != curr[i]:
            changes.append((i, prev[i], curr[i]))
    return changes


# ── File helpers ──────────────────────────────────────────────────────


def _load_or_init(profile_path: Path) -> dict:
    """Load an existing YAML profile or return a fresh skeleton."""
    if profile_path.exists():
        with open(profile_path) as f:
            profile = yaml.safe_load(f)
        if isinstance(profile, dict):
            return profile
    return {"annotations": []}


def _save(profile: dict, profile_path: Path) -> None:
    """Atomically write *profile* to *profile_path* as YAML.

    Writes to a sibling temp file then ``os.replace``s it into place so
    a Ctrl-C mid-write can't truncate an existing valid YAML.
    """
    import os

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = profile_path.with_suffix(profile_path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, profile_path)


def _save_scrubbed(profile: dict, profile_path: Path) -> None:
    """Save *profile* with the SN replaced by a synthetic placeholder.

    Use this for any annotate persistence: the in-memory dict keeps the
    real BLE name for registry-shortcut lookups across sessions, while
    the on-disk YAML is privacy-safe to share.
    """
    _save(scrub_profile(profile), profile_path)


# ── Annotate loop ─────────────────────────────────────────────────────


async def annotate_loop(
    address: str,
    profile_path: Path,
    *,
    encrypted: bool,
    device_name: str = "",
) -> None:
    """Connect, poll register blocks, prompt for field names on changes.

    *device_name* is the BLE-advertised name (e.g., ``"AC2A2305000"``).
    Passing it lets ``_detect_protocol`` take the registry shortcut on
    the first run, before the profile YAML has a ``name`` field stored.
    """
    profile = _load_or_init(profile_path)
    client = BluetoothClient(address, encrypted=encrypted)
    await client.connect()

    try:
        # Prefer the live BLE name; fall back to whatever the saved profile has.
        detect_name = device_name or profile.get("name", "") or ""
        info = await _detect_protocol(client, detect_name)

        if info.kind == "unknown":
            # Fall back to sweeping known V1 blocks
            blocks: list[tuple[int, int, str]] = [
                (addr, size_fn(0), block_name) for addr, block_name, size_fn in V1_BLOCKS
            ]
        elif info.kind == "v1":
            ver = info.version or 0
            blocks = [(addr, size_fn(ver), block_name) for addr, block_name, size_fn in V1_BLOCKS]
        else:
            blocks = list(V2_BLOCKS)

        if not blocks:
            click.secho("No register blocks to poll.", fg="yellow")
            return

        # Save protocol info into the profile for future runs
        profile.setdefault("protocol", info.kind)
        profile.setdefault("protocol_version", info.version)
        profile.setdefault("address", address)
        profile.setdefault("encrypted", encrypted)
        if detect_name:
            profile.setdefault("name", detect_name)
        _save_scrubbed(profile, profile_path)

        # Show the real device identity to the user; the on-disk YAML has
        # a synthetic SN so it's safe to share/commit.
        parts = split_model_sn(detect_name)
        if parts:
            model, real_sn = parts
            click.echo(
                f"Annotating {model} SN {real_sn} → {profile_path} (SN scrubbed to {SYNTHETIC_SN_STR} in saved file)"
            )

        last: dict[str, bytes] = {}
        click.echo(f"Polling {len(blocks)} register blocks. Press Ctrl-C to stop.\n")

        while True:
            for addr, size, block_name in blocks:
                resp = await client.execute(ReadHoldingRegisters(addr, size))
                prev = last.get(block_name)
                changes = _diff(prev, resp)
                for offset, old_byte, new_byte in changes:
                    hex_offset = f"0x{addr * 2 + offset:04X}"
                    click.echo(f"\n  [{block_name}] offset {hex_offset}: 0x{old_byte:02X} → 0x{new_byte:02X}")
                    try:
                        field_name = click.prompt("  Field name (or <Enter> to skip)", default="")
                    except (click.Abort, EOFError, KeyboardInterrupt):
                        click.echo()
                        return
                    if field_name.strip():
                        profile.setdefault("annotations", []).append(
                            {"block": block_name, "offset": offset, "name": field_name.strip()}
                        )
                        _save_scrubbed(profile, profile_path)
                last[block_name] = resp

            await asyncio.sleep(1)

    except (KeyboardInterrupt, click.Abort):
        click.echo("\nStopped.")
    finally:
        await client.disconnect()
