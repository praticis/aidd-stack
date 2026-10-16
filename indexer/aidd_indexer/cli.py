"""`aidd` command line.

  aidd plan      [--tenant T] [--repos a,b] [--config FILE]           what would be indexed, and why
  aidd bootstrap [--tenant T] [--repos a,b] [--yes] [--config FILE]   index everything the plan lists
  aidd refresh   [--tenant T [--repos a,b]] [--wait S] [--config FILE]  re-index only what changed + GC (every tenant)
  aidd daemon    [--config FILE]                                       refresh every AIDD_REFRESH_INTERVAL_MINUTES (service)
  aidd daemon-health                                                   exit 0 when the refresher is alive (healthcheck)
  aidd index <repo|path> [--ref REF] [--tenant T] [--ephemeral] [--dry-run [--out FILE]]
  aidd status    [--tenant T]
  aidd wipe <repo> [--ref REF] [--tenant T]

Manifest: $AIDD_CONFIG (atlas.yaml). <repo> for `index` is resolved under $WORKSPACE_PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import INDEXER_VERSION
from . import conventions, daemon, languages
from .core.config import ConfigError, Neo4jConfig, resolve_repo, resolve_tenant
from .core.deps import collect_manifest_deps
from .core.dispatch import call_names
from .core.discovery import build_files, discover_modules, list_files
from .core.extract import GRAMMAR_ERRORS, extract_file, load_language
from .core.gitinfo import branch_sha, current_ref, default_ref, export_tree, fetch, head_sha, is_git_repo, list_branches, remote_url
from .core.mirror import mirror_path, mirror_root, sync as sync_mirror
from .core.model import ExtractionResult, RepoInfo
from .core.resolve import Resolved, Resolver


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class GrammarError(RuntimeError):
    """A supported language's grammar failed to load — the environment is broken."""


# who started this run — recorded on every IndexRun (manual | scheduled | bootstrap)
TRIGGER = os.getenv("AIDD_TRIGGER", "manual")


# -- core: extract + resolve one tree -------------------------------------------------------

def extract_tree(repo: RepoInfo, patterns=None, dispatch_calls: frozenset[str] = frozenset()) -> tuple[ExtractionResult, list]:
    t0 = time.time()
    rel_files = list_files(Path(repo.root))
    modules, stack = discover_modules(repo, rel_files)
    repo.stack = sorted(stack)
    files = build_files(repo, rel_files, modules)
    res = ExtractionResult(repo=repo, modules=modules, files=files)
    res.provides, res.requires = collect_manifest_deps(repo, rel_files)
    log(f"[discover] {len(rel_files)} files, {len(files)} recorded, {len(modules)} modules, stack={repo.stack} ({time.time()-t0:.1f}s)")

    missing = []
    for lang in sorted({f.language for f in files} & languages.parseable()):
        cl = load_language(lang)
        if cl:
            res.warnings.extend(cl.warnings)
        else:
            missing.append(lang)
    if missing:
        # A supported language we cannot parse means the snapshot would be silently empty.
        # That is an installation defect, not a property of the repo — fail loudly.
        details = "; ".join(f"{l}: {GRAMMAR_ERRORS.get(l, 'unknown error')}" for l in missing)
        raise GrammarError(f"cannot load tree-sitter grammar(s) for {', '.join(missing)} — {details}. "
                           "Run `aidd selftest`; rebuild the indexer image if it fails.")

    extractors = []
    t0 = time.time()
    for f in files:
        if f.language not in languages.parseable():
            continue
        fx, warns = extract_file(repo, f, dispatch_calls)
        res.warnings.extend(warns)
        if fx is None:
            continue
        extractors.append(fx)
        res.symbols.extend(fx.symbols)
        res.calls.extend(fx.calls)
        res.imports.extend(fx.imports)
    log(f"[extract]  {len(res.symbols)} symbols, {len(res.calls)} call sites, {len(res.imports)} imports ({time.time()-t0:.1f}s)")
    # integration candidates: routes exposed + outbound HTTP calls with literal paths
    from .core.integrations import extract_http
    t1 = time.time()
    hr = extract_http(repo, extractors, patterns, modules)
    res.endpoints, res.http_calls = hr.endpoints, hr.calls
    res.warnings.extend(hr.warnings)
    resolved = sum(1 for e in hr.endpoints if e.handler_id)
    log(f"[http]     {len(hr.endpoints)} endpoints exposed ({resolved} with handler), {len(hr.calls)} outbound calls ({time.time()-t1:.1f}s)")
    return res, extractors


