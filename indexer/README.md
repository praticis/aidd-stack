# aidd-indexer

Loads a repository's **micro graph** into atlas (Neo4j): `Repo`, `Snapshot`, `Module`,
`File`, `Symbol`, `CONTAINS`, `IMPORTS`, `CALLS`. Schema: [`../neo4j/SCHEMA.md`](../neo4j/SCHEMA.md).

v0 uses tree-sitter for every language (Go, TypeScript/TSX/JS, Python, C#) and resolves
calls **by name inside the repo** (`same-file` → `same-module` → `unique-name`). Precise,
cross-file resolution via SCIP arrives in roadmap F1.2; the edge property `resolved=false`
marks today's edges so they can be upgraded in place.

## Run (recommended: the `aidd` host wrapper)

`setup/install.sh` installs `~/.aidd/aidd` (linked as `aidd` when `~/.local/bin` exists). It runs
`git fetch --all --prune` **on your machine** and then calls the containerized indexer with
`--no-fetch`. Unix sockets (ssh-agent) do not cross into Docker Desktop/WSL containers, so this is
the reliable path for developers — and the only one the scheduler uses.

```bash
aidd plan                     # host fetch + plan
aidd bootstrap                # host fetch + index everything (asks first)
aidd refresh                  # host fetch + only what changed (+ GC); locked, logged
aidd index <repo> --ref develop
aidd status                   # snapshots with age and trigger (manual | scheduled | bootstrap)
aidd schedule install|status|remove
AIDD_NO_FETCH=1 aidd plan     # skip the host fetch
```

**Fetch authentication on the host.** Two modes, chosen automatically:

| mode | when | how |
|---|---|---|
| `service` | `~/.aidd/secrets/git-token` exists (written by `install.sh` step 6) | a **read-only PAT** sent via `GIT_ASKPASS`; ssh remotes are rewritten to https for that one command (`url.<https>.insteadOf`), the repo config is untouched. This is what the scheduler needs: works with nobody logged in, survives reboots, revocable |
| `personal` | no token file (or `AIDD_FETCH_AUTH=personal`) | your own ssh key / agent / credential helper — fine interactively, fails unattended when the key has a passphrase |

**Scheduler.** `aidd schedule install` reads `AIDD_REFRESH_INTERVAL_MINUTES` from `.env` (default 15)
and installs, in order of preference: a **systemd user timer** (Linux and WSL with `systemd=true` in
`/etc/wsl.conf` — runs where Docker and the repos live, no window, `loginctl enable-linger` keeps it
alive without a terminal), the Windows Task Scheduler as a fallback on WSL without systemd (hidden via
`conhost --headless`), or a crontab entry.
Each run is serialized with `flock`, appends to `~/.aidd/logs/refresh.log` (rotated at 5 MB), and
records `trigger: scheduled` on the `IndexRun`. `install-check.sh` fails when the last refresh is
older than twice the interval.

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
docker compose run --rm indexer index <repo> --ref develop   # one repo, a specific fetched branch
docker compose run --rm indexer wipe <repo>
docker compose run --rm indexer selftest              # grammars + queries load (the image build runs this too)

# The `atlas` MCP is the same image serving `aidd serve` (compose service mcp-atlas, port 3005):
curl -s http://localhost:3005/healthz                 # {"status":"ok","neo4j":true,...}
```

**Ref policy** (per tenant): `always` branches are indexed when they exist (`main`, `master`,
`develop` by default); `patterns` adds globs such as `release/*`; `active` adds branches with a
commit in the last `max_age_days`, not merged into the default branch, not matching `exclude`
(bots and non-code branches: `dependabot/*`, `renovate/*`, `docs/*`, `ci/*`, `cd/*`, `pipeline/*`), capped at `max_per_repo` — these are flagged `ephemeral` and removed by `refresh` after
`gc_ephemeral_after_days` once they stop being selected. All branches are never indexed.

Before reading refs, `plan`/`bootstrap`/`refresh` (and `index --ref`) run `git fetch --all --prune`
in each local repo, so the atlas reflects what the team pushed rather than what one developer last
fetched. A failed fetch is reported under `skipped:` and the repo is planned on its local refs.
Disable with `--no-fetch` or `fetch: false` on the source.

**Authentication for the in-container fetch** (server/CI scenario; developers should prefer the
host wrapper above, where all of this is moot):

| remote | how |
|---|---|
| ssh, key without passphrase | works out of the box (`~/.ssh` is mounted read-only) |
| ssh, key with passphrase | start the agent in the shell that runs compose: `eval $(ssh-agent) && ssh-add`; `SSH_AUTH_SOCK` is forwarded into the container |
| https + PAT | `AIDD_GIT_TOKEN=<pat>` in `.env`; per host `AIDD_GIT_TOKEN_GITHUB_COM`, `..._GITLAB_COM`, `..._DEV_AZURE_COM`; username defaults to `x-access-token` |
| https + Git Credential Manager / `gh auth` | not available inside the container — use a PAT as above |

Tokens are read from environment variables only (`git-askpass.sh`), never stored in files or in
`atlas.yaml`.
Refs are then materialized with `git archive <sha>` into a temp dir — the working tree is never touched.

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

## Layout

| file | role |
|---|---|
| `cli.py` | `aidd plan / bootstrap / refresh / index / status / wipe` |
| `manifest.py` | `atlas.yaml` loader (tenants, sources, ref policy, areas) |
| `planner.py` | sources → repos → (repo, ref, sha) items with reasons; plan rendering |
| `discovery.py` | file list (`git ls-files`), languages, modules (manifests + Go packages) |
| `extract.py` | tree-sitter parsing; symbols, call sites, imports, entry-point heuristics |
| `queries/*.scm` | per-language patterns — compiled one by one, unsupported ones are skipped with a warning |
| `resolve.py` | name-based call resolution, import resolution, external `Package` nodes |
| `graph.py` | Neo4j writer: idempotent `MERGE`, snapshot, orphan GC, `IndexRun` |
| `ids.py` | id convention (SCHEMA.md §4) |

## Adding a language

1. Map the extension in `discovery.LANGUAGE_BY_EXT` and add it to `PARSEABLE`.
2. Write `queries/<language>.scm` with `@def.<kind>` + `@name`, `@call` + `@callee` (+ optional
   `@receiver`), and `@import` captures. Blank lines separate patterns.
3. Teach `resolve._resolve_one` how that ecosystem's import specs map to files/packages.
