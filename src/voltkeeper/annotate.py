# ABOUTME: Interactive annotate REPL — live polling, register-change detection, field-name prompts.

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


# ── UX helpers ────────────────────────────────────────────────────────


def _registry_field_hints() -> list[str]:
    """Collect the union of WRITABLE_FIELD_NAMES across registered devices.

    Surfaced to the user at session start so they have a vocabulary to
    pull from when labelling changed bytes.
    """
    from .bluetooth import _device_registry

    names: set[str] = set()
    for cls in _device_registry().values():
        names.update(getattr(cls, "WRITABLE_FIELD_NAMES", []))
    return sorted(names)


BASELINE_POLLS = 10
"""Cycles to observe at session start before listening for user-driven changes.

At ~1 second per cycle, ~10 polls is enough to catch the obvious noise
(currents, energy counters, frequency drift) without making the user wait
forever before they can interact with the device. Slowly-changing fields
(SOC ticks every few minutes, chgFullTime once a minute) won't show up
during baseline and will trigger one-off "spurious" changes during the
listening phase — acceptable cost.
"""


def _annotation_index(profile: dict) -> dict[tuple[str, int], str]:
    """Build a ``(block_name, offset) → name`` lookup from ``profile['annotations']``.

    Used to surface the existing label for an already-labelled byte
    when it changes again. Last entry wins on duplicate keys, matching
    the latest-wins semantics enforced by ``_replace_annotation``.
    """
    out: dict[tuple[str, int], str] = {}
    for entry in profile.get("annotations", []) or []:
        if not isinstance(entry, dict):
            continue
        block = entry.get("block")
        offset = entry.get("offset")
        name = entry.get("name")
        if isinstance(block, str) and isinstance(offset, int) and isinstance(name, str):
            out[(block, offset)] = name
    return out


def _replace_annotation(profile: dict, block: str, offset: int, name: str) -> None:
    """Set the annotation for ``(block, offset)`` to *name*, removing any prior entry.

    Latest-wins: typing a new name for an already-labelled byte replaces
    the old label rather than stacking another entry alongside it. Keeps
    the YAML clean for downstream maintainer consumption.
    """
    annotations = profile.setdefault("annotations", [])
    profile["annotations"] = [
        e for e in annotations if not (isinstance(e, dict) and e.get("block") == block and e.get("offset") == offset)
    ]
    profile["annotations"].append({"block": block, "offset": offset, "name": name})


async def _capture_baseline(
    client: BluetoothClient,
    blocks: list[tuple[int, int, str]],
    polls: int = BASELINE_POLLS,
) -> tuple[dict[str, bytes], dict[str, set[int]]]:
    """Sample blocks for *polls* cycles. Return (last snapshot, volatile bytes).

    A byte offset is "volatile" if its value changed at any point during
    the baseline window — the listening loop suppresses changes at
    those offsets so the user only sees signal from their own actions.
    """
    history: dict[str, list[bytes]] = {}
    for cycle in range(polls):
        for addr, size, block_name in blocks:
            resp = await client.execute(ReadHoldingRegisters(addr, size))
            history.setdefault(block_name, []).append(resp)
        # In-place progress; final newline printed by caller.
        click.echo(f"  baseline poll {cycle + 1}/{polls}\r", nl=False)
        if cycle < polls - 1:
            await asyncio.sleep(1)
    click.echo()  # finalize the progress line

    last: dict[str, bytes] = {}
    volatile: dict[str, set[int]] = {}
    for block_name, snapshots in history.items():
        last[block_name] = snapshots[-1]
        offsets: set[int] = set()
        for i in range(1, len(snapshots)):
            for offset, _, _ in _diff(snapshots[i - 1], snapshots[i]):
                offsets.add(offset)
        volatile[block_name] = offsets
    return last, volatile


