"""Run state of the refresher service: lock, status file, health, graceful stop.

The `refresher` compose service runs `aidd daemon`: a loop that runs `refresh` for every tenant of the
manifest every `AIDD_REFRESH_INTERVAL_MINUTES` (± 10 % jitter, counted from the end of the previous
run, so a laptop waking up does not fire a burst). It replaces the host schedulers (systemd timer,
Task Scheduler, cron): Docker restarts it, on every OS, with nothing installed on the host.

`$AIDD_STATE_DIR` (bind-mounted from ~/.aidd/state) holds:
  refresh.lock   held during a refresh — the loop and a manual `aidd refresh` never overlap
  status.json    the last run: start/end (ISO + epoch), rc, trigger, per-tenant counts; written at
                 start (`running: true`) and at the end. The compose healthcheck (`aidd daemon-health`)
                 and the host wrapper (`aidd schedule status`) read it — no database needed.
"""

from __future__ import annotations

import fcntl
import json
import os
import random
import signal
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

STOP = threading.Event()        # set by SIGTERM/SIGINT: finish the current snapshot, then exit


class Busy(RuntimeError):
    """Another refresh holds the lock."""


def state_dir() -> Path | None:
    v = os.getenv("AIDD_STATE_DIR", "").strip()
    return Path(v) if v else None


def interval_min() -> int:
    try:
        return max(1, int(os.getenv("AIDD_REFRESH_INTERVAL_MINUTES", "15")))
    except ValueError:
        return 15


@contextmanager
def refresh_lock() -> Iterator[None]:
    d = state_dir()
    if d is None:
        yield
        return
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "refresh.lock", "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Busy("another refresh is still running") from e
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def read_status() -> dict[str, Any]:
    d = state_dir()
    try:
        return json.loads((d / "status.json").read_text()) if d else {}
    except (OSError, ValueError):
        return {}


def write_status(**fields: Any) -> None:
    """Best effort: a state directory we cannot write must not stop the indexing (the healthcheck
    then reports it — `writable_dirs` says why at startup)."""
    d = state_dir()
    if d is None:
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
        cur = read_status()
        cur.update(fields, interval_min=interval_min())
        tmp = d / "status.json.tmp"
        tmp.write_text(json.dumps(cur, indent=2, default=str))
        tmp.replace(d / "status.json")
    except OSError as e:
        import sys
        print(f"[daemon] cannot write {d / 'status.json'}: {e}", file=sys.stderr, flush=True)


def unwritable_dirs(dirs: list[Path]) -> list[str]:
    """The bind-mounted directories the refresher writes to, probed with a real write. On Docker
    Desktop a directory owned by another user (install.sh under sudo) fails here, not at mkdir."""
    bad = []
    for d in dirs:
        probe = d / f".write-probe-{os.getpid()}"
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok")
            probe.unlink()
        except OSError as e:
            bad.append(f"{d}: {e.strerror or e}")
    return bad


def mark_start(trigger: str) -> float:
    t = time.time()
    write_status(running=True, trigger=trigger, last_started_at=_now().isoformat(), last_started_epoch=int(t))
    return t


def mark_end(rc: int, tenants: dict[str, Any]) -> None:
    write_status(running=False, last_rc=rc, last_finished_at=_now().isoformat(), last_finished_epoch=int(time.time()),
                 tenants=tenants)


def health(now: float | None = None, status: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Healthy = a refresh finished within 2 intervals, or one is running and has not run for longer
    than 6 intervals (a first bootstrap of a big portfolio is slow). A failed last run is reported
    but stays healthy: the loop is alive, the cause is in the log."""
    now = now or time.time()
    st = status if status is not None else read_status()
    every = int(st.get("interval_min") or interval_min()) * 60
    if st.get("running"):
        age = now - int(st.get("last_started_epoch") or now)
        if age > 6 * every:
            return False, f"refresh running for {int(age // 60)} min (interval {every // 60} min) — stuck?"
        return True, f"refresh running for {int(age // 60)} min"
    end = st.get("last_finished_epoch")
    if not end:
        return False, "no refresh has finished yet"
    age = now - int(end)
    rc = st.get("last_rc")
    note = "" if rc == 0 else f" — last run failed (rc={rc})"
    if age > 2 * every:
        return False, f"last refresh {int(age // 60)} min ago (interval {every // 60} min){note}"
    return True, f"last refresh {int(age // 60)} min ago{note}"


def next_delay(base_s: int, rng: random.Random | None = None) -> float:
    r = rng or random
    return base_s * (0.9 + 0.2 * r.random())


def install_signal_handlers() -> None:
    def _stop(signum, _frame):
        STOP.set()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
