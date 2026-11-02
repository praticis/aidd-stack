# AIDD Stack — Evolution roadmap (code graph + skills)

> A living document. Mark `[x]` when done. Update the **Where we are** section every session so that any agent or
> person picks up from the right point.

## Where we are

- **Phases:**
  - **Phase 0** (foundation) is done;
  - **Phase 1** started on 2026-10-13 with F0.7.3;
  - **F1.14** (the HTTP extractor measured on the public corpus, H2) closed on 2026-10-19.
- **The milestones and why each choice was made:** `docs/history.md`, one milestone per line, and
  `docs/decisions.md`.
- **Measuring the extractor:**
  - `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-29`;
  - the hold-out: `--holdout --baseline 2026-10-18-v2-holdout-26`;
  - the numbers are in `docs/corpus-report.md`.
- **The gates in CI (H7's first slice, PR #11):** every PR that touches the indexer runs the tests, the corpus, the
  hold-out and the micro graph against `main`. `tests` and `gates` are required to merge into `main`. Since slice 1c
  (PR #22), `tests` also runs the MCP and the graph writer against a throwaway Neo4j.
- **Technical debts:** `docs/tech-debt.md` lists the known defects that do not block, each with the phase it is due in
  and a strict xfail test that fails the suite when it is fixed.
- **In progress:**
  - H5 (`docs/handoffs/H5-indexer-refactor.md`, "State"): its first part merged as PR #7 (H5-D8). Step 5 (the
    `TypeIndex`) goes one language at a time, a refactor and then a change of behavior (H5-D10). Go (PRs #17, #19, #20)
    and C# (PRs #23, #25, the `fix(csharp)` of H5-D17, #27, and the fix of which extension method a call reaches,
    H5-D18, #30) are merged and validated on a live install. The defects the fixes leave, and the gaps H5-D16 and H5-D17
    left out, are debts (`docs/tech-debt.md`, TD-001 to TD-022); TD-005 to TD-007, TD-010, TD-011, TD-013, TD-014,
    TD-016 to TD-022, TD-027, TD-033 and TD-034 are due in `fix(csharp)` PRs before F1.2. Go's calls on an interface,
    which reach no method of the repo unless a single implementer declares it, TD-029, are due in a `fix(go)` PR before
    F1.2. The calls on `base` and on `super` that reached the caller's own method or no ancestor, TD-030 and TD-031, and
    the bases two C# types of one name in one file took from each other, TD-032, are closed by F1.16's `fix(resolve)`
    #60 (H5-D32). A symbol's signature that lost the `>` it ends with, TD-040, found by #69's live validation, is
    closed by `fix(graph)` #70, and TS's module resolution that was not the compiler's, TD-038, by `fix(typescript)`
    #72 (H5-D40). Two debts of the core's architecture, the syntax of each language it holds, TD-023, and the names of
    frameworks and client libraries it holds, TD-024, and a gap of Python's, Django's model managers found by name,
    TD-026, and a C# call on an interface that reaches its single implementer twice, TD-036, and four of TS's, a
    function a class field holds, TD-037, a CommonJS export the type index does not read, TD-039, a hand-written
    declaration file discovery skips, TD-041, and a package of the repo's own workspace read as an npm package, TD-042,
    are due in an H5 step: 6 and 12 for TD-023, 6 for TD-024, TD-026 and TD-036, 5 for TD-037, TD-039, TD-041 and
    TD-042. Python's step 5 is merged and validated on a live install too (H5-D22's PRs: #42,
    #44, #45, #47), with TD-025 due in F1.2 (H5-D26). F1.16 is closed (#57 to #63). Next, TS (H5-D29), in ten PRs
    (H5-D36, H5-D37, H5-D39, H5-D40), judged with the per-site attribution every language now has (H5-D21), which reads the
    resolver's stage too (G2, #56), before the `fix(csharp)` PRs (H5-D19);
    then step 6 (recognizers and the catalog; C#, Go, Python, TS: H5-D20), step 12 (the rest of the code to the shape
    targets), then 10 and 11;
  - H6 (`docs/handoffs/H6-extraction-pipeline.md`): the extraction as a parallel map, a reduce and a per-file cache,
    designed now, plugged in after H5.
    - Step 0, the measurement, is done ("H6 baseline" in the corpus report).
    - It found the resolver quadratic in Go and C#. The fix, an index built once, is in `main` (PR #9).
    - Step 1, the prototypes, is done ("H6 step 1"). A second map that re-extracts (B), with a cache keyed per
      package (D), gives identical output and warm runs of 14–23 s on mattermost, against 73 s today.
    - Step 2 is done: B keyed per package (H6-D5), and batches of whole packages scanned in the worker (H6-D6), with
      14–22 % less CPU than batches of files and the same output. ADR-004 to ADR-006 are accepted.
  - H7 (`docs/handoffs/H7-regression-gates.md`): slices 1 and 1c are in `main`; the next slices are open, and the judgment is to be automated (H7-D6).
- **The order up to SCIP (H5-D1, H6-D1):** design H6 → H5 (the indexer refactor, `docs/handoffs/H5-indexer-refactor.md`,
  with no behavior change, built toward H6's design) → plug H6 in → the new hold-out, measured once, and its handoff
  (H2-D21) → P2 (the indexer in its own repo) → SCIP (F1.1, F1.2).
- **Active handoffs:** H3 (AI dev efficiency), H4 (public docs and the indexer in its own repo), H4.1 (the
  contributor path), H5, H6 and H7. Closed: H1 and H2.
- **Candidates:**
  - a handoff of its own on code quality gates, which the author asked for on 2026-10-21. Until then the shape ratchet
    holds (H5-D9);
  - `dispatch` for validators reached by the bus pipeline (`SendAsync(cmd)` → `AbstractValidator<cmd>`);
  - re-run the .NET Q4 with dispatch.
- **Non-blocking leftovers:**
  - the `raw_path` of a call through a wrapper whose base ends in `/` comes out with a double slash (the normalized
    path is right);
  - a PAT with access to the tenant's org;
  - validation on WSL (SO14);
  - gaps from the code review feedback: Go `who_calls` across repos, messaging by event type.

## Principles (non-negotiable)

- The knowledge layer (graph + vectors + vault) is **orchestrator-independent**: MCP + skills only. Cline, Roo,
  Goose, Claude Code or Aider consume the same backend.
- **Deterministic** extraction (SCIP / tree-sitter). An LLM only summarizes and disambiguates; never the primary
  parser.
- **Design a change by its contracts, boundaries and proof** (decided on 2026-10-28, `docs/design.md`).
  - A refactor or a new implementation first asks what already answers its question: a contract the system keeps
    between its stages, or a reference outside it. Only then does it write a new answer.
  - The core stays universal and reads each language, framework or convention through a hook; their specifics live
    in their own modules.
  - A design is proven against an independent reference over the real data.
  - What the facts in sight do not decide is `Unknown`, with its reason.
- Every micro node carries `tenant`, `repo`, `ref` (branch), `commit_sha` and `indexed_at`, and a micro edge
  none of them, its two ends being in one snapshot; a macro edge of a ref carries that `ref` and the `commit_sha` of
  its evidence, and all but `DEPENDS_ON` also `confidence` + `evidence`.
- Secrets never enter the index (extract the env var's *name*, never its value).
- Every phase ends with the **golden questions** passing (recall measured, not felt).
- A defect that does not block is a **debt** (`docs/tech-debt.md`), not a note: it has a strict xfail test, so the
  suite fails when it is fixed. Every phase ends with its debts settled, or moved by the author.
- **Code shape** (decided on 2026-10-18; H5 brings the current code up to it): a **single-digit** cyclomatic
  complexity per function (≤ 9, `ruff C901`) and at most **300 lines per module**, counted over the whole file. The CI
  fails what is new or grew over a target (a ratchet, H5-D9), and full blocking comes when the author decides. New
  code meets the targets from the start.
- **Comments say only the why the code does not:** a contract, an edge case, the reason for an order. No reference to
  docs or planning items (ROADMAP, `F1.x`, decisions, ADRs, guide sections), because docs change and the code should
  not point at them. No project name: an example describes the shape of the code, and only the framework or library
  that defines the behavior is named.
- **No real tenant, client or private project name** in docs, code, tests or fixtures. The repository is public.
  Where an example is needed, a neutral name is used (`orders-api`, `PARTNER_API_URL`).

## Target stack (open source / low cost)

| Layer | Tool | License / cost |
|---|---|---|
| Universal parser | tree-sitter | MIT |
| Precise indexing | SCIP: scip-go, scip-typescript, scip-dotnet, scip-python | Apache-2.0 |
| Graph DB | Neo4j Community (alt.: Memgraph Community) | GPLv3 / BSL — free |
| Vectors | Qdrant (already in the compose file) | Apache-2.0 |
| Embeddings | FastEmbed + `jinaai/jina-embeddings-v2-base-code` (alt.: nomic-embed-code via Ollama) | Apache-2.0, local |
| Docs/ADR | Obsidian + MCP (already in the compose file) | free (commercial use allowed since 2025) |
| `atlas` MCP | our own FastMCP (Python) + mcp-neo4j-cypher | Apache-2.0 |
| Local LLM | Ollama (Qwen-Coder / DeepSeek for summaries, classification) | free |
| Frontier LLM | Claude (planning, refinement, review) | **the only variable cost** |
| Planning | Jira via the Atlassian MCP | already available |
| Spec | Spec Kit (optional) | MIT |
| CI (phase 3) | GitHub Actions / GitLab CI with a self-hosted runner | free/low |

## When each thing becomes usable (so as not to get lost)

| Milestone | What you can now do | Does it change the skills? |
|---|---|---|
| Compose with Neo4j (done) | Open `localhost:7474`; the `atlas` MCP answers `get_neo4j_schema` | **No.** Empty graph; `scan` stays the same |
| F0.3–F0.5 indexer + linker v0 | `aidd index <repo>` fills the graph; validate with Cypher / golden questions | No |
| F0.6 our own `atlas` MCP (:3005) | Intent tools (`repo_map`, `who_consumes`…) available in Claude Code | No, but it enables the next one |
| F0.8 `scan` v2 | `scan` queries the graph first, falling back to the current flow | **Yes** — transparent: same trigger, more precise |
| F1.10 / F2.7 `flow`, `impact` | Micro/macro questions answered with evidence | New skills |
| S4/S5 `refine-business`, `refine-tech` | The full refinement flow (Jira → context → area → spec) | New skills; they depend on `impact` |

Rule: the graph reaches the skills only through the `atlas` MCP and **always with a fallback**. Up to F0.6 it is
infra in preparation — nothing to trigger day to day.

### Compose validation checklist (validated 2026-09-10/11; `install-check.sh` covers items 2–7 on every upgrade)

Shortcut: `~/.aidd/install-check.sh` (copied by `install.sh`) runs items 2–7 below and prints OK/FAIL per check.

- [x] `.env` has `NEO4J_USER=neo4j` and `NEO4J_PASSWORD=<password>` (`install.sh` generates them; if the volume
  already existed with another password: `docker compose down -v` and bring it up again — dev only)
- [x] `docker compose up -d --build` with no error; `docker compose ps` shows `neo4j` *healthy* and `neo4j-init` as
  *Exited (0)*
- [x] `docker logs aidd-neo4j-init` with no error (cypher-shell is silent on success — empty is good; a syntax error
  shows here)
- [x] **Neo4j Browser** at <http://localhost:7474> (log in with `.env`): `SHOW CONSTRAINTS` lists 14 constraints;
  `SHOW INDEXES` includes `symbol_fulltext`; `RETURN apoc.version()` answers
- [x] `docker logs aidd-mcp-atlas` shows Uvicorn listening on 0.0.0.0:3000; `curl -s http://localhost:3005/healthz`
  returns `{"status":"ok","neo4j":true,...}`
- [x] (debug) `docker compose --profile debug up -d mcp-neo4j` → `curl -s -o /dev/null -w "%{http_code}"
  http://localhost:3004/mcp/` returns an HTTP status
- [x] In Claude Code, with `setup/.mcp.json` applied: `/mcp` lists `atlas`; asking "run `get_neo4j_schema`" returns
  empty (a graph with no data) with no authentication error
- [x] Re-running `install.sh` syncs `~/.aidd/neo4j/` and the new `docker-compose.yml`
- [x] Docs: `git rm docs/graph-schema.md` (moved to `neo4j/SCHEMA.md`)

---

## Phase 0 — Foundation (end-to-end PoC, 2 repos)

Goal: prove micro + macro with the minimum: two repos (Go + Node) that talk over gRPC/HTTP, and a `who_consumes`
question answered from the graph.

- [x] F0.1–F0.2 Neo4j Community in the compose file (D1) and the schema in `neo4j/SCHEMA.md`
- [x] F0.3 The `indexer/`: `aidd index`, tree-sitter → micro nodes, idempotent `MERGE`, orphan GC and `IndexRun`.
  Also: F0.3.1 (validated on the real atlas), F0.3.2 (idempotency and GC), F0.3.5 (the indexing process:
  `atlas.yaml`, `plan`/`bootstrap`/`refresh`, `docs/indexing-process.md`), F0.3.6 (per-repo ref policy) and F0.3.7a
  (host wrapper, install without fetch, D12)
- [x] F0.4 The HTTP integrations extractor (`core/integrations.py` + `languages/<lang>/http.py`). Also:
  - F0.4.1, validated on the portfolio;
  - F0.4.2, the fixtures of the author's pattern (.NET: `dotnet-praticis`);
  - F0.4.3, the public corpus, H2a and H2b: `docs/corpus-report.md`, `docs/handoffs/H2-roadmap.md`;
  - F0.4.4, the ADR-003 refactor;
  - F0.4.5, conventions and `Violation`.
- [x] F0.5 The linker: `CONSUMES`/`CALLED_FROM` by `path_key` and method, with ties broken by hints. Also F0.5.1
  (validated; `DEPENDS_ON` by manifest)
- [x] F0.6 The `atlas` MCP, with 11 tools (`indexer/aidd_indexer/mcp/server.py`). Also F0.6.1, validated in Claude
  Code
- [x] F0.7 The 5 golden questions answered by the graph (`docs/golden-questions.md`). Also:
  - F0.7.1–F0.7.2b, `CALLS` by receiver type in Go and C#;
  - F0.7.3, Go interfaces and mediator dispatch.
- [x] F0.8 The `scan` skill over the atlas, with a fallback. Also F0.8.1, validated in 3 scenarios

**Phase exit:** a local graph with 2 repos, `who_consumes` working, `scan` reading from the graph. **Achieved
(2026-10-03):** 8 repos / 28 snapshots of the portfolio + the reference .NET pair; 130 endpoints, 90 exact
`CONSUMES`, 45 `DEPENDS_ON`; 11 tools in the MCP; Q1–Q5 answered by the graph in Go and .NET without reading code;
40 tests, a corpus of 15 repos as regression.

## Continuous update process (its own track — VERY important)

> **2026-10-12 — D15:** continuous update left the host. The compose `refresher` service (`aidd daemon`) replaces the
> scheduler (U2, U2.1, D14) and the fetch on the host (D12/D13 still hold in principle: a read-only PAT, the personal
> key kept out); U6 is no longer needed. The items below stay as history. Details in the **Security and operations**
> track.
>
> Separate from the install (D12). Without it the atlas ages and the skills answer about an outdated map. **U1–U3
> validated on 2026-09-11**: refresh scheduled through Task Scheduler (WSL), a read-only PAT, 14 of the team's
> snapshots re-indexed with no intervention, `install-check` green.

- [x] U1 **Service credential** (D13): a **read-only** PAT in `~/.aidd/secrets/git-token` (600), collected in step 6
  of `install.sh`; the wrapper uses it through `GIT_ASKPASS` and rewrites ssh→https remotes only for the fetch. Your
  personal key stays out of the scheduler. Validated: `fetch: ok (service)` on the 6 repos. Note: fine-grained needs
  admin approval in the org — classic (scope `repo`, short expiry) works as a bridge; a **GitHub App** is the target
  for the server (F1)
- [x] U2 **Scheduler on the host**: `aidd schedule install|status|remove|check [--fix]` — **systemd user timer
  preferred** (Linux and WSL with `systemd=true`; runs where Docker and the repos live, no window, `enable-linger`),
  hidden Task Scheduler (`conhost --headless`) as a fallback on WSL without systemd, cron last; interval in
  `AIDD_REFRESH_INTERVAL_MINUTES` (.env, default 15); `flock` + a rotating `~/.aidd/logs/refresh.log`. Validated on
  WSL (`schtasks.exe` from the distro)
- [x] U3 **Observability**: `aidd status` with age and `trigger` (manual/scheduled/bootstrap); `install-check.sh`
  section 6 fails if the last refresh > 2× the interval
- [x] U2.1 Scheduler inside WSL (D14): `systemd=true` + linger + distro autostart (`.vbs` in Startup); the Windows
  task removed automatically; `aidd schedule check --fix` validates/repairs. Validated on a clean install 2026-09-11
- [x] U3.1 End-to-end validation (2026-09-11): clean install → step 6 with a PAT → task created → the scheduled
  refresh re-indexed 14 snapshots (`trigger=scheduled auth=service rc=0`) → `install-check.sh` green
- [x] U3.2 Re-validation after the grammar fix (2026-09-11 14:29, offline image): a push to
  `<project-a>@feature/<ticket>` → systemd timer → `1 of 26 changed` → extract/resolve/write in 1 s
  (`orphans_deleted: 1`) → `rc=0` → `aidd status` with the new SHA, `age=1m`, `trigger=scheduled`. **Track U1–U3
  done.**
- [ ] U4 **Event trigger (F3)**: a webhook/CI on a push to a protected branch → `aidd index <repo> --ref <branch>`;
  replaces the scheduler on the central server
- [x] U5 **In-container fetch**: became the default path with the refresher (D15) — a mirror per repo, the PAT as a
  file through `git-askpass.sh`. Validated with a local remote in the e2e; **still to validate against GitHub with a
  real PAT**
- [x] U6 **Linux / macOS portability** — solved by D15: no scheduler and no GNU bash on the host (`aidd` became a thin
  client compatible with bash 3.2). The list below stays as history
  - Native Linux: should work as is (systemd user timer → cron as a fallback). Only needs **validating** on a machine
    (Ubuntu/Fedora with Docker Engine or Docker Desktop)
  - macOS — changes needed in `setup/aidd` and `install-check.sh` (bash 3.2 and BSD utilities):
    - [ ] scheduler: no systemd/`loginctl` → today it falls back to `crontab` (works, but asks for Full Disk Access
      for cron and does not survive sleep well); implement a **launchd agent**
      (`~/Library/LaunchAgents/com.aidd.refresh.plist`, `StartInterval`) as the preferred option on macOS
    - [ ] `flock` does not exist on macOS → a fallback with a `mkdir` lock (or `shlock`/`lockfile`)
    - [ ] `mapfile` needs bash ≥ 4 (macOS ships 3.2) → switch to `while read`, or require `brew install bash` and check
      `BASH_VERSINFO` at the start
    - [ ] `stat -c %s` / `stat -c %a` → `stat -f %z` / `stat -f %Lp` on BSD (a `fsize()`/`fperm()` helper detecting
      `uname`)
    - [ ] `date -d "<ts>" +%s` → `date -j -f ... ` on BSD (a `to_epoch()` helper), or write the epoch to the log
      besides the ISO date
    - [ ] `sed -i` without a suffix in `check --fix` (wsl.conf) is WSL only — ok; the `sed -i.bak && rm` pattern is
      already used in `install.sh`
    - [ ] in-container ssh-agent (U5, only if `fetch: true`): on Docker Desktop macOS the socket is
      `/run/host-services/ssh-auth.sock`, not `$SSH_AUTH_SOCK`
    - [ ] `install-check.sh` section 6: `schedule check` must recognize launchd
      (`launchctl list | grep com.aidd.refresh`)
  - Indexer, compose, Neo4j, Qdrant and MCPs: identical on the 3 platforms (they run in containers) — no change

## Security and operations (its own track)

> A prerequisite for adoption by organizations. Review of 2026-10-12: the stack was born as one dev's local tool and
> exposed more than it should. Order: close what was exposed, take state and credentials off the host, then
> governance.

Done (2026-10-12, validated in the isolated e2e on macOS/Docker Desktop):

- [x] SO1 **Exposure**: every published port on `AIDD_BIND_ADDRESS` (default `127.0.0.1`); the MCPs publish nothing
  — the **`mcp-gateway`** (pinned nginx) serves them on the same ports (3001/3002/3003/3005, `.mcp.json` does not
  change) and returns 403 when the `Host` is not localhost/127.0.0.1/[::1] or when a browser sends an `Origin` from
  another site (DNS rebinding). `atlas` also validates `Host`/`Origin` by itself (MCP SDK). `install-check.sh` checks
  the ports and the refusals
- [x] SO2 **Credentials**: Qdrant requires `QDRANT_API_KEY` (generated by `install.sh`), CORS off; `mcp-git` without
  an ssh key/ssh-agent (local operations; push/pull in the dev's terminal); the refresher's PAT comes in as a file
  secret (`/run/secrets/git-token`), never as an environment variable
- [x] SO3 **Tenant isolation (logical)**: `cypher_readonly` stays offered in both modes (default
  `ATLAS_RAW_CYPHER=on`), but free Cypher is not bound to a tenant — on a multi-tenant atlas whose tenants must not
  see each other (several clients on the same machine), `ATLAS_RAW_CYPHER=off` removes it; Neo4j loads only
  `apoc.version`, `apoc.meta.*` and the pure utilities `apoc.coll/text/map.*` (no `apoc.load`/`export`/`cypher.*` →
  no file/URL access and no dynamic Cypher); Neo4j telemetry off
- [x] SO4 **Supply chain (partial)**: images and packages at fixed versions (neo4j 5.26.30, qdrant v1.19.1, node
  24.21.0, python 3.12.15, nginx 1.28.0, `@cyanheads/git-mcp-server@2.15.3`, `mcp-obsidian@0.8.2`,
  `mcp-proxy@6.7.16`, `mcp-server-qdrant==0.8.1`, `mcp-neo4j-cypher==0.6.0`); obsidian no longer downloads from npm
  on every start
- [x] SO5 **Refresher in a container (D15)**: `aidd daemon` in the compose file (restart unless-stopped, ± 10 %
  jitter, SIGTERM finishes the snapshot in progress, CPU/memory limits, rotating log); `refresh` covers every tenant;
  a **read-only** workspace + a bare mirror per repo (`core/mirror.py`): the dev's clone never receives `FETCH_HEAD`,
  refs or root-owned files; containers as `AIDD_UID`/`AIDD_GID`; the host's `aidd` becomes a thin client (bash 3.2)
  — `schedule install|status|check --fix` manage the container and remove old schedulers; `install.sh` migrates
  `fetch: false` → `true` in the generated manifests
- [x] SO6 **Visible freshness**: `status.json` + healthcheck (`aidd daemon-health`), `RefreshState` per tenant in the
  graph, `atlas_status.refresh.stale` (> 2 intervals without running) and the `scan` skill warns; `install-check`
  checks the age per tenant; snapshot age fixed

Open:

- [ ] SO7 **Strong isolation between tenants**: today Neo4j, Qdrant and the vault are shared (Community has no RBAC
  and no multiple databases) and every tool accepts `tenant`. For whoever serves several organizations on the same
  machine: one stack per tenant (a compose project with its own ports) or, on the server (F3.4), the tenant injected
  by the token
- [ ] SO8 **Authentication on the MCPs** (a per-dev token at the gateway; today the defense is localhost +
  Host/Origin) — ties in with F3.4; careful: the token cannot go in the `.mcp.json` distributed into the repos
- [ ] SO9 **Prompt injection and poisoned memory**: third-party code, Jira and notes enter the context, and what the
  agent writes to the vault/Qdrant comes back as a "convention" in every session. Provenance on the lessons (session,
  repo, sha), human review before something becomes a convention, skills treating that content as data — for memory,
  the mechanism is the **Project knowledge** track (evidence per insight, only a human promotes to `accepted`, K5)
- [ ] SO10 **Full supply chain**: digests (`@sha256`) on the images, a lock with hashes (Python `--require-hashes`,
  npm `package-lock`), SBOM + scan (Trivy/Grype) in CI, Renovate for deliberate bumps; the indexer's `pyproject.toml`
  dependencies are still ranges
- [ ] SO11 **Backup/restore**: the graph and the mirrors can be rebuilt; the Qdrant lessons/insights and the vault
  **cannot** (`docker compose down -v` deletes the lessons). A scheduled Qdrant snapshot + documenting what is
  disposable
- [ ] SO12 **Scale with N devs**: N laptops × M repos every 15 min hit GitHub's secondary rate limit; backoff on a
  fetch failure; a central server (F3) for larger organizations. Mirrors double the repos' disk — GC of mirrors of
  repos that left the workspace
- [x] SO13 **The skill indexes on demand** (2026-10-12): a repo outside the atlas → `scan` runs
  `~/.aidd/aidd refresh --tenant <t> --repos <repo> --wait 300` (the same plan as the refresher: default branch +
  active ones; waits for a refresh in progress; does not count as a refresher round and does no GC; a missing or
  excluded repo is an error with the reason) and, for the branch it is going to work on,
  `aidd index <repo> --ref <branch> --ephemeral`; the skill's `allowed-tools` allows only those two commands (never
  `aidd:*`)
- [ ] SO14 **Validate on WSL and native Linux** (the e2e was on macOS): `AIDD_UID`/workspace permissions (umask 077
  leaves the container without read access), Docker autostart; a real PAT against GitHub (U5)
- [ ] SO15 **Data flow / threat model** for adopters: what leaves the machine (what the LLM reads; embeddings are
  local; telemetry off), where secrets live, what each container can touch. `mcp-neo4j` (debug profile) still has
  write Cypher on `127.0.0.1:3004` — for debugging only

## Phase 1 — Complete micro (multi-language SCIP + hybrid retrieval)

- [ ] F1.1 Integrate SCIP indexers (Go, TS, .NET, Python) into `indexer/`; automatic stack detection by manifest;
  per-repo config (`.aidd/index.yaml`: excludes, connectors)
- [ ] F1.2 SCIP → graph converter (definitions, resolved references, IMPLEMENTS/EXTENDS, types) + a resolver for the
  HTTP layer: a hook in `http_base` (by name by default, SCIP when the snapshot has an index) consulted only at the
  points of indecision that F1.14 recorded as `needs-resolver` — without an index, HTTP stays as today (ADR-002,
  decision 3)
  - Debts due here: TD-001 to TD-004, TD-008, TD-009, TD-012, TD-015, TD-025, TD-028 and TD-035
    (`docs/tech-debt.md`), C# defects `main` has, two Python ones a change of behavior made (H5-D26, and a class a
    function holds), and an override of a package's method no call meets, each with a strict xfail test. SCIP is a possible remedy for them, not a proven one; the first case of TD-001 may be fixed
    in the resolver earlier
- [ ] F1.3 tree-sitter as the fallback for languages without SCIP (Vue SFC, SQL, YAML, templates)
- [ ] F1.4 Incremental indexing (the per-file summary cache is H6's): `git diff` → touched packages → partial re-index; orphan removal per snapshot
  `(repo, ref)`
- [ ] F1.5 Embeddings per **symbol** (signature + docstring + short body) in Qdrant, payload
  `{node_id, repo, ref, kind}`; switch the model to the code one
- [ ] F1.6 Hierarchical summaries via Ollama (file → module → repo) stored in the graph and in Qdrant
- [ ] F1.7 `atlas` MCP: `get_callers`, `get_callees`, `trace_flow(entry_point)`, a hybrid `search(query)` (vector →
  k-hop expansion → rerank)
- [ ] F1.8 `ref` support: index `main` (baseline) and `develop`; nodes/edges with `ref`; queries with an optional
  `ref` (default: develop if it exists)
- [ ] F1.9 Git metrics as attributes: `last_touched`, `churn_90d`, `authors` (hotspots and "who touches this")
- [ ] F1.10 A new `flow` skill: given an entry point (endpoint/handler/job), narrates the micro flow using
  `trace_flow` + snippets
- [ ] F1.11 An `index_runs` table (repo, ref, sha, duration, counts, errors) + an `aidd status` command
- [ ] F1.12 Widen the golden questions to 20; an `aidd eval` script that runs them all and reports recall
- [ ] F1.13 **Large repos (extraction scale)**, absorbed by H6 (`docs/handoffs/H6-extraction-pipeline.md`): grafana (24 thousand files) is killed for memory at 7.7 GB on Docker
  Desktop (corpus v2, 2026-10-15), because `extract_tree` keeps the tree-sitter tree and the text of **every** file
  until the end — only the HTTP extraction needs them; the `Resolver` reads data per file (`namespaces`, `facts`).
  H6 step 0 measured the memory per phase. Grafana peaks at 4.2 GB in a container, and the kept trees account for
  3.7 GB of it. Extracting with each tree dropped peaks at 271 MiB. H6 step 1's prototype, with no tree kept, peaks
  at 2.3 GB: what the reduce and the output hold. Then, in order of cost:
  1. release each file's tree as soon as nothing else reads it — HTTP extraction directory by directory (the
     constants and the scan are already per directory);
  2. batches per module (Go package, `.csproj`, `package.json` workspace), each batch written to the graph, and the
     edges between batches resolved at the end with the symbol table only — the same cut that F1.4 re-indexes and
     that SCIP indexes per project (F1.1);
  3. a per-repo cut in `atlas.yaml` (subfolders as units, excludes) for monorepos where only one part matters.

  A constraint for whoever comes first: the HTTP mount graph (H2b) crosses files — it must work with a summary per
  file (who mounts what, with which prefix), never holding the trees of other directories. **Done when** grafana
  indexes under a fixed memory ceiling (e.g. 2 GB) and, on a medium repo, batched extraction is identical to the
  whole one (the HTTP corpus with `--baseline` gives the diff). Measure along with it the cost of HTTP on repos
  without routes it can read (netbox: 49 s of 107 s with 0 routes and 0 calls in corpus v2; zulip 17 s of 47 s)
- [x] F1.14 **HTTP extractor: what H2 left.** Closed on 2026-10-18, in 11 increments, and the next day came the 12th,
  in the validation of PR #5. Each item ended with a rule with a fixture and a judged corpus, or with a limitation
  recorded in the guide.
  - **Final numbers and where each gap goes:** `docs/corpus-report.md`, "Closing F1.14 and H2".
  - **Rules:** `docs/indexer-evolution.md` §3.
  - **Milestones:** `docs/history.md`.
  - **Scope changes:**
    - the new hold-out moved to after H5 (H2-D21);
    - the framework catalog as data and the `built_bundle` thresholds went to H5;
    - Django stayed out (the portfolio is FastAPI/Flask);
    - test app folders with production names wait for F1.1's per-repo config.
  - **What needs an inferred type** is `needs-resolver`, for F1.2.
- [ ] F1.15 **Regression gates in CI** (H7, `docs/handoffs/H7-regression-gates.md`; slices 1 and 1c in `main`, PR #11
  and PR #22): the method's mechanical checks as gates on every PR (precision ratchet, no win lost, hold-out
  untouched, `0 differ` for refactors, one cause per commit), the diff classified for judgment, baselines published
  on merge, a nightly trend, and a live check on a demo tenant
  - Next slice, decided on 2026-10-27 (H7-D6): automate the judgment of a change of behavior, since a person's check is
    not feasible: the per-site attribution (H5's gap G1: built for every language, H5-D21), the verdict record
    (H7-D2) and each judged case as a test

- [x] F1.16 **A typed call and the overrides it may run** (H5-D27): `CALLS` is the declaration the receiver's type
  gives, in every language. C#'s and Python's type indexes write `EXTENDS` and `IMPLEMENTS` from the bases they read,
  and `CALLS` marks a call that does not dispatch (`super()`, `base.`); `who_calls` and `impact_of` add the callers of
  the methods a method overrides or implements, marked as a dispatch that may happen, and list its overrides. Go's
  embedding promotes and never dispatches; its interface calls are a debt. Seven PRs (H5-D30 to H5-D35):
  `refactor(graph)` #57, `refactor(resolve)` #58, `feat(graph)` #59, `fix(resolve)` #60 for the calls that do not
  dispatch (a Python `super()` reaches what follows the caller's class in each MRO) and the bases of two types of one
  name, `feat(graph)` #61 for `OVERRIDES`, what a dispatching call may run instead as each language says, a
  `feat(graph)` #62 for the receivers a dispatching call and an override hold, so a call on a subclass reaches only the
  overrides an instance of it may run, then `feat(mcp)` #63, which closes it: `who_calls` lists a method's dispatching
  callers and its overrides, and `impact_of` follows a dispatch at any hop. Of netbox's 67 sites that lose an override,
  46 of them `_get_queryset`, the override's `who_calls` reaches all but the one TD-035 holds. It comes before TS's
  step 5 (H5-D29). SCIP (F1.2) may then confirm the `EXTENDS` read from tree-sitter, or replace it

**Phase exit:** any workspace repo indexable with 1 command; `scan` and `flow` answering with facts from the graph.

## Phase 2 — Complete macro (contract linker + governance)

- [ ] F2.1 OpenAPI connector: specs → `HttpEndpoint`; routes extracted from the code reconciled with the spec
  (divergence = alert)
- [ ] F2.2 Messaging connector: topics/queues in constants, config and env (Kafka, RabbitMQ, SQS/SNS) →
  `PUBLISHES`/`SUBSCRIBES`; event schemas when they exist
- [ ] F2.3 Infra connector: `docker-compose`, k8s/Helm, gateway → resolve `ENV_VAR → URL → repo` to link outbound
  HTTP calls to the target repo
- [ ] F2.4 Database connector: migrations/ORM → `DbTable`, `READS/WRITES`; tables shared between repos = an implicit
  macro edge
- [ ] F2.5 Confidence on the edges (`exact | heuristic | llm`) + `evidence`; an LLM pass only on the ambiguous ones;
  the result becomes a review note in Obsidian (`<tenant>/_links-review.md`)
- [ ] F2.6 `atlas` MCP: transitive cross-repo `impact_analysis(symbol|endpoint|topic)`, `repo_dependencies(repo)`,
  `workspace_map(tenant)`
- [ ] F2.7 A new `impact` skill: given a target, lists the affected repos/flows with confidence and evidence
- [ ] F2.8 Visualization: export of the subgraph to Obsidian (canvas/notes with wikilinks) or static HTML — human
  reading of the macro level
- [ ] F2.9 Macro golden questions (≥ 15) + `aidd eval` covering micro and macro

**Phase exit:** a queryable workspace map; cross-repo impact with evidence.

## Phase 3 — Central and continuous (the end goal)

- [ ] F3.1 A central server (Neo4j + Qdrant + MCPs) with backup; a compose "server profile"
- [ ] F3.2 A CI job per repo: on every merge to `main`/`develop` → `aidd index` → push to the central server (a
  self-hosted runner with a SCIP cache)
- [ ] F3.3 A scheduled/event-driven linker on the central server; a report of new edges and divergences
- [ ] F3.4 MCP auth per tenant (a token per dev/team behind a reverse proxy); the tenant filter injected, never
  trusted to the client
- [ ] F3.5 A coverage/freshness dashboard: indexed repos, index age, % of macro edges by confidence
- [ ] F3.6 Retention: keep N snapshots per `(repo, ref)`; GC of dead refs
- [ ] F3.7 `install.sh` points `.mcp.json` at the central server when configured; local stays as the offline fallback

---

## Parallel track — Skills and the development flow

The target chain (each skill consumes the graph through MCP and writes to Obsidian/Qdrant):

```
scan ──► flow / impact ──► refine-business ──► refine-tech ──► implement ──► review
 (facts)   (micro/macro)     (card + context)    (tech spec)      (harness)    (senior)
```

- [x] S0 `scan` v1 with a vault per project (`<tenant>/knowledge/<repo>/<repo>.md`) and `refine-business` v1 (Jira →
  candidates through Qdrant → "what to do" per project → loop → `<tenant>/cards/<card>.md`)
- [x] S0.1 *(2026-10-12: `scan` documents `cards/`, which is where `refine-business` writes)* Align the vault layout:
  `scan` documented `refine-business/` but `refine-business` writes to `cards/` — pick one and fix both SKILL.md
- [ ] S1 `scan` v2: reads from the graph, falls back to the current flow; saves conventions with
  `source: graph|llm`
- [ ] S2 `flow`: entry point → a narrative of the micro flow (F1.10)
- [ ] S3 `impact`: target → affected repos/flows (F2.7)
- [ ] S4 `refine-business` v2 — where the graph fits into the existing skill (without changing the trigger):
  - Step 2 (coverage): besides "are there conventions in Qdrant?", check "is it indexed in the atlas?"
    (`atlas.repo_map`) and suggest `aidd index`
  - Step 4 (affected projects): today it is only a vector search over the convention summaries; it becomes hybrid —
    the vector finds candidate symbols/endpoints → `impact_analysis`/`who_consumes` expands to the repos linked by
    contract. Candidates gain `confidence` + `evidence`
  - Step 5 ("what to do"): cite the micro flow (`trace_flow`) and the macro edges that justify coordinating between
    projects
  - Step 7: the card's note starts to include the **delimited area of work** (repos, modules, entry symbols) — it is
    `refine-tech`'s input
- [ ] S5 `refine-tech`: from the delimited area, zoom in with `flow`/`get_callers`; produces a technical spec (files,
  contracts, tests, risks, ADRs); explicit human validation before moving on. The spec has a section called
  "Contracts, boundaries and proof", with `docs/design.md`'s questions asked of the project: what it already has that
  answers the card (a contract, a module, a convention `scan` found), where each piece of the change belongs, and what
  proves it
- [ ] S6 `implement`: runs the spec on the chosen orchestrator (harness: tests, coverage, lessons → `record_insight`,
  the **Project knowledge** track)
- [ ] S7 `review`: injected context (spec + diff + coverage + the graph's conventions + the area's
  `accepted`/`enforced` insights) → a senior opinion, which asks `docs/design.md`'s questions of the diff; PR
- [ ] S8 Define a common contract between skills (frontmatter + the format of the output note) so that one's output
  is the next one's input — the knowledge part (the project index + the insight note) is K1
- [ ] S9 (handoff H3) Measure the effect of the atlas and of knowledge on AI-assisted development — tokens, time,
  completeness and defects, on real tasks within a repo and across repos, with and without the stack
  (`docs/handoffs/H3-ai-dev-efficiency.md`). After H2b, in another process

## Project knowledge (its own track)

> Each project has an **entry point** in the vault (the index `scan` creates) and a **knowledge base** that the
> process stages feed and consult: what shows up in code review, Sonar, security tools, incidents and decisions
> becomes a filtered insight, so the problem does not repeat and the review already knows what to look at. It is not
> a skill (D16): it is a stack mechanism that `scan`, `refine-business`, `refine-tech` and `implement` use through the
> same contract. The skill does the part that needs judgment (what is worth recording, with what evidence); the stack
> does the deterministic part (dedup, counting, note, index, Qdrant, status rules).
>
> What the process **requires** (minimum coverage, harness attempts, when to ask for an ADR, when an insight becomes
> `recurring`) lives in `policy.yaml` (D17), next to `atlas.yaml`: `atlas.yaml` says how to read the code,
> `policy.yaml` says what the process requires. `scan` describes the project; policy is a human decision and is not
> discovered.

Vault layout:

```
<tenant>/knowledge/
├── <repo>/
│   ├── <repo>.md            index: scan's fixed sections + a generated knowledge block
│   └── insights/<slug>.md   one insight per note (frontmatter)
└── shared/insights/         what holds for several of the tenant's repos
```

An insight's lifecycle:

```
observed ──► recurring ──► accepted ──────────► enforced
(once)       (N times)     (a human approved:   (became a checkable rule:
                            the agent follows)   violations / lint)
        └──────────────► archived (discarded, or no occurrence for a long time)
```

- [x] K1 *(2026-10-13: `docs/knowledge-contract.md`, contract v1)* **The vault contract** (closes S8 for knowledge):
  the index skeleton — `scan`'s fixed sections (including the repo's effective policy, read-only: it is changed in
  `policy.yaml`) + a block between `<!-- aidd:knowledge:start -->`/`<!-- aidd:knowledge:end -->`, generated from the
  notes and never edited by hand; the insight note format — frontmatter `topic` (a controlled vocabulary:
  `architecture`, `review`, `quality`, `security`, `incident`, `decision`, `business`; extensible through a topic
  registry, not free text — avoids `security`/`segurança`/`sec`), `status`, `severity`, `scope` (`repo`|`shared`),
  `occurrences`, `first_seen`/`last_seen`, `evidence[]` (PR, file:line, sha, tool, session), `applies_to` (files,
  roles, symbols); payload in Qdrant `{project, type: insight, topic, status}`
- [x] K1.1 *(2026-10-13: `core/policy.py`, `aidd policy show|check`, `install.sh` creates it from
  `indexer/policy.example.yaml`, `install-check` validates it)* **`policy.yaml`** in `~/.aidd` (D17), with layers like
  `atlas.yaml`: built-in defaults → tenant → area → repo (`overrides`), each level overriding only what it declares.
  Initial content: `coverage` (`min`, `new_code_min`), `harness` (`max_attempts`), `review` (`spec_approval`,
  `adr_when`), `knowledge` (`recurring_after`, `archive_after_days`) — everything that would be a fixed number in the
  code. Validated with a clear error (like `atlas.yaml`'s `ConfigError`); `install.sh` creates a commented example;
  `aidd policy show <repo>` prints the effective policy with the origin of each value
- [x] K2 *(2026-10-13: `aidd_indexer/knowledge/`, the `mcp-knowledge` service on the gateway's port 3006)* **The
  `knowledge` service** in the compose file (the same image as the indexer, behind `mcp-gateway`; the only one that
  writes knowledge to the vault and to Qdrant — the atlas stays read-only). Three tools:
  - `policy_for(repo)` → the effective policy, already combined, with the origin of each value
    (default/tenant/area/repo) — the skills do not merge the layers
  - `insights_for(repo, files?, roles?, topic?)` → `accepted`/`enforced` as rules, `observed`/`recurring` as context
    (labeled: data, not instructions)
  - `record_insight(repo, topic, summary, evidence, applies_to, severity)` → dedup (Qdrant by similarity + the same
    topic), increments or creates the note, `recurring` on reaching `knowledge.recurring_after` occurrences (policy;
    default 3), rebuilds the index block, mirrors to Qdrant; no tool promotes to `accepted`
  - `refresh_index(repo)` → rewrites only the `aidd:knowledge` block from the notes (`scan` calls it when it finishes
    the page; a new page is born with what was recorded before)
  - Tests: dedup, rebuilding the index while preserving `scan`'s sections, idempotency
- [x] K3 *(2026-10-13: the skill rewritten and validated on the real install — migration, repetition in another
  language, a page from scratch)* `scan` generates the index skeleton and shows the knowledge block; the end-of-task
  lesson (today a direct `qdrant-store`) becomes `record_insight`
- [ ] K4 *(with the `refine-business` review)* `refine-business` adopts the contract: consults the affected projects'
  incidents/decisions, records the card's business decisions. `refine-tech` (S5) and `implement` (S6) are born with
  it: the area's known risks in the spec; `accepted`/`enforced` as a checklist before coding and before the PR
- [ ] K5 *(born with `refine-tech`, S5)* **Promotion with a human inside the process**: `refine-tech` shows the
  `observed`/`recurring` items that touch the delimited area ("it showed up 3×, does it become a rule?") and records
  the approval (`accepted`, who and when); editing the frontmatter in Obsidian counts the same. Closes the memory part
  of SO9
- [ ] K6 *(born with `implement`, S6)* Sources inside `implement`, where the reason for an error shows up: (1) **a
  review rejection** (the senior opinion that sends it back to execution — the reason is the insight); (2) **a
  harness escalation** (`harness.max_attempts` exhausted: what the model could not fix by itself, and why); (3) **PR
  review comments** while handling the feedback (`gh`). In all of them, record only what is not obvious
- [ ] K7 *(when the tenants have a scanner in CI)* `aidd ingest <file.sarif>` (Semgrep, CodeQL, Trivy, Snyk): groups
  findings by rule × repo, writes `observed` with a count and evidence — the raw data stays in the tool; runs in CI or
  through the refresher. Sonar through its API later
- [ ] K8 *(after Phase 1)* `enforced`: an insight checkable on the graph becomes a convention rule and shows up in
  `violations`; what is not checkable stays as a checklist
- [ ] K9 *(with a volume of insights; backup together with SO11)* Aging and backup: a `last_seen` older than
  `knowledge.archive_after_days` with no new occurrences loses weight and goes to `archived`; the notes and the
  insights collection cannot be rebuilt from the code → they go into the backup (SO11)
- [ ] K10 Policy inside the repo (`.aidd/policy.yaml`, read from the mirror on the default branch): in organizations,
  the policy in `~/.aidd` is each dev's, and two devs may work with different thresholds; in the repo it holds the
  same for everyone and only changes through a PR (human review). A layer above the repo's `overrides`; after K1.1 is
  proven

## Publishing and documentation (its own track)

> The repo is public and the README has one line. This track gives both repositories — aidd-stack and the indexer,
> which moves to its own repo — documentation for newcomers, in English, Portuguese, Spanish and Chinese. Decisions,
> the boundary between the repos and the order: `docs/handoffs/H4-public-docs.md`.

- [ ] P0 Recycle the working docs (H4 step 0, asked for on 2026-10-18): the current truth separated from history; an
  `AGENTS.md` at the root as the entry point for a contributor and their AI; the ROADMAP log condensed into
  `docs/history.md`; the decisions distilled into `docs/decisions.md`; the corpus report with only the method, the
  current baseline and the gaps; from ~600 KB to at most ~150 KB. Phase 0a done on 2026-10-19, with every doc in
  English (H4-D1); phase 0b (the extractor guide, rewritten in English) after H5
- [ ] P1 H4's decisions (H4-D1…D12, the name of the indexer's repo, reviewers per language) and a sketch of the docs
  architecture — can run in parallel with H2b
- [ ] P2 The indexer in its own repo: `filter-repo` with an audited history, a multi-architecture image on GHCR,
  `knowledge` and policy in aidd-stack, the schema applied by the indexer; regression = tests, an identical corpus
  and a clean aidd-stack install with the published image; `cli.py` brought to the shape targets, the one exception
  H5 left (H5-D6). After the H2b merge
- [ ] P3 English content for both repos (README + `docs/en/`), validated by someone who has never seen the project
- [ ] P3.1 The contributor path (H4.1, `docs/handoffs/H4.1-contributor-path.md`): `CONTRIBUTING.md`, playbooks per
  contribution type, the method explained, PR and issue templates, the method's checks in CI, and an acceptance test
  in which a fresh agent re-enacts past increments and follows the method on its own
- [ ] P4 Languages: a glossary, a style guide, `i18n_check.py` in CI; translations per tier into pt-BR, es and zh-CN
- [ ] P5 Visual assets (manifest `docs/assets/README.md`), community files, GitHub settings and the first release of
  both repos
- [ ] P6 *(optional)* A docs site, when navigation calls for it

## Pending decisions

The decided ones (D1, D3, D6–D17, and D5 through H4-D1) are in `docs/decisions.md`.

- [ ] D2 Execution orchestrator (Phase S6): Claude Code (we already use skills in that format) vs Cline/Roo Code
  (VS Code, MCP, local models) vs Goose/Aider (CLI)
- [ ] D4 Minimum local model for agentic tasks with tool calling (evaluate Qwen-Coder ≥ 30B); 7B/14B stay for
  summaries and classification only
