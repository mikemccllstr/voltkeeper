# ABOUTME: Tests for annotate module — _diff, _load_or_init, _save.
# ABOUTME: Unit 13 per IMPLEMENTATION_UNITS.md.

import yaml

from src.bluetti_cli.annotate import (
    _annotation_index,
    _diff,
    _format_change,
    _load_or_init,
    _registry_field_hints,
    _replace_annotation,
    _save,
)

# ── _diff tests ───────────────────────────────────────────────────────


def test_diff_no_previous():
    """First read — nothing to diff against."""
    curr = b"\x00\x01\x02"
    result = _diff(None, curr)
    assert result == []


def test_diff_no_changes():
    """Same bytes — no changes."""
    prev = b"\xaa\xbb\xcc"
    curr = b"\xaa\xbb\xcc"
    result = _diff(prev, curr)
    assert result == []


def test_diff_single_byte_change():
    prev = b"\x00\x00\x00"
    curr = b"\x00\xff\x00"
    result = _diff(prev, curr)
    assert result == [(1, 0, 0xFF)]


def test_diff_multiple_changes():
    prev = b"\x01\x02\x03\x04"
    curr = b"\xff\x02\xff\x04"
    result = _diff(prev, curr)
    assert result == [(0, 1, 0xFF), (2, 3, 0xFF)]


def test_diff_length_mismatch_short_curr():
    """Longer prev — diff up to curr length."""
    prev = b"\x01\x02\x03\x04"
    curr = b"\xff\x02"
    result = _diff(prev, curr)
    assert result == [(0, 1, 0xFF)]


def test_diff_length_mismatch_short_prev():
    """Longer curr — diff up to prev length, treat extra as new bytes."""
    prev = b"\x01\x02"
    curr = b"\xff\x02\x03\x04"
    result = _diff(prev, curr)
    # offset 0 changed, offsets 2-3 are "new" (treated as change from 0)
    assert result == [(0, 1, 0xFF)]


def test_diff_all_bytes_changed():
    prev = b"\x00\x00"
    curr = b"\xff\xff"
    result = _diff(prev, curr)
    assert result == [(0, 0, 0xFF), (1, 0, 0xFF)]


# ── _load_or_init / _save tests ──────────────────────────────────────


def test_load_or_init_empty(tmp_path):
    p = tmp_path / "draft.yaml"
    profile = _load_or_init(p)
    assert profile == {"annotations": []}


def test_load_or_init_existing(tmp_path):
    p = tmp_path / "draft.yaml"
    existing = {"annotations": [{"block": "TEST", "offset": 5, "name": "field1"}]}
    with open(p, "w") as f:
        yaml.dump(existing, f)
    profile = _load_or_init(p)
    assert profile == existing


def test_save_and_reload(tmp_path):
    p = tmp_path / "draft.yaml"
    profile = {"annotations": [{"block": "B1", "offset": 0, "name": "foo"}]}
    _save(profile, p)

    with open(p) as f:
        reloaded = yaml.safe_load(f)
    assert reloaded == profile


def test_load_or_init_inherits_existing_fields(tmp_path):
    """_load_or_init preserves non-annotation top-level keys."""
    p = tmp_path / "draft.yaml"
    existing = {"annotations": [], "address": "AA:BB", "model": "AC2A"}
    with open(p, "w") as f:
        yaml.dump(existing, f)
    profile = _load_or_init(p)
    assert profile["address"] == "AA:BB"
    assert profile["model"] == "AC2A"
    assert profile["annotations"] == []


def test_save_creates_parent_dirs(tmp_path):
    p = tmp_path / "subdir" / "draft.yaml"
    profile = {"annotations": []}
    _save(profile, p)
    assert p.exists()
    with open(p) as f:
        reloaded = yaml.safe_load(f)
    assert reloaded == profile


def test_save_is_atomic_preserves_old_file_on_failure(tmp_path, monkeypatch):
    """If yaml.dump raises mid-write, the existing file is untouched."""
    p = tmp_path / "draft.yaml"
    good = {"annotations": [{"block": "B1", "offset": 0, "name": "kept"}]}
    _save(good, p)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated dump failure")

    monkeypatch.setattr("src.bluetti_cli.annotate.yaml.dump", boom)
    try:
        _save({"annotations": [{"block": "B2", "offset": 1, "name": "lost"}]}, p)
    except RuntimeError:
        pass

    # Original file is intact and parseable
    with open(p) as f:
        reloaded = yaml.safe_load(f)
    assert reloaded == good


# ── UX helpers ────────────────────────────────────────────────────────


def test_registry_field_hints_includes_known_writable_names():
    """Hints surface writable-field names from registered devices.

    Locks the contract that the intro screen has a non-empty vocabulary.
    """
    hints = _registry_field_hints()
    assert "ac_output" in hints  # AC2A, AC60, AC300, etc.
    assert "charging_mode" in hints  # AC2A, AC60, AC300
    assert "factory_reset" in hints
    assert hints == sorted(hints)  # deterministic order


def test_format_change_uses_register_and_byte_coords():
    """Changes report (register, byte) — easier to look up than raw byte offset."""
    # Block at register 100, byte offset 49 within the block.
    # → register 100 + 49//2 = 124, byte 49%2 = 1.
    line = _format_change("APP_HOME_DATA", 100, 49, 0x00, 0x40)
    assert "APP_HOME_DATA" in line
    assert "reg 124" in line
    assert "byte 1" in line
    assert "0x00" in line
    assert "0x40" in line