def conventions_for(tenant: str, repo_name: str, config: str | None = None) -> list:
    """Conventions declared for this tenant in atlas.yaml (+ AIDD_CONVENTIONS=path,path for ad-hoc runs)."""
    specs: list = [p for p in os.getenv("AIDD_CONVENTIONS", "").split(",") if p.strip()]
    try:
        from .core.manifest import load_manifest
        tc = load_manifest(config).tenants.get(tenant)
        if tc:
            specs += tc.conventions
    except ConfigError:
        pass                                    # no manifest (plain `aidd index` outside the container) — fine
    return conventions.load(specs, repo_name)


def extract_and_resolve(repo: RepoInfo, convs: list | None = None) -> tuple[ExtractionResult, Resolved]:
    if convs is None:
        convs = conventions_for(repo.tenant, repo.name)
    rules = conventions.dispatch_rules(convs)
    res, extractors = extract_tree(repo, conventions.scan_patterns(convs), call_names(rules))
    rv = Resolver(res, extractors, rules).run()
    log(f"[resolve]  {len(rv.calls)} CALLS edges ({rv.unresolved_calls} unresolved call sites), "
        f"{len(rv.imports)} IMPORTS edges ({rv.unresolved_imports} unresolved), {len(rv.packages)} external packages")
    if convs:
        t0 = time.time()
        conventions.apply(convs, res, rv)
        layered = sum(1 for f in res.files if f.layer)
        log(f"[conv]     {', '.join(c.describe() for c in convs)}: {layered} files layered, "
            f"{len(res.violations)} violations ({time.time()-t0:.1f}s)")
    for w in res.warnings[:10]:
        log(f"[warn]     {w}")
    if len(res.warnings) > 10:
        log(f"[warn]     ... {len(res.warnings) - 10} more")
    return res, rv


def repo_info_for_checkout(repo_path: Path, tenant: str, ref_label: str | None) -> RepoInfo:
    """RepoInfo for indexing the working tree as-is (whatever is checked out)."""
    git = is_git_repo(repo_path)
    return RepoInfo(
        tenant=tenant, name=repo_path.name,
        ref=ref_label or (current_ref(repo_path) if git else "workdir"),
        commit_sha=head_sha(repo_path) if git else "workdir",
        root=str(repo_path),
        default_ref=default_ref(repo_path) if git else "workdir",
        url=remote_url(repo_path) if git else "",
    )


def index_exported_ref(gw, repo_path: Path, name: str, tenant: str, ref: str, sha: str,
                       ephemeral: bool, url: str, default: str, area: str | None) -> dict:
    """Index a specific commit without touching the checkout: git archive -> temp dir -> index."""
    started = datetime.now(timezone.utc)
    tmp = Path(tempfile.mkdtemp(prefix=f"aidd-{name}-"))
    try:
        if not export_tree(repo_path, sha, tmp):
            raise ConfigError(f"{name}@{ref}: git archive of {sha[:10]} failed (is the ref fetched locally?)")
        repo = RepoInfo(tenant=tenant, name=name, ref=ref, commit_sha=sha, root=str(tmp), default_ref=default, url=url)
        res, rv = extract_and_resolve(repo)
        t0 = time.time()
        counts = gw.write(res, rv, started, ephemeral=ephemeral, area=area, trigger=TRIGGER)
        log(f"[write]    {name}@{ref} {json.dumps(counts)} ({time.time()-t0:.1f}s)")
        return counts
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def open_graph():
    from .core.graph import GraphWriter  # lazy: dry-run / plan must work without a database
    cfg = Neo4jConfig.from_env()
    gw = GraphWriter(cfg)
    gw.verify()
    return gw, cfg


# -- commands --------------------------------------------------------------------------------

