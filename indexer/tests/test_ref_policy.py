"""The ref policy as `plan_refs` applies it: `always`, then `patterns`, then the active branches, one repo at a time.

The branches, their dates and what is merged are given, so each rule is checked on its own; one case runs real git."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aidd_indexer.core import planner
from aidd_indexer.core.manifest import ActivePolicy, RefPolicy, TenantConfig
from aidd_indexer.core.planner import RepoCandidate, plan_refs

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def branch(name: str, days: float, sha: str | None = None) -> dict:
    return {"name": name, "sha": sha or f"{name}-sha", "committed_at": (NOW - timedelta(days=days)).isoformat(),
            "remote": True}


def tenant(**refs) -> TenantConfig:
    return TenantConfig(name="acme", sources=[], refs=RefPolicy(**refs))


@pytest.fixture()
def repo(monkeypatch):
    """A repo whose branches are `repo.branches`; `repo.merged` holds the shas merged into the base."""
    r = RepoCandidate(name="orders-api", path=Path("/nowhere"), source="local")
    r.branches, r.merged, r.merge_checks = [], set(), []
    monkeypatch.setattr(planner, "has_git", lambda path: True)
    monkeypatch.setattr(planner, "list_branches", lambda path: list(r.branches))
    monkeypatch.setattr(planner, "remote_url", lambda path: "https://example.test/orders-api.git")
    monkeypatch.setattr(planner, "default_ref", lambda path: "main")

    def merged(path, sha, base_sha):
        r.merge_checks.append((sha, base_sha))
        return sha in r.merged
    monkeypatch.setattr(planner, "is_merged_into", merged)
    return r


def picked(items) -> list[tuple[str, str, bool]]:
    return [(it.ref, it.reason, it.ephemeral) for it in items]


def test_always_takes_the_listed_names_that_exist_in_the_policy_order_once(repo):
    repo.branches = [branch("main", 0.5), branch("master", 100)]
    items, note = plan_refs(repo, tenant(always=["main", "main", "develop", "master"],
                                         active=ActivePolicy(max_per_repo=0)), NOW)
    assert picked(items) == [("main", "always", False), ("master", "always", False)]
    assert [it.sha for it in items] == ["main-sha", "master-sha"] and note is None


def test_patterns_go_glob_by_glob_and_skip_what_is_taken(repo):
    repo.branches = [branch("release/2.0", 1), branch("main", 2), branch("hotfix/x", 3), branch("release/1.0", 4)]
    items, _ = plan_refs(repo, tenant(always=["main"], patterns=["release/*", "hotfix/*", "release/1.*", "m*"],
                                      active=ActivePolicy(max_per_repo=0)), NOW)
    assert picked(items) == [("main", "always", False), ("release/2.0", "pattern:release/*", False),
                             ("release/1.0", "pattern:release/*", False), ("hotfix/x", "pattern:hotfix/*", False)]


def test_active_branches_newest_first_skipping_excluded_merged_and_undated_until_one_is_too_old(repo):
    repo.branches = [branch("dependabot/npm", 0.2), branch("feature/new", 1), branch("feature/merged", 2),
                     {"name": "feature/undated", "sha": "u", "committed_at": "yesterday", "remote": True},
                     branch("feature/ten", 10), branch("main", 11), branch("feature/old", 20),
                     branch("feature/listed-after-old", 3)]
    repo.merged = {"feature/merged-sha"}
    items, _ = plan_refs(repo, tenant(always=["main"]), NOW)
    assert picked(items) == [("main", "always", False), ("feature/new", "active:1d", True),
                             ("feature/ten", "active:10d", True)]
    assert repo.merge_checks == [("feature/new-sha", "main-sha"), ("feature/merged-sha", "main-sha"),
                                 ("feature/ten-sha", "main-sha")]


def test_the_limit_counts_only_what_is_taken(repo):
    repo.branches = [branch("docs/readme", 0.5)] + [branch(f"feature/{n}", n) for n in range(1, 5)]
    items, _ = plan_refs(repo, tenant(always=[], active=ActivePolicy(max_per_repo=2)), NOW)
    assert picked(items) == [("feature/1", "active:1d", True), ("feature/2", "active:2d", True)]


def test_an_override_without_active_branches_keeps_only_the_named_refs(repo):
    repo.name = "legacy-billing"
    repo.branches = [branch("feature/a", 1), branch("master", 2)]
    items, _ = plan_refs(repo, tenant(always=["main"], overrides={"legacy-*": {"always": ["master"], "active": False}}),
                         NOW)
    assert picked(items) == [("master", "always", False)]


def test_the_base_falls_back_to_the_first_always_name_and_without_one_nothing_is_merged(repo):
    repo.default_ref = "trunk"
    repo.branches = [branch("feature/a", 1), branch("develop", 2)]
    repo.merged = {"feature/a-sha"}
    items, _ = plan_refs(repo, tenant(always=["develop"]), NOW)
    assert picked(items) == [("develop", "always", False)]
    assert repo.merge_checks == [("feature/a-sha", "develop-sha")]

    repo.merge_checks = []
    items, _ = plan_refs(repo, tenant(always=[]), NOW)
    assert picked(items) == [("feature/a", "active:1d", True), ("develop", "active:2d", True)]
    assert repo.merge_checks == []


def test_the_notes_when_nothing_is_planned(repo, monkeypatch):
    assert plan_refs(repo, tenant(always=["main"]), NOW) == ([], "orders-api: no branches found")
    repo.branches = [branch("feature/a", 30)]
    assert plan_refs(repo, tenant(always=["main"]), NOW) == ([], "orders-api: no ref matched the policy")
    monkeypatch.setattr(planner, "has_git", lambda path: False)
    assert plan_refs(repo, tenant(always=["main"]), NOW) == ([], "orders-api: not a git repository")


def test_url_and_default_ref_are_filled_only_when_empty(repo):
    repo.branches = [branch("main", 1)]
    plan_refs(repo, tenant(always=["main"]), NOW)
    assert (repo.url, repo.default_ref) == ("https://example.test/orders-api.git", "main")
    repo.url, repo.default_ref = "kept", "kept-ref"
    plan_refs(repo, tenant(always=["main"]), NOW)
    assert (repo.url, repo.default_ref) == ("kept", "kept-ref")


def _git(cwd: Path, *args: str, days: int = 0) -> None:
    when = (NOW - timedelta(days=days)).isoformat()
    subprocess.run(["git", "-c", "safe.directory=*", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@x", "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
                        "HOME": str(cwd)})


def test_on_a_real_repository(tmp_path: Path):
    r = tmp_path / "orders-api"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "commit", "-q", "--allow-empty", "-m", "a", days=9)
    _git(r, "checkout", "-q", "-b", "feature/merged")
    _git(r, "commit", "-q", "--allow-empty", "-m", "b", days=8)
    _git(r, "checkout", "-q", "main")
    _git(r, "merge", "-q", "--no-ff", "-m", "m", "feature/merged", days=7)
    _git(r, "checkout", "-q", "-b", "feature/open")
    _git(r, "commit", "-q", "--allow-empty", "-m", "c", days=3)
    _git(r, "checkout", "-q", "-b", "release/1.0", "main")
    items, note = plan_refs(RepoCandidate(name="orders-api", path=r, source="local"),
                            tenant(always=["main"], patterns=["release/*"]), NOW)
    assert picked(items) == [("main", "always", False), ("release/1.0", "pattern:release/*", False),
                             ("feature/open", "active:3d", True)]
    assert note is None
