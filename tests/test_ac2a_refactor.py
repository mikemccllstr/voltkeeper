# ABOUTME: Baseline capture and comparison test for AC2A → V2Base refactor.
# ABOUTME: Unit 8 per IMPLEMENTATION_UNITS.md.

import json
from decimal import Decimal
from enum import Enum
from pathlib import Path

from src.bluetti_cli.core.devices.ac2a import (
    AC2A,
    INV_BASE_INFO,
    INV_GRID_INFO,
    INV_INV_INFO,
    INV_LOAD_INFO,
    INV_PV_INFO,
)
from src.bluetti_cli.core.devices.v2_base import APP_HOME_DATA

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ac2a_baseline.json"


def _make_serializable(d: dict) -> dict:
    """Convert enum/Decimal values for JSON serialization."""
    result = {}
    for k, v in d.items():
        if isinstance(v, Enum):
            result[k] = v.name
        elif isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, float) and v.is_integer():
            result[k] = int(v)
        else:
            result[k] = v
    return result


def _make_data(start: int, size: int) -> bytes:
    """Generate all-zero register data — safe for all enum/bool fields."""
    return bytes(size * 2)


def test_capture_ac2a_baseline():
    """Generate a JSON fixture representing the CURRENT AC2A parsing output.

    If the fixture already exists, load it and assert the current AC2A
    produces identical output. If it doesn't exist, create it.
    """
    device = AC2A("00:00:00:00:00:00", "TEST")

    # Parse each register block with deterministic data
    blocks: dict[str, dict] = {}
    for start, size, name in [
        (APP_HOME_DATA, 62, "home"),
        (INV_BASE_INFO, 51, "inv_base"),
        (INV_PV_INFO, 70, "inv_pv"),
        (INV_GRID_INFO, 31, "inv_grid"),
        (INV_LOAD_INFO, 48, "inv_load"),
        (INV_INV_INFO, 30, "inv_inv"),
    ]:
        data = _make_data(start, size)
        blocks[name] = device.parse(start, data)

    if FIXTURE_PATH.exists():
        expected = json.loads(FIXTURE_PATH.read_text())
        serialized = {name: _make_serializable(sub) for name, sub in blocks.items()}
        assert serialized == expected, "AC2A parse output diverged from baseline; did you intentionally change parsing?"
    else:
        Path(FIXTURE_PATH).parent.mkdir(exist_ok=True)
        serialized = {name: _make_serializable(sub) for name, sub in blocks.items()}
        FIXTURE_PATH.write_text(json.dumps(serialized, indent=2, sort_keys=True))
