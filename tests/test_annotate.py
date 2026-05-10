# ABOUTME: Tests for annotate module — _diff, _load_or_init, _save.
# ABOUTME: Unit 13 per IMPLEMENTATION_UNITS.md.

import yaml

from src.bluetti_cli.annotate import (
    _diff,
    _format_change,
    _load_or_init,
    _registry_field_hints,
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