def cmd_index(args: argparse.Namespace) -> int:
    repo_path = resolve_repo(args.repo)
    tenant = resolve_tenant(repo_path, args.tenant)
    log(f"[aidd {INDEXER_VERSION}] repo={repo_path} tenant={tenant}")

    # --ref that differs from the checkout: index that ref via git archive
    if args.ref and is_git_repo(repo_path) and args.ref != current_ref(repo_path) and not args.dry_run:
        url = remote_url(repo_path)
        git_dir = repo_path
        mroot = mirror_root()
        if mroot is not None:          # refresher service: read the workspace, write only the mirror
            git_dir = mirror_path(mroot, tenant, repo_path.name)
            ok, msg = sync_mirror(repo_path, git_dir, remote=not args.no_fetch)
            log(f"[mirror]   {repo_path.name}: {msg}")
        elif not args.no_fetch:
            ok, msg = fetch(repo_path)
            log(f"[fetch]    {repo_path.name}: {msg}" + ("" if ok else " — using local refs"))
        sha = branch_sha(git_dir, args.ref)
        if not sha:
            known = sorted(b["name"] for b in list_branches(git_dir))
            raise ConfigError(f"ref '{args.ref}' not found in {repo_path.name} (known: {', '.join(known[:15])}...)")
        gw, cfg = open_graph()
        try:
            index_exported_ref(gw, git_dir, repo_path.name, tenant, args.ref, sha,
                               args.ephemeral, url, default_ref(git_dir), None)
            _link(gw, tenant)
        finally:
            gw.close()
        return 0

    started = datetime.now(timezone.utc)
    repo = repo_info_for_checkout(repo_path, tenant, args.ref)
    res, rv = extract_and_resolve(repo)

    if args.dry_run:
        payload = {
            "repo": asdict(res.repo),
            "counts": res.counts() | {"calls_edges": len(rv.calls), "imports_edges": len(rv.imports), "packages": len(rv.packages)},
            "modules": [asdict(m) for m in res.modules],
            "files": [asdict(f) for f in res.files],
            "symbols": [asdict(s) for s in res.symbols],
            "calls": [asdict(c) for c in rv.calls],
            "imports": [asdict(i) for i in rv.imports],
            "packages": [asdict(p) for p in rv.packages.values()],
            "endpoints": [asdict(e) for e in res.endpoints],
            "http_calls": [asdict(c) for c in res.http_calls],
            "violations": [asdict(v) for v in res.violations],
            "provides": [asdict(p) for p in res.provides],
            "requires": [asdict(d) for d in res.requires],
            "warnings": res.warnings,
        }
        if args.out:
            Path(args.out).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            log(f"[dry-run]  wrote {args.out}")
        else:
            print(json.dumps(payload["counts"], indent=2))
        return 0

    gw, cfg = open_graph()
    try:
        t0 = time.time()
        counts = gw.write(res, rv, started, ephemeral=args.ephemeral, trigger=TRIGGER)
        log(f"[write]    {json.dumps(counts)} ({time.time()-t0:.1f}s) → {cfg.uri}/{cfg.database}")
        _link(gw, tenant)
    finally:
        gw.close()
    return 0


def _link(gw, tenant: str) -> None:
    """Rebuild the tenant's CONSUMES / CALLED_FROM and DEPENDS_ON edges — after any snapshot changes."""
    t0 = time.time()
    c = gw.link_tenant(tenant)
    log(f"[link]     {tenant}: {c['linked']} call sites linked ({c['exact']} exact, {c['suffix']} suffix, "
        f"{c['by_hint']} by hint), {c['ambiguous']} ambiguous, {c['unmatched']} unmatched "
        f"of {c['calls']} calls × {c['endpoints']} endpoints; {c['depends_on']} DEPENDS_ON edges "
        f"from {c['deps_packages']} internal packages ({c['deps_ambiguous']} ambiguous) ({time.time()-t0:.1f}s)")


def _load_plan(args: argparse.Namespace, tenant_name: str | None = None):
    from .core.manifest import load_manifest
    from .core.planner import build_plan
    manifest = load_manifest(args.config)
    tenant = manifest.tenant(tenant_name or args.tenant)
    only = [r.strip() for r in args.repos.split(",")] if getattr(args, "repos", None) else None
    do_fetch = not getattr(args, "no_fetch", False)
    if do_fetch:
        log("[fetch] " + ("syncing mirrors and fetching the remotes" if mirror_root() else
                          "refreshing remote-tracking refs (git fetch --all --prune)") + " — use --no-fetch to skip")
    return tenant, build_plan(tenant, only, do_fetch=do_fetch, progress=log)


