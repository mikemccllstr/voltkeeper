# ABOUTME: Unit tests for bluetti_cli.bluetooth module — registry dispatch, build_device.
# ABOUTME: Unit 1 per IMPLEMENTATION_UNITS.md.

import pytest

from src.bluetti_cli.bluetooth import build_device


def test_build_device_rejects_unknown():
    with pytest.raises(ValueError, match="Unsupported device model"):
        build_device("AA:BB:CC:DD:EE:FF", "EP600123456")
