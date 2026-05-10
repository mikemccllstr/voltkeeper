# ABOUTME: Tests for annotate module — _diff, _load_or_init, _save.
# ABOUTME: Unit 13 per IMPLEMENTATION_UNITS.md.

import yaml

from src.bluetti_cli.annotate import _diff, _load_or_init, _save

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
