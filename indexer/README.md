# aidd-indexer

Loads a repository's **micro graph** into atlas (Neo4j): `Repo`, `Snapshot`, `Module`,
`File`, `Symbol`, `CONTAINS`, `IMPORTS`, `CALLS`. Schema: [`../neo4j/SCHEMA.md`](../neo4j/SCHEMA.md).

v0 uses tree-sitter for every language (Go, TypeScript/TSX/JS, Python, C#). A call resolves
through a mediator's dispatch or the receiver's declared type where the language answers it (Go
and C# so far, through the type service in `core/types.py`), and otherwise **by name inside the
repo** (`same-file` → `same-module` → `unique-name`); `neo4j/SCHEMA.md` lists every strategy.
Precise, cross-file resolution via SCIP is planned; the edge property `resolved=false`
marks today's edges so they can be upgraded in place.

## Run (recommended: the `aidd` client)

`setup/install.sh` installs `~/.aidd/aidd` (linked as `aidd` when `~/.local/bin` exists). It is a thin
client: every command runs in a container — inside the `refresher` when it is running (so it shares
its lock), otherwise in a one-off `indexer` container of the same image.

```bash
aidd plan                     # what atlas.yaml would index, and why
aidd bootstrap                # index everything (asks first)
aidd refresh                  # only what changed (+ GC), every tenant; skipped while another refresh runs
aidd refresh --tenant t --repos x --wait 300   # one repo on demand (the scan skill); waits for a running refresh
aidd index <repo> --ref feature/x   # one branch on demand — pushed or not
aidd status                   # snapshots with age and trigger (manual | scheduled | bootstrap)
aidd schedule install|status|remove|check [--fix]   # the refresher (see below)
aidd logs [-f]                # the refresher's log
aidd policy show [repo]       # effective process policy (policy.yaml) and where each value came from
aidd policy check             # validate ~/.aidd/policy.yaml
aidd knowledge serve          # the `knowledge` MCP server (the mcp-knowledge service runs it)
AIDD_NO_FETCH=1 aidd plan     # no remote fetch (mirrors synced from the workspace only)
```

**Refresher (continuous update).** The `refresher` compose service runs `aidd daemon`: a
`refresh` of every tenant in the manifest every `AIDD_REFRESH_INTERVAL_MINUTES` (`.env`, default 15,
± 10 % jitter, counted from the end of the previous run). Docker restarts it after reboots on every OS
— there is no host scheduler (the systemd timer / Task Scheduler / cron of earlier versions are
removed by `aidd schedule install` or `aidd schedule check --fix`). Each run writes
`~/.aidd/state/status.json` (read by the compose healthcheck `aidd daemon-health` and by
`aidd schedule status`) and a `RefreshState` per tenant in atlas (read by `atlas_status.refresh` —
`stale: true` after two intervals without a run — and by `install-check.sh`). SIGTERM finishes the
snapshot being written and exits.

**Mirrors — the workspace is read-only.** The indexer containers mount `WORKSPACE_PATH` read-only and
never write to your clones. Each repo is synced into `~/.aidd/mirrors/<tenant>/<repo>.git`
([`core/mirror.py`](aidd_indexer/core/mirror.py)): first from your clone (your branches, unpushed ones
included, and your view of `origin`, no network), then `git fetch origin` with the service credential.
Plans, `git archive` and `index --ref` read the mirror. Disable the remote half with `--no-fetch` or
`fetch: false` on the source.

**Fetch authentication.** A **read-only PAT** in `~/.aidd/secrets/git-token` (one line, `chmod 600`,
written by `install.sh` step 6). Compose mounts it as a secret file (`/run/secrets/git-token`) — never
an environment variable, so it does not show in `docker inspect` — and `git-askpass.sh` hands it to
git; ssh remotes are fetched over https for that one command (`url.<https>.insteadOf`), the mirror's
config is not rewritten. Without a token (empty file) ssh remotes are not fetched at all: the mirrors
follow your own fetches. Your personal ssh key and agent are never mounted. Server/CI variants:
`AIDD_GIT_TOKEN` / `AIDD_GIT_TOKEN_<HOST>` (`GITHUB_COM`, `GITLAB_COM`, `DEV_AZURE_COM`), username
`x-access-token` by default.

The containers run as the host user (`AIDD_UID`/`AIDD_GID` in `.env`), so the mirrors, the state and
anything else written to bind mounts belong to you, on Linux as on macOS.

## Run (directly from the compose stack)

Everything is driven by `~/.aidd/atlas.yaml` (written by `setup/install.sh`, reference in
[`atlas.example.yaml`](atlas.example.yaml)): sources per tenant, repo include/exclude globs, the
ref policy and optional business areas.

```bash
cd ~/.aidd
docker compose run --rm indexer plan                 # repos × refs the manifest selects, and why
docker compose run --rm indexer bootstrap            # index all of it (prints the plan, asks first)
docker compose run --rm indexer refresh              # only snapshots whose commit changed + GC of stale ephemeral ones
docker compose run --rm indexer status
docker compose run --rm indexer index <repo>                 # one repo, checkout as-is
docker compose run --rm indexer index <repo> --ref develop   # one repo, a specific branch (from the mirror)
docker compose run --rm indexer wipe <repo>
docker compose run --rm indexer selftest              # grammars + queries load (the image build runs this too)

# The `atlas` MCP is the same image serving `aidd serve` (compose service mcp-atlas, behind
# mcp-gateway on port 3005):
curl -s http://localhost:3005/healthz                 # {"status":"ok","neo4j":true,...}
```

**Ref policy** (per tenant): `always` branches are indexed when they exist (`main`, `master`,
`develop` by default); `patterns` adds globs such as `release/*`; `active` adds branches with a
commit in the last `max_age_days`, not merged into the default branch, not matching `exclude`
(bots and non-code branches: `dependabot/*`, `renovate/*`, `docs/*`, `ci/*`, `cd/*`, `pipeline/*`), capped at `max_per_repo` — these are flagged `ephemeral` and removed by `refresh` after
`gc_ephemeral_after_days` once they stop being selected. All branches are never indexed.
The policy reads the remote-tracking branches (what the team pushed); a branch that only exists in
your clone is indexed on demand (`aidd index <repo> --ref <branch>`).
Refs are materialized with `git archive <sha>` into a temp dir — no working tree is touched.

`AIDD_TENANT` is **required** (written to `.env` by `setup/install.sh`, same value as the skills'
`tenant:` frontmatter). For `index`, `auto` derives the tenant from the path
(`<WORKSPACE_PATH>/<tenant>/<repo>`); the manifest always names tenants explicitly. There is no
fallback: a missing or underivable tenant is an error, never a guess.

## Run locally (development)

```bash
cd indexer && pip install -e .
export NEO4J_URI=bolt://localhost:7687 NEO4J_USERNAME=neo4j NEO4J_PASSWORD=... NEO4J_DATABASE=atlas
export WORKSPACE_PATH=/path/to/workspace AIDD_TENANT=auto
aidd index my-repo --dry-run --out /tmp/my-repo.json   # no database needed
aidd index my-repo
```

`--dry-run --out` writes the full payload (symbols, resolved calls, imports, packages) as JSON —
the fastest way to inspect what a language query extracts.

## Layout (ADR-003: core + language modules + conventions)

```
aidd_indexer/
  cli.py                    aidd plan / bootstrap / refresh / index / link / status / policy / wipe / selftest / serve
  daemon.py                 aidd daemon: the refresher's loop, lock, status file and health
  tree.py                   node text, a cursor walk and a per-node cache; no language
  core/                     language-agnostic pipeline — never names a language
    config.py manifest.py   env + atlas.yaml (tenants, sources, refs, areas, conventions)
    policy.py               policy.yaml: process policy in layers (built-in → defaults → tenant → area → repo)
    planner.py gitinfo.py   sources → (repo, ref, sha) items; git plumbing
    mirror.py               bare mirrors of the read-only workspace, which every git read goes to
    build.py                which indexer wrote a snapshot: the version plus a fingerprint of the code
    discovery.py            file list (git ls-files), languages via the registry, modules (manifests + language hooks)
    extract.py              tree-sitter parsing; symbols, call sites, imports — hooks into LanguageSupport
    resolve.py dispatch.py  CALLS (mediator dispatch, the receiver's type, then by name; a call that does not dispatch
                            never by name), IMPORTS, external Packages
    edges.py                the resolver's records: a CALLS edge, its evidence and whether it may dispatch, one per
                            key; IMPORTS; Package
    hierarchy.py            EXTENDS and IMPLEMENTS: the bases of the repo a type names, as its language reads them;
                            none for two types of one qualified name
    types.py                the type service (ADR-005): TypeRef, Unknown with its reason, the TypeIndex questions
    integrations.py         HTTP candidates orchestrator (per-dir context → language http scanner → compose)
    http_base.py            BaseScanner: where a route lives, handler-vs-data, method detection
    http_expr.py            expression → path template and method; a directory's constants
    http_scope.py http_mounts.py http_view.py http_wrappers.py http_nodes.py
                            a file's scopes, the mount graph, the repo view, client wrappers, node kinds
    package_facts.py scan_patterns.py  package facts' base; what a convention adds to the scanners
    paths.py matching.py    normalize_path / path_key; when a call and a route meet (linker, MCP, corpus)
    deps.py                 manifests → provides / requires per repo (LanguageSupport.manifest_deps)
    linker.py               HttpCall × HttpEndpoint → CONSUMES / CALLED_FROM; requires × provides → DEPENDS_ON (pure; graph.py reads and writes)
    graph.py ids.py model.py Neo4j writer (idempotent MERGE, GC), id convention, dataclasses
    graph_session.py graph_links.py graph_snapshots.py
                            what the writer inherits: the session, the linker's reads and writes, the snapshots'
                            bookkeeping (shas, failures, heartbeat, status, GC, wipe)
    dry_run.py              what `aidd index --dry-run --out` writes in place of the graph
  languages/                one folder per language; registered in languages/__init__.py
    base.py                 LanguageSupport contract (identity · discovery · symbols · resolution · http)
    go/ typescript/ csharp/ python/
      queries.scm           tree-sitter patterns: @def.<kind> + @name, @call + @callee (+ @receiver), @import
      symbols.py            the LanguageSupport subclass (qualified names, visibility, imports, resolution)
      http.py               the BaseScanner subclass (routes exposed, outbound calls)
      http_facts.py         what a file publishes for compose, and the requests it leaves pending (Go, C#, TS)
      package_facts.py      the language's package facts (Go, Python, TS)
      …                     what a scanner splits out (client wrappers, TS's file routes): the guide's §2
    go/ csharp/
      type_facts.py         a file's type facts as values with no tree node
      type_index.py         the language's TypeIndex, built once per repo
      locals.py             the type a name's declaration in scope gives it, for the resolver and the scanner
    csharp/
      type_syntax.py        how C# writes a type: its simple name, its type arguments, a declaration's type parameters
      written.py            the receiver's written start read through the TypeIndex, then the members after it
      wiring.py             what the DI container builds for an interface; who handles a mediator's message
  conventions/              pluggable rules of *your* development pattern (layers, allowed deps, targets)
    base.py                 Convention contract + ConventionContext
    declarative.py          convention.yaml → Convention (no Python needed)
    __init__.py             registry: path | entry point `aidd.conventions` | `module:Class`; apply()
  mcp/                      MCP `atlas` (read-only tools over the graph)
    server.py store.py      assembles the tools; the Neo4j accessor per tenant
    tools_*.py              one module per tool group (status, symbols, HTTP, impact, violations and Cypher)
  knowledge/                MCP `knowledge` (docs/knowledge-contract.md) — image stage `knowledge`
    vault.py                safe names, frontmatter, owned `aidd:` blocks, atomic writes
    insights.py             insight notes, lifecycle data, the index's knowledge block
    vectors.py              FastEmbed (mcp-qdrant's model) + the Qdrant mirror
    service.py server.py    record_insight / insights_for / refresh_index / policy_for, and the MCP server
```

## Adding a language

1. `mkdir aidd_indexer/languages/<lang>/` with `queries.scm` (`@def.<kind>` + `@name`, `@call` +
   `@callee` (+ optional `@receiver`), `@import`; blank lines separate patterns).
2. `symbols.py`: subclass `LanguageSupport`, override only what differs (`module_prefix`,
   `qualified_name`, `visibility`, `import_bindings`, `resolve_import`; optionally `file_facts` +
   `call_receiver` + `resolve_receiver` and a `type_index`, the language's `TypeIndex` (ADR-005), so
   method calls resolve by the receiver's static type, as Go and C# do) and export
   `LANGUAGES = [<instance>]` with `id`, `grammar`, `extensions`, `query_file`, `stack`, `manifests`.
3. Optional `http.py`: subclass `BaseScanner`, set `http_scanner=` on the instance.
4. Add the folder name to `_MODULES` in `languages/__init__.py`. The Dockerfile prefetches the
   grammar and `aidd selftest` checks it — nothing else to edit.
5. Add a fixture under `tests/fixtures/` and run the public corpus (`scripts/http_corpus.py`).

## Adding a convention

Write a `convention.yaml` (see `setup/conventions/hexagonal.example.yaml`) and reference it in
`atlas.yaml` under the tenant's `conventions:`. For rules the declarative format cannot express,
subclass `aidd_indexer.conventions.base.Convention` in your own package and publish it under the
`aidd.conventions` entry-point group (or reference it as `package.module:Class`). Conventions never
change extraction — they annotate (`File.layer`, `Module.layer`, `HttpCall.target_hint`,
`Symbol.is_entry_point`) and emit `Violation` nodes.
