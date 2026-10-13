"""Turn the manifest into a concrete plan: which (repo, ref, sha) to index and why.

Sources yield repos; the ref policy picks refs per repo:
  always   -> listed names that exist (main/master/develop by default)
  patterns -> globs (release/*)
  active   -> not merged into the default branch, committed within N days,
              not excluded, capped at K per repo, flagged ephemeral
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ConfigError
from .gitinfo import default_ref, fetch, has_git, is_merged_into, list_branches, remote_url
from .manifest import Source, TenantConfig
from .mirror import mirror_path, mirror_root, sync


@dataclass
class RepoCandidate:
    name: str
    path: Path                 # local checkout (or mirror) to read from
    source: str                # local | github | ...
    url: str = ""
    default_ref: str = ""
    area: str | None = None
    remote: str | None = None  # last fetch from the git remote: "ok", the failure, or None (not attempted)


@dataclass
class PlanItem:
    repo: RepoCandidate
    ref: str
    sha: str
    reason: str                # always | pattern:<glob> | active:<age>d
    ephemeral: bool


@dataclass
class Plan:
    tenant: str
    items: list[PlanItem] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # human-readable notes (no git, no refs, ...)
    errors: list[str] = field(default_factory=list)    # repos that could not be read at all (the run fails)

    def repos(self) -> list[RepoCandidate]:
        seen: dict[str, RepoCandidate] = {}
        for it in self.items:
            seen.setdefault(it.repo.name, it.repo)
        return list(seen.values())

    def by_area(self) -> dict[str, list[PlanItem]]:
        out: dict[str, list[PlanItem]] = {}
        for it in self.items:
            out.setdefault(it.repo.area or "(no area)", []).append(it)
        return dict(sorted(out.items(), key=lambda kv: (kv[0] == "(no area)", kv[0])))


# -- sources -------------------------------------------------------------------------------

def discover_local(source: Source, tenant: TenantConfig) -> list[RepoCandidate]:
    root = Path(source.path)
    if not root.is_dir():
        raise ConfigError(f"local source path does not exist: {root} (inside the container WORKSPACE_PATH is /workspace)")
    repos: list[RepoCandidate] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / ".git").exists():
            continue
        if not source.selects(child.name):
            continue
        repos.append(RepoCandidate(name=child.name, path=child, source="local", area=tenant.area_of(child.name)))
    return repos


def discover_repos(tenant: TenantConfig, do_fetch: bool = True, progress=None,
                   errors: list[str] | None = None,
                   only: set[str] | None = None) -> tuple[list[RepoCandidate], list[str]]:
    """Repos from every source. For local sources with `fetch: true` (default) the
    remote-tracking refs are refreshed first — the atlas must see what the team pushed,
    not what one developer last fetched. A failed fetch is a note, not an error.

    With `$AIDD_MIRROR_DIR` set (the refresher service) the workspace is only read: each repo is
    synced into its own mirror (core/mirror.py) and planned from there; `fetch` then governs the
    remote half of that sync."""
    repos: dict[str, RepoCandidate] = {}
    notes: list[str] = []
    mroot = mirror_root()
    for s in tenant.sources:
        if s.type == "local":
            found = [r for r in discover_local(s, tenant) if not only or r.name in only]   # before any sync/fetch
            if mroot is not None:
                kept = []
                for r in found:
                    if progress:
                        progress(f"[mirror] {r.name}")
                    mp = mirror_path(mroot, tenant.name, r.name)
                    try:
                        ok, msg = sync(r.path, mp, remote=do_fetch and s.fetch)
                    except RuntimeError as e:
                        (errors if errors is not None else notes).append(f"{r.name}: {e} — skipped")
                        continue
                    if do_fetch and s.fetch:
                        r.remote = "ok" if ok else msg
                        if not ok:
                            notes.append(f"{r.name}: {msg}")
                    r.url = remote_url(r.path)
                    r.path = mp
                    kept.append(r)
                found = kept
            elif do_fetch and s.fetch:
                for r in found:
                    if progress:
                        progress(f"[fetch] {r.name}")
                    ok, msg = fetch(r.path)
                    r.remote = "ok" if ok else f"git fetch failed ({msg}) — planned on local refs"
                    if not ok:
                        notes.append(f"{r.name}: {r.remote}")
            for r in found:
                repos.setdefault(r.name, r)
        else:
            notes.append(f"source '{s.type}' (org {s.org}) not implemented yet (remote providers); skipped")
    return list(repos.values()), notes


# -- ref policy ----------------------------------------------------------------------------

def plan_refs(repo: RepoCandidate, tenant: TenantConfig, now: datetime | None = None) -> tuple[list[PlanItem], str | None]:
    now = now or datetime.now(timezone.utc)
    if not has_git(repo.path):
        return [], f"{repo.name}: not a git repository"
    branches = list_branches(repo.path)
    if not branches:
        return [], f"{repo.name}: no branches found"
    repo.url = repo.url or remote_url(repo.path)
    repo.default_ref = repo.default_ref or default_ref(repo.path)
    by_name = {b["name"]: b for b in branches}
    pol = tenant.refs.for_repo(repo.name)
    items: list[PlanItem] = []
    taken: set[str] = set()

    for name in pol.always:
        b = by_name.get(name)
        if b and name not in taken:
            items.append(PlanItem(repo, name, b["sha"], "always", False))
            taken.add(name)

    for glob in pol.patterns:
        for b in branches:
            if b["name"] not in taken and fnmatch.fnmatch(b["name"], glob):
                items.append(PlanItem(repo, b["name"], b["sha"], f"pattern:{glob}", False))
                taken.add(b["name"])

    base = by_name.get(repo.default_ref) or (by_name.get(pol.always[0]) if pol.always else None)
    cutoff = now - timedelta(days=pol.active.max_age_days)
    active = 0
    for b in branches:  # already sorted by committerdate desc
        if active >= pol.active.max_per_repo:
            break
        if b["name"] in taken or any(fnmatch.fnmatch(b["name"], g) for g in pol.active.exclude):
            continue
        try:
            committed = datetime.fromisoformat(b["committed_at"])
        except ValueError:
            continue
        if committed < cutoff:
            break  # sorted desc: everything after is older
        if base and is_merged_into(repo.path, b["sha"], base["sha"]):
            continue
        age = (now - committed).days
        items.append(PlanItem(repo, b["name"], b["sha"], f"active:{age}d", True))
        taken.add(b["name"])
        active += 1

    return items, (None if items else f"{repo.name}: no ref matched the policy")


def build_plan(tenant: TenantConfig, only_repos: list[str] | None = None,
               do_fetch: bool = True, progress=None) -> Plan:
    plan = Plan(tenant=tenant.name)
    repos, notes = discover_repos(tenant, do_fetch=do_fetch, progress=progress, errors=plan.errors,
                                  only=set(only_repos) if only_repos else None)
    plan.skipped.extend(notes)
    if only_repos:
        wanted = set(only_repos)
        unreadable = {e.split(":", 1)[0] for e in plan.errors}       # found, but the mirror sync failed
        missing = wanted - {r.name for r in repos} - unreadable
        if missing:
            # asked for by name (refresh --repos): not finding it is an error, not a footnote
            plan.errors.append(f"requested but not found in any source of tenant '{tenant.name}' "
                               f"(not cloned under it, or excluded in atlas.yaml): {', '.join(sorted(missing))}")
        repos = [r for r in repos if r.name in wanted]
    for r in repos:
        items, note = plan_refs(r, tenant)
        plan.items.extend(items)
        if note:
            plan.skipped.append(note)
    return plan


def render_plan(plan: Plan, stale: dict[tuple[str, str], str] | None = None) -> str:
    """Text table. `stale` = {(repo, ref): indexed_sha} lets us mark up-to-date items."""
    lines: list[str] = []
    total = len(plan.items)
    lines.append(f"tenant: {plan.tenant} — {len(plan.repos())} repos, {total} snapshots to index")
    for area, items in plan.by_area().items():
        lines.append(f"\n[{area}]")
        current_repo = None
        for it in items:
            if it.repo.name != current_repo:
                current_repo = it.repo.name
                lines.append(f"  {it.repo.name}  (default: {it.repo.default_ref or '?'})")
            state = ""
            if stale is not None:
                indexed = stale.get((it.repo.name, it.ref))
                if indexed == it.sha:
                    state = "  [up to date]"
                elif indexed == "":
                    state = "  [reindex: older indexer]"
                else:
                    state = "  [changed]" if indexed else "  [new]"
            eph = "  ephemeral" if it.ephemeral else ""
            lines.append(f"    - {it.ref:<40} {it.sha[:10]}  {it.reason:<14}{eph}{state}")
    if plan.errors:
        lines.append("\nerrors (not indexed):")
        lines += [f"  - {s}" for s in plan.errors]
    if plan.skipped:
        lines.append("\nskipped:")
        lines += [f"  - {s}" for s in plan.skipped]
    return "\n".join(lines)
