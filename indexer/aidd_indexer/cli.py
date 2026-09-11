"""`aidd` command line.

  aidd plan      [--tenant T] [--repos a,b] [--config FILE]           what would be indexed, and why
  aidd bootstrap [--tenant T] [--repos a,b] [--yes] [--config FILE]   index everything the plan lists
  aidd refresh   [--tenant T] [--config FILE]                          re-index only what changed + GC
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
from .config import ConfigError, Neo4jConfig, resolve_repo, resolve_tenant
from .discovery import PARSEABLE, build_files, discover_modules, list_files
from .extract import GRAMMAR_ERRORS, extract_file, load_language
from .gitinfo import current_ref, default_ref, export_tree, fetch, head_sha, is_git_repo, list_branches, remote_url
from .model import ExtractionResult, RepoInfo
from .resolve import Resolved, Resolver


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class GrammarError(RuntimeError):
    """A supported language's grammar failed to load — the environment is broken."""


# who started this run — recorded on every IndexRun (manual | scheduled | bootstrap)
TRIGGER = os.getenv("AIDD_TRIGGER", "manual")


# -- core: extract + resolve one tree -------------------------------------------------------

def extract_tree(repo: RepoInfo) -> tuple[ExtractionResult, list]:
    t0 = time.time()
    rel_files = list_files(Path(repo.root))
    modules, stack = discover_modules(repo, rel_files)
    repo.stack = sorted(stack)
    files = build_files(repo, rel_files, modules)
    res = ExtractionResult(repo=repo, modules=modules, files=files)
    log(f"[discover] {len(rel_files)} files, {len(files)} recorded, {len(modules)} modules, stack={repo.stack} ({time.time()-t0:.1f}s)")

    missing = []
    for lang in sorted({f.language for f in files} & PARSEABLE):
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
        if f.language not in PARSEABLE:
            continue
        fx, warns = extract_file(repo, f)
        res.warnings.extend(warns)
        if fx is None:
            continue
        extractors.append(fx)
        res.symbols.extend(fx.symbols)
        res.calls.extend(fx.calls)
        res.imports.extend(fx.imports)
    log(f"[extract]  {len(res.symbols)} symbols, {len(res.calls)} call sites, {len(res.imports)} imports ({time.time()-t0:.1f}s)")
    return res, extractors


def extract_and_resolve(repo: RepoInfo) -> tuple[ExtractionResult, Resolved]:
    res, extractors = extract_tree(repo)
    rv = Resolver(res, extractors).run()
    log(f"[resolve]  {len(rv.calls)} CALLS edges ({rv.unresolved_calls} unresolved call sites), "
        f"{len(rv.imports)} IMPORTS edges ({rv.unresolved_imports} unresolved), {len(rv.packages)} external packages")
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
    from .graph import GraphWriter  # lazy: dry-run / plan must work without a database
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
        if not args.no_fetch:
            ok, msg = fetch(repo_path)
            log(f"[fetch]    {repo_path.name}: {msg}" + ("" if ok else " — using local refs"))
        branches = {b["name"]: b for b in list_branches(repo_path)}
        if args.ref not in branches:
            raise ConfigError(f"ref '{args.ref}' not found in {repo_path.name} (known: {', '.join(sorted(branches)[:15])}...)")
        gw, cfg = open_graph()
        try:
            index_exported_ref(gw, repo_path, repo_path.name, tenant, args.ref, branches[args.ref]["sha"],
                               args.ephemeral, remote_url(repo_path), default_ref(repo_path), None)
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
    finally:
        gw.close()
    return 0


def _load_plan(args: argparse.Namespace):
    from .manifest import load_manifest
    from .planner import build_plan
    manifest = load_manifest(args.config)
    tenant = manifest.tenant(args.tenant)
    only = [r.strip() for r in args.repos.split(",")] if getattr(args, "repos", None) else None
    do_fetch = not getattr(args, "no_fetch", False)
    if do_fetch:
        log("[fetch] refreshing remote-tracking refs (git fetch --all --prune) — use --no-fetch to skip")
    return tenant, build_plan(tenant, only, do_fetch=do_fetch, progress=log)


def cmd_plan(args: argparse.Namespace) -> int:
    from .planner import render_plan
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
    from .planner import render_plan
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
        return _run_items(gw, tenant, plan.items, skip_up_to_date=False)
    finally:
        gw.close()


def cmd_refresh(args: argparse.Namespace) -> int:
    tenant, plan = _load_plan(args)
    gw, _ = open_graph()
    try:
        indexed = gw.snapshot_shas(tenant.name)
        todo = [it for it in plan.items if indexed.get((it.repo.name, it.ref)) != it.sha]
        log(f"[refresh] {len(todo)} of {len(plan.items)} snapshots changed or new")
        rc = _run_items(gw, tenant, todo, skip_up_to_date=True) if todo else 0
        gone = gw.gc_ephemeral(tenant.name, tenant.refs.gc_ephemeral_after_days,
                               keep={(it.repo.name, it.ref) for it in plan.items})
        log(f"[refresh] ephemeral snapshots removed: {gone}")
        return rc
    finally:
        gw.close()


def _run_items(gw, tenant, items, skip_up_to_date: bool) -> int:
    ok = failed = 0
    t_all = time.time()
    for n, it in enumerate(items, 1):
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


def cmd_selftest(args: argparse.Namespace) -> int:
    """Load every grammar and compile every query. Exit 1 on any failure."""
    import tree_sitter, tree_sitter_language_pack  # noqa: F401
    from importlib.metadata import version
    log(f"tree-sitter {version('tree-sitter')} · tree-sitter-language-pack {version('tree-sitter-language-pack')} · python {sys.version.split()[0]}")
    from .extract import GRAMMAR_OFFLINE
    log(f"grammar cache {tree_sitter_language_pack.cache_dir()} · cached: {', '.join(tree_sitter_language_pack.downloaded_languages()) or '(none)'}"
        f" · downloads {'forbidden (AIDD_GRAMMAR_OFFLINE)' if GRAMMAR_OFFLINE else 'allowed'}")
    bad = 0
    for lang in sorted(PARSEABLE):
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
    finally:
        gw.close()
    log(f"[wipe] deleted {n} nodes for {tenant}/{name}" + (f"@{args.ref}" if args.ref else " (all refs)"))
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

    r = sub.add_parser("refresh", help="re-index snapshots whose commit changed; GC stale ephemeral ones")
    manifest_args(r, repos=False)
    r.set_defaults(fn=cmd_refresh)

    i = sub.add_parser("index", help="index one repository (checkout as-is, or a given --ref)")
    i.add_argument("repo", help="repo name under WORKSPACE_PATH, or a path")
    i.add_argument("--ref", help="branch to index (fetched locally); defaults to the checked-out one")
    i.add_argument("--tenant", help="override tenant (default: AIDD_TENANT)")
    i.add_argument("--ephemeral", action="store_true", help="mark the snapshot as disposable (feature branches)")
    i.add_argument("--no-fetch", action="store_true", help="with --ref: do not fetch before resolving the ref")
    i.add_argument("--dry-run", action="store_true", help="extract and resolve, but do not write to Neo4j")
    i.add_argument("--out", help="with --dry-run: write the full payload as JSON to this file")
    i.set_defaults(fn=cmd_index)

    st = sub.add_parser("selftest", help="load every grammar and query; non-zero exit if the environment is broken")
    st.set_defaults(fn=cmd_selftest)

    s = sub.add_parser("status", help="list indexed snapshots")
    s.add_argument("--tenant")
    s.set_defaults(fn=cmd_status)

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
