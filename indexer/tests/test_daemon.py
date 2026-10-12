"""Refresher service state: lock, status file, health, jitter."""
from __future__ import annotations

import os
import random

import pytest

from aidd_indexer import daemon


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("AIDD_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AIDD_REFRESH_INTERVAL_MINUTES", "15")
    return tmp_path


def test_lock_excludes_a_second_refresh(state):
    with daemon.refresh_lock():
        with pytest.raises(daemon.Busy):
            with daemon.refresh_lock():
                pass
    with daemon.refresh_lock():                     # released
        pass


def test_status_round_trip_and_health(state):
    assert daemon.health() == (False, "no refresh has finished yet")
    daemon.mark_start("scheduled")
    assert daemon.read_status()["running"] is True
    ok, msg = daemon.health()
    assert ok and "running" in msg
    daemon.mark_end(0, {"acme": {"changed": 2}})
    st = daemon.read_status()
    assert st["running"] is False and st["last_rc"] == 0 and st["interval_min"] == 15
    assert st["tenants"]["acme"]["changed"] == 2
    ok, _ = daemon.health()
    assert ok


def test_health_flags_a_dead_or_stuck_loop():
    now = 100_000
    fresh = {"interval_min": 15, "running": False, "last_finished_epoch": now - 10 * 60, "last_rc": 1}
    ok, msg = daemon.health(now, fresh)
    assert ok and "rc=1" in msg                     # failed run: alive, reported
    dead = dict(fresh, last_finished_epoch=now - 31 * 60)
    assert daemon.health(now, dead)[0] is False     # > 2 intervals
    stuck = {"interval_min": 15, "running": True, "last_started_epoch": now - 91 * 60}
    assert daemon.health(now, stuck)[0] is False    # > 6 intervals running
    slow = dict(stuck, last_started_epoch=now - 60 * 60)
    assert daemon.health(now, slow)[0] is True      # a long bootstrap is fine


def test_jitter_stays_within_ten_percent():
    rng = random.Random(7)
    delays = [daemon.next_delay(900, rng) for _ in range(200)]
    assert min(delays) >= 810 and max(delays) <= 990


def test_no_state_dir_means_no_lock_and_no_status(monkeypatch):
    monkeypatch.delenv("AIDD_STATE_DIR", raising=False)
    with daemon.refresh_lock():
        with daemon.refresh_lock():                 # plain CLI use outside the service: nothing to lock
            pass
    daemon.mark_start("manual")
    assert daemon.read_status() == {}


def test_unwritable_state_is_reported_not_fatal(tmp_path, monkeypatch):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        if os.access(ro, os.W_OK):                  # running as root: permissions do not bind
            pytest.skip("root ignores directory permissions")
        assert daemon.unwritable_dirs([ro, tmp_path]) and len(daemon.unwritable_dirs([ro, tmp_path])) == 1
        monkeypatch.setenv("AIDD_STATE_DIR", str(ro))
        daemon.mark_start("scheduled")              # logs, does not raise: the refresh still runs
        assert daemon.read_status() == {}
    finally:
        ro.chmod(0o700)