def _format_change(block_name: str, addr: int, offset: int, old_byte: int, new_byte: int) -> str:
    """Render a one-line description of a changed byte using register coords.

    Modbus addresses things by register (16-bit word), so reporting
    register + byte-within-register is more useful than a raw byte
    offset when the user later wants to look it up in FINDINGS or the
    APK.
    """
    register = addr + (offset // 2)
    byte_in_reg = offset % 2
    return f"  [{block_name} reg {register} byte {byte_in_reg}]: 0x{old_byte:02X} → 0x{new_byte:02X}"


def _print_intro(profile_path: Path, model_sn: tuple[str, str] | None, num_blocks: int, hints: list[str]) -> None:
    """One-screen onboarding shown before polling starts.

    Explains the workflow (toggle on the device → watch the diff →
    label) and lists known field names so the user has a vocabulary.
    """
    if model_sn:
        model, real_sn = model_sn
        click.echo(f"\nAnnotating {model} SN {real_sn} → {profile_path}")
        click.echo(f"(SN scrubbed to {SYNTHETIC_SN_STR} in the saved file)\n")
    else:
        click.echo(f"\nAnnotating → {profile_path}\n")

    click.secho("How this works:", bold=True)
    click.echo("  1. Make a change on the device (toggle a switch, change a mode,")
    click.echo("     wait for SOC to tick down).")
    click.echo("  2. Watch which bytes change in the output below.")
    click.echo("  3. Type a short field name when prompted, or press Enter to skip.")
    click.echo("  4. Repeat for each thing you want to map.\n")

    if hints:
        click.secho("Common field names from existing models:", bold=True)
        # Wrap the hint list to fit a typical terminal width without dominating.
        wrapped = click.wrap_text(", ".join(hints), width=72, initial_indent="  ", subsequent_indent="  ")
        click.echo(wrapped + "\n")

    click.echo(f"Polling {num_blocks} register blocks. Press Ctrl-C to stop.\n")


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

        _print_intro(
            profile_path=profile_path,
            model_sn=split_model_sn(detect_name),
            num_blocks=len(blocks),
            hints=_registry_field_hints(),
        )

        click.echo(f"Capturing baseline ({BASELINE_POLLS} polls) to identify noisy fields...")
        last, volatile = await _capture_baseline(client, blocks, polls=BASELINE_POLLS)
        suppressed = sum(len(s) for s in volatile.values())
        click.echo(f"Baseline captured. Suppressing {suppressed} volatile byte(s) from change detection.")
        click.echo("Make a change on the device now.\n")

        # Lookup of (block, offset) → name from any prior session's annotations.
        # Refreshed in-place as the user adds new labels.
        annotations_index = _annotation_index(profile)

        while True:
            cycle_changes: list[tuple[str, int, int, int, int]] = []
            for addr, size, block_name in blocks:
                resp = await client.execute(ReadHoldingRegisters(addr, size))
                prev = last.get(block_name)
                vol = volatile.get(block_name, set())
                for offset, old_byte, new_byte in _diff(prev, resp):
                    if offset in vol:
                        continue
                    cycle_changes.append((block_name, addr, offset, old_byte, new_byte))
                last[block_name] = resp

            if cycle_changes:
                click.echo("─" * 60)
                click.echo(f"{len(cycle_changes)} byte(s) changed:")
                for block_name, addr, offset, old, new in cycle_changes:
                    line = _format_change(block_name, addr, offset, old, new)
                    existing = annotations_index.get((block_name, offset))
                    if existing:
                        line += click.style(f"   (currently: {existing})", fg="cyan")
                    click.echo(line)
                try:
                    field_name = click.prompt(
                        "\nField name for these changes (Enter to skip)",
                        default="",
                        show_default=False,
                    )
                except (click.Abort, EOFError, KeyboardInterrupt):
                    click.echo()
                    return
                if field_name.strip():
                    name_clean = field_name.strip()
                    for block_name, _addr, offset, _old, _new in cycle_changes:
                        _replace_annotation(profile, block_name, offset, name_clean)
                        annotations_index[(block_name, offset)] = name_clean
                    _save_scrubbed(profile, profile_path)
                    click.echo(f"  ✓ recorded {len(cycle_changes)} entries as {name_clean!r}\n")
                else:
                    click.echo("  (skipped)\n")

            await asyncio.sleep(1)

    except (KeyboardInterrupt, click.Abort):
        click.echo("\nStopped.")
    finally:
        await client.disconnect()
