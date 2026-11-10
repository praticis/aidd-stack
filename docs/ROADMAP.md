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
  hold-out and the micro graph against `main`. `tests`, `gates` and `debts` are required to merge into `main`. Since
  slice 1c (PR #22), `tests` also runs the MCP and the graph writer against a throwaway Neo4j.
- **Technical debts:** `docs/tech-debt.md` lists the known defects that do not block, each with the phase it is due in
  and a strict xfail test that fails the suite when it is fixed.
- **In progress:**
  - H5 (`docs/handoffs/H5-indexer-refactor.md`, "State"; each PR's story is in `docs/history.md`):
    - merged: steps 0–2, 4 and 7–9 (PR #7, H5-D8); step 5, the `TypeIndex`, in Go, C#, Python and TS (H5-D10, H5-D29; #85
      the last), each validated on a live install and judged with the per-site attribution (H5-D21, G2 #56); F1.16 (#57
      to #63); step 12 for the conventions, the corpus runner, the MCP's tools and the refresher (#74 to #78);
    - the debts step 5 leaves are in `docs/tech-debt.md` (TD-001 to TD-073), each with a strict xfail case, but two with none yet, and the ones
      it closed carry their PR there: TD-005 to TD-007, TD-010, TD-011, TD-013, TD-014, TD-016 to TD-022, TD-027, TD-033,
      TD-034, TD-067, TD-068 and TD-070 to TD-072 are due in `fix(csharp)` PRs before F1.2; Go's calls on an interface, which reach no method of the repo
      unless a single implementer declares it, TD-029, a bare name that reaches a method, TD-065, and a package-qualified call
      whose name two packages declare, TD-066, are due in `fix(go)` PRs before F1.2; a call found by name that reaches a function
      of another language, TD-064, is due in a `fix(resolve)` PR before F1.2; an identifier read as written, where Python names it
      by its NFKC form, TD-069, is due in a `fix(python)` PR before F1.2; three forms of a declaration
      the reading still misses, TD-048, are due in a `fix(conventions)` PR before F1.2; a workspace package whose source a
      condition only a tool of the repo enables names, TD-052, a member of an interface whose function type a name or
      `typeof` gives, TD-053, a member of an alias's object type below more wrappers than the query reaches, TD-055, a class
      field or a parameter property typed as a function, TD-056, a class a factory call makes, TD-058, a module with a
      declaration file beside its JS, TD-061, a wrapper behind an interface, TD-062, and a call on `super`, TD-063, are due
      in `fix(typescript)` PRs before F1.2; what a type checker answers and the reading does not, TD-057, TD-059 and
      TD-060 (H5-D52), are due in F1.2; two debts of the core's architecture, the syntax of each language it holds,
      TD-023, and the names of frameworks and client libraries it holds, TD-024, a gap of Python's, Django's model managers
      found by name, TD-026, and a C# call on an interface that reaches its single implementer twice, TD-036, are due in an
      H5 step: 6 and 12 for TD-023, 6 for TD-024, TD-026 and TD-036;
    - next: the `fix` PRs of the debts due before F1.2, by scope (H5-D19); then step 6 (recognizers and the catalog; C#,
      Go, Python, TS: H5-D20, with the core's HTTP modules: H5-D44), step 12's last PR (the pipeline's `extract` and
      `resolve`), then 10 and 11;
  - H6 (`docs/handoffs/H6-extraction-pipeline.md`): the extraction as a parallel map, a reduce and a per-file cache,
    designed now, plugged in after H5. Steps 0 to 2 are done (the measurement and the prototypes are "H6 baseline" and
    "H6 step 1" in the corpus report; B keyed per package, H6-D5, and batches of whole packages, H6-D6); the resolver's
    quadratic cost in Go and C# is fixed (PR #9); ADR-004 to ADR-006 are accepted;
  - H7 (`docs/handoffs/H7-regression-gates.md`): slices 1 and 1c are in `main`; the next slices are open, and the judgment is to be automated (H7-D6).
  - H8 (`docs/handoffs/H8-independent-review.md`): the independent reviewer, a read-only adversary for plans and diffs,
    designed and used in three rounds, five reviews (H5-D50 and H5-D51); its script is in `indexer/scripts/review/`
    (slice 1), its stage hooks and its record are open.
- **The order up to SCIP (H5-D1, H6-D1):** design H6 → H5 (the indexer refactor, `docs/handoffs/H5-indexer-refactor.md`,
  with no behavior change, built toward H6's design) → plug H6 in → the new hold-out, measured once, and its handoff
  (H2-D21) → P2 (the indexer in its own repo) → SCIP (F1.1, F1.2).
- **Active handoffs:** H3 (AI dev efficiency), H4 (public docs and the indexer in its own repo), H4.1 (the
  contributor path), H5, H6, H7 and H8. Closed: H1 and H2.
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
- A defect a change opens or widens is **fixed in that change** when that is viable; what is not, and what `main`
  already has, is a **debt** (`docs/tech-debt.md`), not a note: it has a strict xfail test, so the suite fails when it
  is fixed. Every phase ends with its debts settled, or moved by the author.
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

_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Compose validation checklist (validated 2026-09-10/11; `install-check.sh` covers items 2–7 on every upgrade)"._

---

## Phase 0 — Foundation (end-to-end PoC, 2 repos)

_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Phase 0 — Foundation (end-to-end PoC, 2 repos)"._

## Continuous update process (its own track — VERY important)

_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Continuous update process (its own track — VERY important)"._

- [x] U1 **Service credential** (D13): a **read-only** PAT in `~/.aidd/secrets/git-token` (600), collected in step 6
  of `install.sh`; the wrapper uses it through `GIT_ASKPASS` and rewrites ssh→https remotes only for the fetch. Your
  personal key stays out of the scheduler. Validated: `fetch: ok (service)` on the 6 repos. Note: fine-grained needs
  admin approval in the org — classic (scope `repo`, short expiry) works as a bridge; a **GitHub App** is the target
  for the server (F1)
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Continuous update process (its own track — VERY important)"._
- [ ] U4 **Event trigger (F3)**: a webhook/CI on a push to a protected branch → `aidd index <repo> --ref <branch>`;
  replaces the scheduler on the central server
- [x] U5 **In-container fetch**: became the default path with the refresher (D15) — a mirror per repo, the PAT as a
  file through `git-askpass.sh`. Validated with a local remote in the e2e; **still to validate against GitHub with a
  real PAT**
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Continuous update process (its own track — VERY important)"._

## Security and operations (its own track)

> A prerequisite for adoption by organizations. Review of 2026-10-12: the stack was born as one dev's local tool and
> exposed more than it should. Order: close what was exposed, take state and credentials off the host, then
> governance.

_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Security and operations (its own track)"._

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
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Security and operations (its own track)"._
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
  - Debts due here: TD-001 to TD-004, TD-008, TD-009, TD-012, TD-015, TD-025, TD-028, TD-035, TD-050, TD-051,
    TD-054, TD-057, TD-059, TD-060 and TD-073 (`docs/tech-debt.md`), C# defects `main` has, two Python ones a change of behavior made (H5-D26, and a class a
    function holds), an override of a package's method no call meets, a workspace package whose entry is a build
    no project the config references emits, an HTTP path that reads a field of an instance as a constant, a
    function an object literal holds or a member of an object type no declaration names, which need a symbol the
    schema does not have, and three answers of a type checker (a generic's argument an alias gives, a receiver a type guard
    narrows, an overloaded function's result), each with a strict xfail test, and the share of TS calls that go by name, which a case cannot state. SCIP is a possible remedy for them, not a proven one; the first case of TD-001 may be fixed
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
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Phase 1 — Complete micro (multi-language SCIP + hybrid retrieval)"._
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
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Phase 1 — Complete micro (multi-language SCIP + hybrid retrieval)"._

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

_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Project knowledge (its own track)"._
- [x] K1 *(2026-10-13: `docs/knowledge-contract.md`, contract v1)* **The vault contract** (closes S8 for knowledge):
_The detail of this section is in git: `git show before-roadmap-history-condensation:docs/ROADMAP.md`, section "Project knowledge (its own track)"._
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
  same for everyone and only changes through a PR (human review). A layer above the repo's `overrides`; after `policy.yaml` is
  proven

## Publishing and documentation (its own track)

> The repo is public and the README has one line. This track gives both repositories — aidd-stack and the indexer,
> which moves to its own repo — documentation for newcomers, in English, Portuguese, Spanish and Chinese. Decisions,
> the boundary between the repos and the order: `docs/handoffs/H4-public-docs.md`.

- [ ] P0 Recycle the working docs (H4 step 0, asked for on 2026-10-18): the current truth separated from history; an
  `AGENTS.md` at the root as the entry point for a contributor and their AI; the ROADMAP log condensed into
  `docs/history.md`; the decisions distilled into `docs/decisions.md`; the corpus report with only the method, the
  current baseline and the gaps; from ~600 KB to a ceiling per growth file (`indexer/scripts/checks/docs_ceilings.txt`), with no total. Phase 0a done on 2026-10-19, with every doc in
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