def test_format_change_byte_zero_is_high_byte():
    """Modbus byte 0 of register N is the high byte; verify coords align."""
    line = _format_change("INV_BASE_INFO", 1100, 0, 0xAA, 0xBB)
    assert "reg 1100 byte 0" in line


# ── Annotation index + latest-wins replacement ────────────────────────


def test_annotation_index_builds_lookup_from_profile():
    profile = {
        "annotations": [
            {"block": "APP_HOME_DATA", "offset": 48, "name": "ac_output"},
            {"block": "APP_HOME_DATA", "offset": 49, "name": "ac_output"},
            {"block": "INV_INV_INFO", "offset": 0, "name": "inv_voltage"},
        ]
    }
    idx = _annotation_index(profile)
    assert idx == {
        ("APP_HOME_DATA", 48): "ac_output",
        ("APP_HOME_DATA", 49): "ac_output",
        ("INV_INV_INFO", 0): "inv_voltage",
    }


def test_annotation_index_handles_missing_or_malformed_entries():
    # No annotations key, malformed entries, type mismatches — all skipped.
    assert _annotation_index({}) == {}
    assert _annotation_index({"annotations": None}) == {}
    assert (
        _annotation_index(
            {
                "annotations": [
                    "not a dict",
                    {"block": "X"},  # missing offset/name
                    {"block": "X", "offset": "not int", "name": "y"},
                    {"block": "X", "offset": 0, "name": 42},  # name not str
                ]
            }
        )
        == {}
    )


def test_annotation_index_last_entry_wins_on_duplicate_key():
    """If the YAML has duplicates, _annotation_index uses the last one.

    Matches the latest-wins semantics enforced by _replace_annotation.
    """
    profile = {
        "annotations": [
            {"block": "B", "offset": 0, "name": "old"},
            {"block": "B", "offset": 0, "name": "new"},
        ]
    }
    assert _annotation_index(profile) == {("B", 0): "new"}


def test_replace_annotation_adds_when_absent():
    profile: dict = {}
    _replace_annotation(profile, "APP_HOME_DATA", 48, "ac_output")
    assert profile["annotations"] == [{"block": "APP_HOME_DATA", "offset": 48, "name": "ac_output"}]


def test_replace_annotation_removes_prior_entry_for_same_byte():
    """Calling twice for the same (block, offset) leaves only the latest entry."""
    profile = {
        "annotations": [
            {"block": "APP_HOME_DATA", "offset": 48, "name": "ac_output"},
            {"block": "APP_HOME_DATA", "offset": 49, "name": "ac_output"},  # untouched
        ]
    }
    _replace_annotation(profile, "APP_HOME_DATA", 48, "ac_switch_state")
    # Only the offset-48 entry should be replaced; offset 49 untouched.
    names_at_48 = [e for e in profile["annotations"] if e["offset"] == 48]
    assert names_at_48 == [{"block": "APP_HOME_DATA", "offset": 48, "name": "ac_switch_state"}]
    names_at_49 = [e for e in profile["annotations"] if e["offset"] == 49]
    assert names_at_49 == [{"block": "APP_HOME_DATA", "offset": 49, "name": "ac_output"}]


def test_replace_annotation_only_matches_same_block():
    """Same offset in a different block is not replaced."""
    profile = {
        "annotations": [
            {"block": "APP_HOME_DATA", "offset": 48, "name": "in_home"},
            {"block": "INV_INV_INFO", "offset": 48, "name": "in_inv"},
        ]
    }
    _replace_annotation(profile, "APP_HOME_DATA", 48, "renamed")
    by_block = {e["block"]: e["name"] for e in profile["annotations"]}
    assert by_block == {"APP_HOME_DATA": "renamed", "INV_INV_INFO": "in_inv"}


# ── Baseline volatile-byte capture ────────────────────────────────────


def test_capture_baseline_marks_changing_bytes_as_volatile(monkeypatch):
    """A byte that flips during baseline ends up in the volatile set."""
    import asyncio
    from unittest.mock import AsyncMock

    from src.bluetti_cli.annotate import _capture_baseline

    # No real waiting between polls.
    monkeypatch.setattr("src.bluetti_cli.annotate.asyncio.sleep", AsyncMock())

    # 4-byte block. Byte 1 wiggles every cycle; byte 3 stays constant.
    snapshots = [
        b"\x00\x00\xff\xaa",
        b"\x00\x10\xff\xaa",
        b"\x00\x00\xff\xaa",
    ]
    client = AsyncMock()
    client.execute = AsyncMock(side_effect=snapshots)

    blocks = [(100, 4, "APP_HOME_DATA")]
    last, volatile = asyncio.run(_capture_baseline(client, blocks, polls=3))

    assert last["APP_HOME_DATA"] == b"\x00\x00\xff\xaa"
    # Byte 1 flipped 0→0x10→0; bytes 0/2/3 stayed put.
    assert volatile["APP_HOME_DATA"] == {1}


def test_capture_baseline_with_stable_data_no_volatile_bytes(monkeypatch):
    """If nothing changes during baseline, the volatile set is empty."""
    import asyncio
    from unittest.mock import AsyncMock

    from src.bluetti_cli.annotate import _capture_baseline

    monkeypatch.setattr("src.bluetti_cli.annotate.asyncio.sleep", AsyncMock())

    stable = b"\xde\xad\xbe\xef"
    client = AsyncMock()
    client.execute = AsyncMock(return_value=stable)

    blocks = [(200, 4, "INV_INV_INFO")]
    last, volatile = asyncio.run(_capture_baseline(client, blocks, polls=4))

    assert last["INV_INV_INFO"] == stable
    assert volatile["INV_INV_INFO"] == set()
