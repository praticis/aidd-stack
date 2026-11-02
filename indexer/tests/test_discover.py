"""Which repos the planner finds, and what it says about each: through the mirrors, or with a plain fetch.

Real git, no network: `origin` is a bare repo on disk."""
from __future__ import annotations

from pathlib import Path

import pytest

from aidd_indexer.core.config import ConfigError
from aidd_indexer.core.manifest import RefPolicy, Source, TenantConfig
from aidd_indexer.core.planner import discover_repos
from test_mirror import git, world  # noqa: F401  (the fixture)


def acme(*sources: Source) -> TenantConfig:
    return TenantConfig(name="acme", sources=list(sources), refs=RefPolicy())


def local(path: Path, **kw) -> Source:
    return Source(type="local", path=str(path), **kw)


def test_mirrors_are_synced_in_order_and_each_repo_is_read_from_its_own(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    (tmp / "workspace" / "acme" / "broken-api" / ".git").mkdir(parents=True)
    said, errors = [], []
    repos, notes = discover_repos(acme(local(tmp / "workspace" / "acme")), progress=said.append, errors=errors)
    assert said == ["[mirror] broken-api", "[mirror] orders-api"]
    assert [(r.name, r.path, r.url, r.remote) for r in repos] == [
        ("orders-api", tmp / "mirrors" / "acme" / "orders-api.git", str(origin), "ok")]
    assert notes == []
    assert len(errors) == 1 and errors[0].startswith(
        f"broken-api: cannot sync mirror from {tmp / 'workspace' / 'acme' / 'broken-api'}: ")
    assert errors[0].endswith(" — skipped")


def test_without_an_errors_list_a_failed_sync_is_a_note(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    (tmp / "workspace" / "acme" / "broken-api" / ".git").mkdir(parents=True)
    repos, notes = discover_repos(acme(local(tmp / "workspace" / "acme")))
    assert [r.name for r in repos] == ["orders-api"]
    assert len(notes) == 1 and notes[0].startswith("broken-api: cannot sync mirror from ")


def test_a_failed_remote_fetch_is_recorded_on_the_repo_and_noted(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    git(dev, "remote", "set-url", "origin", str(tmp / "gone.git"))
    repos, notes = discover_repos(acme(local(tmp / "workspace" / "acme")))
    (r,) = repos
    assert r.remote.startswith("remote fetch failed (") and r.remote.endswith(") — indexed on local refs")
    assert notes == [f"orders-api: {r.remote}"]
    assert r.url == str(tmp / "gone.git")


@pytest.mark.parametrize("do_fetch,fetch", [(False, True), (True, False)])
def test_without_the_remote_half_nothing_is_said_about_it(world, monkeypatch, do_fetch, fetch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    repos, notes = discover_repos(acme(local(tmp / "workspace" / "acme", fetch=fetch)), do_fetch=do_fetch)
    assert [(r.name, r.remote, r.url) for r in repos] == [("orders-api", None, str(origin))]
    assert notes == []


def test_a_plain_fetch_without_mirrors(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.delenv("AIDD_MIRROR_DIR", raising=False)
    said = []
    repos, notes = discover_repos(acme(local(tmp / "workspace" / "acme")), progress=said.append)
    assert said == ["[fetch] orders-api"]
    assert [(r.name, r.path, r.url, r.remote) for r in repos] == [("orders-api", dev, "", "ok")]
    assert notes == []

    git(dev, "remote", "set-url", "origin", str(tmp / "gone.git"))
    (r,), notes = discover_repos(acme(local(tmp / "workspace" / "acme")))
    assert r.remote.startswith("git fetch failed (") and r.remote.endswith(") — planned on local refs")
    assert notes == [f"orders-api: {r.remote}"]

    said = []
    (r,), notes = discover_repos(acme(local(tmp / "workspace" / "acme")), do_fetch=False, progress=said.append)
    assert (said, r.remote, notes) == ([], None, [])


def test_sources_in_order_the_first_wins_and_remote_providers_are_a_note(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIDD_MIRROR_DIR", raising=False)
    for ws in ("one", "two"):
        for name in ("orders-api", "billing-api"):
            (tmp_path / ws / name / ".git").mkdir(parents=True)
    tenant = acme(local(tmp_path / "one", include=["orders-*"]), Source(type="github", org="acme", token_env="TOKEN"),
                  local(tmp_path / "two"))
    repos, notes = discover_repos(tenant, do_fetch=False)
    assert [(r.name, r.path) for r in repos] == [("orders-api", tmp_path / "one" / "orders-api"),
                                                 ("billing-api", tmp_path / "two" / "billing-api")]
    assert notes == ["source 'github' (org acme) not implemented yet (remote providers); skipped"]
    repos, _ = discover_repos(tenant, do_fetch=False, only={"billing-api"})
    assert [r.name for r in repos] == ["billing-api"]


def test_a_local_source_that_does_not_exist(tmp_path: Path):
    with pytest.raises(ConfigError) as e:
        discover_repos(acme(local(tmp_path / "missing")))
    assert str(e.value) == (f"local source path does not exist: {tmp_path / 'missing'} "
                            "(inside the container WORKSPACE_PATH is /workspace)")
