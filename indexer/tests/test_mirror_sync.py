"""A mirror's sync step by step: created once, filled from the workspace (with one retry), then from `origin`.

Real git, no network: `origin` is a bare repo on disk. Where git cannot be made to fail on cue, the module's `_git`
is wrapped."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aidd_indexer.core import mirror as mirror_module
from aidd_indexer.core.gitinfo import default_ref
from aidd_indexer.core.mirror import mirror_path, sync
from test_mirror import git, world  # noqa: F401  (the fixture)


def calls(monkeypatch, fail=lambda args: None) -> list[list[str]]:
    """Every `_git` call's arguments; `fail(args)` returns an answer to give instead of running git."""
    seen: list[list[str]] = []
    real = mirror_module._git

    def spy(args, timeout):
        seen.append(list(args))
        return fail(args) or real(args, timeout)
    monkeypatch.setattr(mirror_module, "_git", spy)
    return seen


def origin_url(m: Path) -> str | None:
    out = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(m), "config", "remote.origin.url"],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip() if out.returncode == 0 else None


def from_workspace(args: list[str], ws: Path) -> bool:
    return "fetch" in args and str(ws) in args


@pytest.fixture()
def no_token(monkeypatch):
    for k in [k for k in __import__("os").environ if k.startswith("AIDD_GIT_TOKEN")]:
        monkeypatch.delenv(k)


def test_a_mirror_is_created_once(world, monkeypatch):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    assert sync(dev, m) == (True, "ok") and (m / "HEAD").exists()
    seen = calls(monkeypatch)
    assert sync(dev, m) == (True, "ok")
    assert not any(a[0] == "init" for a in seen)


def test_a_mirror_that_cannot_be_created(world, monkeypatch):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    calls(monkeypatch, fail=lambda args: (128, "fatal: no room") if args[0] == "init" else None)
    with pytest.raises(RuntimeError) as e:
        sync(dev, m)
    assert str(e.value) == f"cannot create mirror {m}: fatal: no room"


def test_the_workspace_copy_is_tried_twice(world, monkeypatch):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    failed = []

    def once(args):
        if from_workspace(args, dev) and not failed:
            failed.append(args)
            return 1, "fatal: did not send all necessary objects"
        return None
    seen = calls(monkeypatch, fail=once)
    assert sync(dev, m, remote=False) == (False, "local only (--no-fetch)")
    assert len([a for a in seen if from_workspace(a, dev)]) == 2
    assert git(m, "rev-parse", "--verify", "refs/heads/feature/local-only")

    seen.clear()
    sync(dev, m, remote=False)
    assert len([a for a in seen if from_workspace(a, dev)]) == 1


def test_a_workspace_that_cannot_be_read_fails_both_passes(tmp_path: Path, monkeypatch):
    ws = tmp_path / "not-a-repo"
    ws.mkdir()
    m = mirror_path(tmp_path / "mirrors", "acme", "not-a-repo")
    seen = calls(monkeypatch)
    with pytest.raises(RuntimeError) as e:
        sync(ws, m)
    prefix = f"cannot sync mirror from {ws}: "
    assert str(e.value).startswith(prefix) and str(e.value) != prefix       # git's own reason follows
    assert len([a for a in seen if from_workspace(a, ws)]) == 2


def test_the_workspace_copy_brings_the_developer_branches_and_origin_head(world):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    sync(dev, m, remote=False)
    assert git(m, "symbolic-ref", "refs/remotes/origin/HEAD") == "refs/remotes/origin/main"
    assert default_ref(m) == "main"
    assert git(m, "rev-parse", "refs/heads/feature/local-only") == git(dev, "rev-parse", "feature/local-only")


def test_the_remote_half_says_why_it_did_not_run(world, no_token):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    assert sync(dev, m, remote=False) == (False, "local only (--no-fetch)")
    assert origin_url(m) == str(origin)

    git(dev, "remote", "set-url", "origin", "git@github.com:acme/orders-api.git")
    assert sync(dev, m) == (False, "local only (ssh remote and no service token — the mirror follows your own fetches)")
    assert origin_url(m) == "git@github.com:acme/orders-api.git"

    git(dev, "remote", "remove", "origin")
    assert sync(dev, m) == (False, "local only (no origin remote)")
    assert origin_url(m) is None


def test_the_remote_half_with_a_token_and_when_it_fails(world, monkeypatch, no_token):
    tmp, origin, dev = world
    m = mirror_path(tmp / "mirrors", "acme", "orders-api")
    monkeypatch.setenv("AIDD_GIT_TOKEN", "not-used-by-a-local-remote")
    seen = calls(monkeypatch)
    assert sync(dev, m) == (True, "ok")
    remote = [a for a in seen if "origin" in a and "fetch" in a]
    assert remote and remote[0][:2] == ["-C", str(m)]                    # no rewrite for a path remote

    git(dev, "remote", "set-url", "origin", str(tmp / "gone.git"))
    ok, msg = sync(dev, m)
    assert not ok and msg.startswith("remote fetch failed (") and msg.endswith(") — indexed on local refs")
    assert msg != "remote fetch failed () — indexed on local refs"