def cmd_plan(args: argparse.Namespace) -> int:
    from .core.planner import render_plan
    tenant, plan = _load_plan(args)
    stale = None
    if not args.offline:
        try:
            gw, _ = open_graph()
            try:
                stale = gw.snapshot_shas(tenant.name)
            finally:
                gw.close()
        except Exception as e:  # noqa: BLE001 — plan must still work without the database
            log(f"[plan] database unavailable ({type(e).__name__}); showing plan without index state")
    print(render_plan(plan, stale))
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    from .core.planner import render_plan
    tenant, plan = _load_plan(args)
    if not plan.items:
        log("nothing to index — check sources in the manifest")
        return 1
    gw, cfg = open_graph()
    try:
        if not args.quiet_plan:
            print(render_plan(plan, gw.snapshot_shas(tenant.name)))
        if not args.yes:
            if not sys.stdin.isatty():
                log(f"\nno interactive terminal to confirm indexing {len(plan.items)} snapshots — re-run with --yes")
                return 1
            try:
                answer = input(f"\nIndex {len(plan.items)} snapshots into {cfg.database}? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                log("aborted — nothing was written (use --yes to skip this prompt)")
                return 1
        global TRIGGER
        TRIGGER = "bootstrap" if TRIGGER == "manual" else TRIGGER
        started = datetime.now(timezone.utc).isoformat()
        try:
            with daemon.refresh_lock():
                rc = _run_items(gw, tenant, plan.items, skip_up_to_date=False)
                _link(gw, tenant.name)
        except daemon.Busy as e:
            log(f"[bootstrap] {e} — wait for it (aidd logs) and run again")
            return 1
        gw.heartbeat(tenant.name, started, datetime.now(timezone.utc).isoformat(), rc, TRIGGER,
                     daemon.interval_min(), len(plan.items))
        return rc
    finally:
        gw.close()


def cmd_refresh(args: argparse.Namespace) -> int:
    """Refresh one tenant (`--tenant`) or every tenant of the manifest, under the refresh lock.
    `--repos a,b` refreshes only those repos (on demand, e.g. the `scan` skill meeting a repo atlas does
    not have yet): no GC, and it does not count as the refresher's run (status.json, RefreshState)."""
    from .core.manifest import load_manifest
    names = [args.tenant] if args.tenant else list(load_manifest(args.config).tenants)
    if getattr(args, "repos", None) and len(names) > 1:
        raise ConfigError("--repos needs --tenant (repo names are only unique inside a tenant)")
    try:
        with daemon.refresh_lock(wait=getattr(args, "wait", 0) or 0):
            return _refresh_all(args, names)
    except daemon.Busy as e:
        log(f"[refresh] {e} — skipped")
        return 75 if getattr(args, "repos", None) else 0     # EX_TEMPFAIL: the caller asked for these repos


def _refresh_all(args: argparse.Namespace, names: list[str]) -> int:
    partial = bool(getattr(args, "repos", None))
    if not partial:
        daemon.mark_start(TRIGGER)
    rc, summary = 0, {}
    try:
        gw, _ = open_graph()
        try:
            for name in names:
                if daemon.STOP.is_set():
                    break
                started = datetime.now(timezone.utc).isoformat()
                try:
                    r, info = _refresh_tenant(gw, args, name)
                except ConfigError as e:       # one tenant's broken source must not stop the others
                    log(f"[refresh] {name}: {e}")
                    r, info = 2, {"error": str(e)}
                rc = max(rc, r)
                summary[name] = info
                if not partial:
                    gw.heartbeat(name, started, datetime.now(timezone.utc).isoformat(), r, TRIGGER,
                                 daemon.interval_min(), int(info.get("changed", 0)))
        finally:
            gw.close()
    except Exception:
        rc = max(rc, 3)
        raise
    finally:
        if not partial:
            daemon.mark_end(rc, summary)
    return rc


def _refresh_tenant(gw, args: argparse.Namespace, tenant_name: str) -> tuple[int, dict]:
    log(f"\n[refresh] tenant {tenant_name}")
    tenant, plan = _load_plan(args, tenant_name)
    indexed = gw.snapshot_shas(tenant.name)
    todo = [it for it in plan.items if indexed.get((it.repo.name, it.ref)) != it.sha]
    log(f"[refresh] {len(todo)} of {len(plan.items)} snapshots changed or new")
    rc = _run_items(gw, tenant, todo, skip_up_to_date=True) if todo else 0
    gone = 0
    if getattr(args, "repos", None):
        log("[refresh] partial refresh (--repos): ephemeral GC left to the full refresh")
    else:
        gone = gw.gc_ephemeral(tenant.name, tenant.refs.gc_ephemeral_after_days,
                               keep={(it.repo.name, it.ref) for it in plan.items})
        log(f"[refresh] ephemeral snapshots removed: {gone}")
    planned = {(it.repo.name, it.ref) for it in plan.items}
    planned_repos = {it.repo.name for it in plan.items}
    outside = sorted(k for k in gw.persistent_snapshots(tenant.name) if k not in planned and k[0] in planned_repos)
    if outside:
        log(f"[refresh] {len(outside)} persistent snapshot(s) outside the ref policy (kept — branch gone or refs changed): "
            + ", ".join(f"{r}@{ref}" for r, ref in outside[:10]) + (" …" if len(outside) > 10 else "")
            + f" — remove with: aidd wipe <repo> --ref <ref>")
    if todo or gone:
        _link(gw, tenant.name)
    gw.record_remote_sync(tenant.name, {r.name: r.remote for r in plan.repos() if r.remote is not None})
    for e in plan.errors:
        log(f"[error]    {e}")
    if plan.errors:
        rc = max(rc, 1)                # a repo that could not be read is a failed run, not a footnote
    return rc, {"snapshots": len(plan.items), "changed": len(todo), "gc": gone, "notes": plan.skipped[:20],
                "errors": plan.errors[:20]}


def _run_items(gw, tenant, items, skip_up_to_date: bool) -> int:
    ok = failed = 0
    t_all = time.time()
    for n, it in enumerate(items, 1):
        if daemon.STOP.is_set():
            log(f"[stop]     stopping before {it.repo.name}@{it.ref} — the next refresh picks it up")
            failed += 1
            break
        log(f"\n[{n}/{len(items)}] {it.repo.name}@{it.ref} ({it.reason})")
        try:
            index_exported_ref(gw, it.repo.path, it.repo.name, tenant.name, it.ref, it.sha,
                               it.ephemeral, it.repo.url, it.repo.default_ref, it.repo.area)
            ok += 1
        except GrammarError:
            raise                      # environment defect: stop instead of writing 26 empty snapshots
        except Exception as e:  # noqa: BLE001 — one repo must not stop the portfolio
            failed += 1
            log(f"[error]    {it.repo.name}@{it.ref}: {type(e).__name__}: {str(e).splitlines()[0]}")
            try:
                gw.record_failure(tenant.name, it.repo.name, it.ref, it.sha, str(e))
            except Exception:  # noqa: BLE001
                pass
    log(f"\n[done] {ok} indexed, {failed} failed ({time.time()-t_all:.0f}s)")
    return 0 if failed == 0 else 1


def cmd_daemon(args: argparse.Namespace) -> int:
    """The refresher service: `refresh` every tenant, sleep an interval (± 10 %), repeat. Errors are
    logged and retried on the next round (Neo4j restarting, a manifest being edited)."""
    daemon.install_signal_handlers()
    every = daemon.interval_min()
    log(f"[daemon] aidd {INDEXER_VERSION} refresher — every {every} min ± 10 %, state in {daemon.state_dir() or '(none)'}, "
        f"mirrors in {mirror_root() or '(workspace, no mirrors)'}")
    while not daemon.STOP.is_set():
        bad = daemon.unwritable_dirs([d for d in (daemon.state_dir(), mirror_root()) if d is not None])
        if bad:
            log(f"[daemon] cannot write {'; '.join(bad)} — running as uid {os.getuid()}. On the host the directories "
                f"must belong to the user in AIDD_UID (~/.aidd/.env): sudo chown -R $(id -u):$(id -g) ~/.aidd/mirrors ~/.aidd/state "
                f"— retrying next round")
        try:
            rc = cmd_refresh(args)
        except Exception as e:  # noqa: BLE001 — the loop outlives any single failure
            rc = 3
            log(f"[daemon] refresh failed: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
        delay = daemon.next_delay(every * 60)
        log(f"[daemon] rc={rc}; next refresh in {delay / 60:.1f} min")
        daemon.STOP.wait(delay)
    log("[daemon] stopped")
    return 0


def cmd_daemon_health(args: argparse.Namespace) -> int:
    ok, msg = daemon.health()
    print(msg)
    return 0 if ok else 1


def cmd_link(args: argparse.Namespace) -> int:
    """Rebuild CONSUMES / CALLED_FROM for one tenant (or every tenant of the manifest)."""
    from .core.manifest import load_manifest
    if args.tenant:
        tenants = [args.tenant]
    else:
        try:
            tenants = list(load_manifest(args.config).tenants)
        except ConfigError as e:
            raise ConfigError(f"{e} — or pass --tenant")
    gw, _ = open_graph()
    try:
        for t in tenants:
            _link(gw, t)
    finally:
        gw.close()
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Load every grammar and compile every query. Exit 1 on any failure."""
    import tree_sitter, tree_sitter_language_pack  # noqa: F401
    from importlib.metadata import version
    log(f"tree-sitter {version('tree-sitter')} · tree-sitter-language-pack {version('tree-sitter-language-pack')} · python {sys.version.split()[0]}")
    from .core.extract import GRAMMAR_OFFLINE
    log(f"grammar cache {tree_sitter_language_pack.cache_dir()} · cached: {', '.join(tree_sitter_language_pack.downloaded_languages()) or '(none)'}"
        f" · downloads {'forbidden (AIDD_GRAMMAR_OFFLINE)' if GRAMMAR_OFFLINE else 'allowed'}")
    bad = 0
    for lang in sorted(languages.parseable()):
        cl = load_language(lang)
        if cl is None:
            print(f"  [FAIL] {lang}: {GRAMMAR_ERRORS.get(lang, 'unknown error')}")
            bad += 1
            continue
        skipped = len(cl.warnings)
        print(f"  [OK]   {lang}: {len(cl.patterns)} query patterns" + (f", {skipped} skipped (grammar mismatch)" if skipped else ""))
        for w in cl.warnings:
            print(f"         - {w}")
    if bad:
        log(f"{bad} grammar(s) failed to load — the indexer would produce empty snapshots. Rebuild: docker compose --profile tools build --no-cache indexer")
        return 1
    log("all grammars loaded.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .mcp.server import serve
    log(f"atlas MCP · tenant={os.getenv('AIDD_TENANT', '?')} · neo4j={os.getenv('NEO4J_URI', '?')}/{os.getenv('NEO4J_DATABASE', '?')}")
    return serve(host=args.host, port=args.port)


def cmd_knowledge(args: argparse.Namespace) -> int:
    """The `knowledge` MCP server (project knowledge + process policy for the skills)."""
    from .knowledge.server import serve
    from .knowledge.vault import KnowledgeError
    log(f"knowledge MCP · tenant={os.getenv('AIDD_TENANT', '?')} · vault={os.getenv('AIDD_VAULT_DIR', '/vault')} · "
        f"qdrant={os.getenv('QDRANT_URL', '?')} · model={os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')}")
    try:
        return serve(host=args.host, port=args.port)
    except KnowledgeError as e:
        log(f"error: {e}")
        return 2


def cmd_policy(args: argparse.Namespace) -> int:
    """`policy check`: validate policy.yaml. `policy show [repo]`: the effective policy of a tenant (or one
    of its repos) and the layer each value came from — what the skills receive."""
    from .core.manifest import load_manifest
    from .core.policy import load_policy
    pol = load_policy(args.policy)
    if args.action == "check":
        where = str(pol.path) if pol.path else "no policy.yaml (built-in defaults)"
        log(f"policy OK — {where}; tenants: {', '.join(pol.tenants) or '(none: defaults apply to every tenant)'}")
        return 0
    try:
        manifest = load_manifest(args.config)
    except ConfigError:
        manifest = None                     # the policy does not need atlas.yaml; only areas come from it
    tenant = args.tenant or (os.getenv("AIDD_TENANT", "").strip() if os.getenv("AIDD_TENANT", "").strip() != "auto" else "")
    if not tenant and manifest is not None:
        tenant = manifest.tenant(None).name           # one tenant declared, or an error asking for --tenant
    if not tenant:
        raise ConfigError("which tenant? pass --tenant (AIDD_TENANT is 'auto' or unset)")
    area = None
    if args.repo and manifest is not None and tenant in manifest.tenants:
        area = manifest.tenants[tenant].area_of(args.repo)
    eff = pol.effective(tenant, args.repo, area)
    if args.json:
        print(json.dumps(eff.as_dict(), indent=2))
        return 0
    scope = f"{tenant}/{args.repo}" if args.repo else tenant
    log(f"policy for {scope}" + (f" (area {area})" if area else "") + f" — {eff.path or 'no policy.yaml: built-in defaults'}")
    for section, keys in eff.values.items():
        for key, value in keys.items():
            shown = ", ".join(map(str, value)) if isinstance(value, list) else value
            print(f"  {section + '.' + key:<28} {str(shown):<44} {eff.origin.get(section + '.' + key, 'built-in')}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    gw, _ = open_graph()
    try:
        rows = gw.status(args.tenant)
    finally:
        gw.close()
    if not rows:
        print("atlas is empty — nothing indexed yet.")
        return 0
    w = max(len(f"{r['tenant']}/{r['repo']}@{r['ref']}") for r in rows)
    oldest = 0
    for r in rows:
        key = f"{r['tenant']}/{r['repo']}@{r['ref']}"
        flags = ("ephemeral " if r.get("ephemeral") else "") + (r.get("status") or "")
        age = r.get("age_min")
        oldest = max(oldest, age or 0)
        age_s = "-" if age is None else (f"{age}m" if age < 120 else f"{age // 60}h" if age < 2880 else f"{age // 1440}d")
        print(f"{key:<{w}}  {r['sha'] or '-':<10}  age={age_s:<5} files={r['files']:<5} {flags:<12} {r.get('trigger') or '-':<9} {r['counts'] or ''}")
    print(f"\n{len(rows)} snapshots; oldest indexed {oldest} min ago")
    return 0


def cmd_wipe(args: argparse.Namespace) -> int:
    repo_path = None
    try:
        repo_path = resolve_repo(args.repo)
    except ConfigError:
        pass
    tenant = args.tenant or (resolve_tenant(repo_path, None) if repo_path else None)
    if not tenant:
        raise ConfigError("cannot derive tenant — pass --tenant")
    name = repo_path.name if repo_path else args.repo
    gw, _ = open_graph()
    try:
        n = gw.wipe(tenant, name, args.ref)
        log(f"[wipe] deleted {n} nodes for {tenant}/{name}" + (f"@{args.ref}" if args.ref else " (all refs)"))
        _link(gw, tenant)          # CONSUMES / CALLED_FROM / DEPENDS_ON of the wiped ref go with it
    finally:
        gw.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aidd", description="aidd-stack code graph indexer (atlas)")
    p.add_argument("--version", action="version", version=INDEXER_VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    def manifest_args(sp, repos=True):
        sp.add_argument("--tenant", help="tenant declared in the manifest (required when it declares several)")
        sp.add_argument("--config", help="manifest path (default: $AIDD_CONFIG or /app/atlas.yaml)")
        sp.add_argument("--no-fetch", action="store_true", help="do not run `git fetch --all --prune` before reading refs")
        if repos:
            sp.add_argument("--repos", help="comma-separated repo names to restrict the plan to")

    pl = sub.add_parser("plan", help="show what the manifest would index, and why")
    manifest_args(pl)
    pl.add_argument("--offline", action="store_true", help="do not query the database for current index state")
    pl.set_defaults(fn=cmd_plan)

    b = sub.add_parser("bootstrap", help="index every snapshot the plan lists")
    manifest_args(b)
    b.add_argument("--yes", "-y", action="store_true", help="do not ask for confirmation")
    b.add_argument("--quiet-plan", action="store_true", help="do not print the plan again (install.sh shows it first)")
    b.set_defaults(fn=cmd_bootstrap)

    r = sub.add_parser("refresh", help="re-index snapshots whose commit changed; GC stale ephemeral ones (every tenant unless --tenant)")
    manifest_args(r)
    r.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                   help="wait up to SECONDS for a running refresh instead of skipping (on-demand use)")
    r.set_defaults(fn=cmd_refresh)

    dm = sub.add_parser("daemon", help="refresh every AIDD_REFRESH_INTERVAL_MINUTES until stopped (the `refresher` service)")
    manifest_args(dm, repos=False)
    dm.set_defaults(fn=cmd_daemon)

    dh = sub.add_parser("daemon-health", help="exit 0 when the refresher finished a run within 2 intervals (healthcheck)")
    dh.set_defaults(fn=cmd_daemon_health)

    i = sub.add_parser("index", help="index one repository (checkout as-is, or a given --ref)")
    i.add_argument("repo", help="repo name under WORKSPACE_PATH, or a path")
    i.add_argument("--ref", help="branch to index (fetched locally); defaults to the checked-out one")
    i.add_argument("--tenant", help="override tenant (default: AIDD_TENANT)")
    i.add_argument("--ephemeral", action="store_true", help="mark the snapshot as disposable (feature branches)")
    i.add_argument("--no-fetch", action="store_true", help="with --ref: do not fetch before resolving the ref")
    i.add_argument("--dry-run", action="store_true", help="extract and resolve, but do not write to Neo4j")
    i.add_argument("--out", help="with --dry-run: write the full payload as JSON to this file")
    i.set_defaults(fn=cmd_index)

    lk = sub.add_parser("link", help="rebuild CONSUMES/CALLED_FROM edges (HttpCall × HttpEndpoint) for a tenant")
    lk.add_argument("--tenant", help="tenant to link (default: every tenant in the manifest)")
    lk.add_argument("--config", help="manifest path (default: $AIDD_CONFIG or /app/atlas.yaml)")
    lk.set_defaults(fn=cmd_link)

    st = sub.add_parser("selftest", help="load every grammar and query; non-zero exit if the environment is broken")
    st.set_defaults(fn=cmd_selftest)

    sv = sub.add_parser("serve", help="run the `atlas` MCP server (streamable HTTP, read-only tools over the graph)")
    sv.add_argument("--host", default=None, help="bind address (default: ATLAS_MCP_HOST or 0.0.0.0)")
    sv.add_argument("--port", type=int, default=None, help="port (default: ATLAS_MCP_PORT or 3000)")
    sv.set_defaults(fn=cmd_serve)

    s = sub.add_parser("status", help="list indexed snapshots")
    s.add_argument("--tenant")
    s.set_defaults(fn=cmd_status)

    kn = sub.add_parser("knowledge", help="run the `knowledge` MCP server (insights + process policy for the skills)")
    kn.add_argument("action", choices=["serve"])
    kn.add_argument("--host", default=None)
    kn.add_argument("--port", type=int, default=None)
    kn.set_defaults(fn=cmd_knowledge)

    po = sub.add_parser("policy", help="process policy (policy.yaml): validate it, or show the effective policy of a repo")
    po.add_argument("action", choices=["show", "check"])
    po.add_argument("repo", nargs="?", help="show: repo whose effective policy to print (default: the tenant's)")
    po.add_argument("--tenant", help="tenant (default: AIDD_TENANT, or the only tenant of atlas.yaml)")
    po.add_argument("--policy", help="policy path (default: $AIDD_POLICY or /app/policy.yaml)")
    po.add_argument("--config", help="manifest path, for the repo's area (default: $AIDD_CONFIG or /app/atlas.yaml)")
    po.add_argument("--json", action="store_true", help="show: machine-readable output")
    po.set_defaults(fn=cmd_policy)

    w = sub.add_parser("wipe", help="delete everything indexed for a repo")
    w.add_argument("repo")
    w.add_argument("--ref")
    w.add_argument("--tenant")
    w.set_defaults(fn=cmd_wipe)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except ConfigError as e:
        log(f"error: {e}")
        return 2
    except GrammarError as e:
        log(f"error: {e}")
        return 4
    except KeyboardInterrupt:
        log("interrupted")
        return 130
    except Exception as e:  # noqa: BLE001
        if e.__class__.__module__.startswith("neo4j"):
            log(f"error: Neo4j {type(e).__name__}: {str(e).splitlines()[0]}")
            log("       check NEO4J_URI / credentials / database, and that the neo4j container is healthy")
            return 3
        raise


if __name__ == "__main__":
    sys.exit(main())
