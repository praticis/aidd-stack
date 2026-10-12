"""Mirrors: the workspace repo is only read; the planner reads the mirror.

Real git, no network: `origin` is a bare repo on disk. The developer's clone has a branch they never
pushed and is missing a branch someone else pushed after their last fetch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aidd_indexer.core.gitinfo import branch_sha, default_ref, list_branches
from aidd_indexer.core.manifest import load_manifest
from aidd_indexer.core.mirror import https_rewrite, mirror_path, sync
from aidd_indexer.core.planner import build_plan


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "safe.directory=*", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                               "GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)}
                          ).stdout.strip()


@pytest.fixture()
def world(tmp_path: Path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-q", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    (seed / "app.go").write_text("package app\n\nfunc Run() {}\n")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "init")
    git(seed, "push", "-q", "origin", "main")

    ws = tmp_path / "workspace" / "acme"
    ws.mkdir(parents=True)
    dev = ws / "orders-api"
    git(tmp_path, "clone", "-q", str(origin), str(dev))
    git(dev, "checkout", "-q", "-b", "feature/local-only")            # never pushed
    (dev / "local.go").write_text("package app\n\nfunc Local() {}\n")
    git(dev, "add", ".")
    git(dev, "commit", "-q", "-m", "wip")

    git(seed, "checkout", "-q", "-b", "feature/pushed-later")          # pushed after the dev's last fetch
    (seed / "x.go").write_text("package app\n\nfunc X() {}\n")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "x")
    git(seed, "push", "-q", "origin", "feature/pushed-later")
    return tmp_path, origin, dev


def refs(repo: Path) -> str:
    return git(repo, "for-each-ref", "--format=%(refname) %(objectname)")


def test_sync_reads_the_workspace_and_fetches_the_remote_into_the_mirror(world):
    tmp, origin, dev = world
    before = refs(dev)
    mirror = mirror_path(tmp / "mirrors", "acme", "orders-api")
    ok, msg = sync(dev, mirror, remote=True)
    assert ok, msg
    names = {b["name"] for b in list_branches(mirror)}
    assert {"main", "feature/pushed-later"} <= names            # the team's view, not the dev's last fetch
    assert branch_sha(mirror, "feature/local-only")              # unpushed: still indexable on demand
    assert default_ref(mirror) == "main"
    # the developer's repo is untouched: same refs, no FETCH_HEAD
    assert refs(dev) == before
    assert not (dev / ".git" / "FETCH_HEAD").exists()


def test_sync_without_remote_follows_the_developer(world):
    tmp, origin, dev = world
    mirror = mirror_path(tmp / "mirrors", "acme", "orders-api")
    ok, msg = sync(dev, mirror, remote=False)
    assert not ok and "local only" in msg
    names = {b["name"] for b in list_branches(mirror)}
    assert "main" in names and "feature/pushed-later" not in names
    # a later sync with the remote prunes nothing the developer has and adds what was pushed
    ok, _ = sync(dev, mirror, remote=True)
    assert ok and "feature/pushed-later" in {b["name"] for b in list_branches(mirror)}
    assert branch_sha(mirror, "feature/local-only")


def test_ssh_remote_without_token_is_not_fetched(world, monkeypatch):
    tmp, origin, dev = world
    for k in [k for k in __import__("os").environ if k.startswith("AIDD_GIT_TOKEN")]:
        monkeypatch.delenv(k)
    git(dev, "remote", "set-url", "origin", "git@github.com:acme/orders-api.git")
    ok, msg = sync(dev, mirror_path(tmp / "m", "acme", "orders-api"), remote=True)
    assert not ok and "no service token" in msg                 # no network attempt, no ssh prompt


def test_https_rewrite_for_ssh_remotes():
    assert https_rewrite("git@github.com:acme/x.git") == [
        "-c", "url.https://github.com/.insteadOf=git@github.com:", "-c", "url.https://github.com/.insteadOf=ssh://git@github.com/"]
    assert https_rewrite("ssh://git@gitlab.com/acme/x.git")[1] == "url.https://gitlab.com/.insteadOf=git@gitlab.com:"
    assert https_rewrite("https://github.com/acme/x.git") == []


def test_planner_reads_mirrors_when_configured(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    manifest = tmp / "atlas.yaml"
    manifest.write_text(f"""
tenants:
  acme:
    sources:
      - type: local
        path: {tmp / 'workspace' / 'acme'}
        fetch: true
    refs:
      always: [main]
      active: {{max_age_days: 3650, max_per_repo: 5}}
""")
    tenant = load_manifest(str(manifest)).tenant("acme")
    plan = build_plan(tenant)
    assert {it.repo.path for it in plan.items} == {tmp / "mirrors" / "acme" / "orders-api.git"}
    assert {it.ref for it in plan.items} == {"main", "feature/pushed-later"}     # remote view; local-only is on demand
    assert all(it.repo.url == str(origin) for it in plan.items)
    assert not (dev / ".git" / "FETCH_HEAD").exists()


def test_a_repo_that_cannot_be_mirrored_is_an_error_not_a_note(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    broken = tmp / "workspace" / "acme" / "broken-api"
    (broken / ".git").mkdir(parents=True)              # looks like a repo, git cannot read it
    manifest = tmp / "atlas.yaml"
    manifest.write_text(f"""
tenants:
  acme:
    sources:
      - type: local
        path: {tmp / 'workspace' / 'acme'}
    refs:
      always: [main]
""")
    plan = build_plan(load_manifest(str(manifest)).tenant("acme"), do_fetch=False)
    assert [e.split(":")[0] for e in plan.errors] == ["broken-api"]
    assert {it.repo.name for it in plan.items} == {"orders-api"}


def test_a_requested_repo_that_is_not_there_is_an_error(world, monkeypatch):
    tmp, origin, dev = world
    monkeypatch.setenv("AIDD_MIRROR_DIR", str(tmp / "mirrors"))
    manifest = tmp / "atlas.yaml"
    manifest.write_text(f"""
tenants:
  acme:
    sources:
      - type: local
        path: {tmp / 'workspace' / 'acme'}
        exclude: ["orders-api"]
    refs:
      always: [main]
""")
    plan = build_plan(load_manifest(str(manifest)).tenant("acme"), only_repos=["orders-api"], do_fetch=False)
    assert plan.items == [] and "excluded in atlas.yaml" in plan.errors[0]
    assert not (tmp / "mirrors" / "acme" / "orders-api.git").exists()      # filtered before any sync
