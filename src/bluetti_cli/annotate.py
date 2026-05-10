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
    """Atomically write *profile* to *profile_path* as YAML."""
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(profile_path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ── Annotate loop ─────────────────────────────────────────────────────


async def annotate_loop(address: str, profile_path: Path, *, encrypted: bool) -> None:
    """Connect, poll register blocks, prompt for field names on changes."""
    profile = _load_or_init(profile_path)
    client = BluetoothClient(address, encrypted=encrypted)
    await client.connect()

    try:
        name = profile.get("name", "") or ""
        info = await _detect_protocol(client, name)

        if info.kind == "unknown":
            # Fall back to sweeping known V1 blocks
            blocks: list[tuple[int, int, str]] = [(addr, size_fn(0), name) for addr, name, size_fn in V1_BLOCKS]
        elif info.kind == "v1":
            ver = info.version or 0
            blocks = [(addr, size_fn(ver), name) for addr, name, size_fn in V1_BLOCKS]
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
        _save(profile, profile_path)

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
                        name = click.prompt("  Field name (or <Enter> to skip)", default="")
                    except (click.Abort, EOFError, KeyboardInterrupt):
                        click.echo()
                        return
                    if name.strip():
                        profile.setdefault("annotations", []).append(
                            {"block": block_name, "offset": offset, "name": name.strip()}
                        )
                        _save(profile, profile_path)
                last[block_name] = resp

            await asyncio.sleep(1)

    except (KeyboardInterrupt, click.Abort):
        click.echo("\nStopped.")
    finally:
        await client.disconnect()
