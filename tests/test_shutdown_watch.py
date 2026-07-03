# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


import pytest

from voltkeeper.shutdown_watch import ShutdownWatch


class TestShutdownWatch:
    def test_no_latch_above_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        assert w.handle_soc(50) is None
        assert not w.latched

    def test_no_latch_at_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        assert w.handle_soc(10) is None
        assert not w.latched

    def test_latch_below_threshold(self):
        w = ShutdownWatch(threshold=10, grace=60)
        cmd = w.handle_soc(5)
        assert cmd is None  # grace period hasn't expired yet
        assert w.latched
        assert w.fire_at is not None
        assert w.time_remaining > 0

    def test_latch_stays_set_on_recovery(self):
        w = ShutdownWatch(threshold=10, grace=60)
        w.handle_soc(5)
        assert w.latched
        w.handle_soc(80)
        assert w.latched  # still latched

    def test_grace_timer_shutdown_after_expiry(self):
        w = ShutdownWatch(threshold=10, grace=0)
        cmd = w.handle_soc(5)
        assert cmd == "sudo shutdown -h now"

    def test_grace_timer_not_expired(self):
        w = ShutdownWatch(threshold=10, grace=999)
        cmd = w.handle_soc(5)
        assert cmd is None
        assert w.time_remaining > 0

    def test_latch_triggers_recovery_log(self, caplog):
        import logging

        w = ShutdownWatch(threshold=10, grace=60)
        with caplog.at_level(logging.INFO):
            w.handle_soc(5)
            w.handle_soc(50)
        assert "shutdown already triggered" in caplog.text

    def test_execute_shutdown_raises_on_non_linux(self):
        import sys as _sys
        from unittest.mock import patch

        w = ShutdownWatch(threshold=10, grace=60)
        with patch.object(_sys, "platform", "win32"):
            with pytest.raises(RuntimeError, match="only supported on Linux"):
                w.execute_shutdown()
