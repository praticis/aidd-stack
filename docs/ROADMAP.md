# The Atlas — roadmap

> A living document. Mark `[x]` when done. Update the **Where we are** section every session so that any agent or
> person picks up from the right point. The text this file had before it was condensed, Phase 0 and its `F0.x` items
> among it, is in git (`git show before-roadmap-history-condensation:docs/ROADMAP.md`), and before it was reorganized
> (`git show before-roadmap-reorganization:docs/ROADMAP.md`).

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
    - the debts step 5 leaves are in `docs/tech-debt.md` (TD-001 to TD-073), each with a strict xfail case, but two with
      none yet, and the ones it closed carry their PR there; each open one's Due cell says where it is due;
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
    (slice 1), and its record is open.
- **The order up to SCIP (H5-D1, H6-D1):** design H6 → H5 (the indexer refactor, `docs/handoffs/H5-indexer-refactor.md`,
  with no behavior change, built toward H6's design) → plug H6 in → the new hold-out, measured once, and its handoff
  (H2-D21) → SCIP (F1.1, F1.2).
- **Handoffs:** one row each in `docs/handoffs/README.md`, with its state and what it waits for. H10, the
  reorganization of this roadmap, is under way: until its last pull request merges, no other one enters `main`.

## Principles (non-negotiable)

- The Atlas is **orchestrator-independent**: MCP only.
- **Extraction is deterministic:** no model writes a record of the graph. What a model derives from the records (an
  embedding, a ranking) is an index beside them: rebuilt from them, never read by the extraction, never part of a
  snapshot's comparison.
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
| `atlas` MCP | our own FastMCP (Python) | MIT |
| CI | GitHub Actions | free |

---

## Continuous update process (its own track — VERY important)

- [x] U1 **Service credential** (D13): a **read-only** PAT in `~/.aidd/secrets/git-token` (600), collected in step 6
  of `install.sh`; the wrapper uses it through `GIT_ASKPASS` and rewrites ssh→https remotes only for the fetch. Your
  personal key stays out of the scheduler. Validated: `fetch: ok (service)` on the 6 repos. Note: fine-grained needs
  admin approval in the org — classic (scope `repo`, short expiry) works as a bridge; a **GitHub App** is the target
  for the server (F1)
- [ ] U4 **Event trigger (F3)**: a webhook/CI on a push to a protected branch → `aidd index <repo> --ref <branch>`;
  replaces the scheduler on the central server
- [x] U5 **In-container fetch**: became the default path with the refresher (D15) — a mirror per repo, the PAT as a
  file through `git-askpass.sh`. Validated with a local remote in the e2e; **still to validate against GitHub with a
  real PAT**

## Security and operations (its own track)

> A prerequisite for adoption by organizations. Review of 2026-10-12: the stack was born as one dev's local tool and
> exposed more than it should. Order: close what was exposed, take state and credentials off the host, then
> governance.

Open:

- [ ] SO7 **Strong isolation between tenants**: today one Neo4j holds every tenant (Community has no RBAC and no
  multiple databases) and every `atlas` tool accepts `tenant`. For whoever serves several organizations on the same
  machine: one Atlas stack per tenant (a compose project with its own ports) or, on the server (F3.4), the tenant
  injected by the token
- [ ] SO8 **Authentication on the `atlas` MCP** (a per-dev token at the gateway; today the defense is localhost +
  Host/Origin) — ties in with F3.4; careful: the token cannot go in the MCP configuration the installer writes into
  the repos
- [ ] SO9 **Prompt injection through the graph's answers**: third-party code reaches the agent as text it did not
  write (a symbol's `doc` and `signature`, a violation's `message`, the docstrings `find_symbol` matches). Name the
  answer fields that carry code text, so a consumer treats them as data; never filter or rewrite that text by heuristic
- [ ] SO10 **Full supply chain**: digests (`@sha256`) on the images, a lock with hashes (Python `--require-hashes`,
  npm `package-lock`), SBOM + scan (Trivy/Grype) in CI, Renovate for deliberate bumps; the indexer's `pyproject.toml`
  dependencies are still ranges
- [ ] SO11 **What is disposable**: once only Neo4j and the mirrors hold state, everything the Atlas keeps is rebuilt
  from the repositories; say so, and say what the host must keep (`atlas.yaml`, `.env`, the read-only token)
- [ ] SO12 **Scale with N devs**: N laptops × M repos every 15 min hit GitHub's secondary rate limit; backoff on a
  fetch failure; a central server (F3) for larger organizations. Mirrors double the repos' disk — GC of mirrors of
  repos that left the workspace
- [ ] SO14 **Validate on WSL and native Linux** (the e2e was on macOS): `AIDD_UID`/workspace permissions (umask 077
  leaves the container without read access), Docker autostart; a real PAT against GitHub (U5)
- [ ] SO15 **Data flow / threat model** for adopters: what leaves the machine (what the LLM reads; telemetry off),
  where secrets live, what each container of the Atlas can touch. `mcp-neo4j` (debug profile) still has write Cypher
  on `127.0.0.1:3004` — for debugging only

## Phase 1 — Complete micro (multi-language SCIP)

- [ ] F1.1 Integrate SCIP indexers (Go, TS, .NET, Python) into `indexer/`; automatic stack detection by manifest;
  per-repo config (`.aidd/index.yaml`: excludes, connectors)
- [ ] F1.2 SCIP → graph converter (definitions, resolved references, IMPLEMENTS/EXTENDS, types) + a resolver for the
  HTTP layer: a hook in `http_base` (by name by default, SCIP when the snapshot has an index) consulted only at the
  points of indecision that F1.14 recorded as `needs-resolver` — without an index, HTTP stays as today (ADR-002,
  decision 3)
  - The debts due here are the open rows of `docs/tech-debt.md` whose Due is F1.2 or a `fix(<scope>)` PR before F1.2;
    F1.2 is not ticked while one is open. SCIP is a possible remedy for the ones due in F1.2, not a proven one; the first
    case of TD-001 may be fixed in the resolver earlier
- [ ] F1.3 tree-sitter as the fallback for languages without SCIP (Vue SFC, SQL, YAML, templates)
- [ ] F1.4 Incremental indexing (the per-file summary cache is H6's): `git diff` → touched packages → partial re-index; orphan removal per snapshot
  `(repo, ref)`
- [ ] F1.5 Semantic search over the symbols, not decided: a reference first (search questions with an expected list,
  scored against `find_symbol` with `match="fuzzy"` as the baseline), whose result decides whether it is built; if it
  is, Neo4j's vector index is the candidate store, and the `search(query)` once planned in F1.7 is this item's
- [ ] F1.7 `atlas` MCP: `trace_flow(entry_point)`, the micro flow from an entry point (callers and callees already
  answer through `who_calls` and `symbol_context`)
- [ ] F1.8 `ref` support: index `main` (baseline) and `develop`; nodes/edges with `ref`; queries with an optional
  `ref` (default: develop if it exists)
- [ ] F1.9 Git metrics as attributes: `last_touched`, `churn_90d`, `authors` (hotspots and "who touches this")
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

**Phase exit:** any workspace repo indexable with 1 command; the `atlas` MCP answering the golden questions with facts
from the graph.

## Phase 2 — Complete macro (contract linker + governance)

- [ ] F2.1 OpenAPI connector: specs → `HttpEndpoint`; routes extracted from the code reconciled with the spec
  (divergence = alert)
- [ ] F2.2 Messaging connector: topics/queues in constants, config and env (Kafka, RabbitMQ, SQS/SNS) →
  `PUBLISHES`/`SUBSCRIBES`; event schemas when they exist
- [ ] F2.3 Infra connector: `docker-compose`, k8s/Helm, gateway → resolve `ENV_VAR → URL → repo` to link outbound
  HTTP calls to the target repo
- [ ] F2.4 Database connector: migrations/ORM → `DbTable`, `READS/WRITES`; tables shared between repos = an implicit
  macro edge
- [ ] F2.5 Confidence and evidence on the macro edges F2.1 to F2.4 add, as `CONSUMES` has them (`exact`, `suffix`, and
  the candidates listed when the linker cannot decide); no level is decided by a model
- [ ] F2.6 `atlas` MCP: `workspace_map(tenant)`, and the cross-repo impact of an endpoint or a topic, as `impact_of`
  gives a symbol's (`repo_map` already gives a repo's dependencies); Go's `who_calls` across repositories
- [ ] F2.8 Visualization: export of the subgraph as static HTML or as data — human reading of the macro level
- [ ] F2.9 Macro golden questions (≥ 15) + `aidd eval` covering micro and macro

**Phase exit:** a queryable workspace map; cross-repo impact with evidence.

## Phase 3 — Central and continuous (the end goal)

- [ ] F3.1 A central server (Neo4j and the `atlas` MCP) with backup; a compose "server profile"
- [ ] F3.2 A CI job per repo: on every merge to `main`/`develop` → `aidd index` → push to the central server (a
  self-hosted runner with a SCIP cache)
- [ ] F3.3 A scheduled/event-driven linker on the central server; a report of new edges and divergences
- [ ] F3.4 MCP auth per tenant (a token per dev/team behind a reverse proxy); the tenant filter injected, never
  trusted to the client
- [ ] F3.5 A coverage/freshness dashboard: indexed repos, index age, % of macro edges by confidence
- [ ] F3.6 Retention: keep N snapshots per `(repo, ref)`; GC of dead refs
- [ ] F3.7 The installer points the `atlas` entry of a repository's MCP configuration at the central server when
  configured; local stays as the offline fallback

---

## Publishing and documentation (its own track)

> The repository is public. This track gives it documentation for newcomers, in English, Portuguese, Spanish and
> Chinese. Decisions and the order: `docs/handoffs/H4-public-docs.md`.

- [ ] P0 Recycle the working docs (H4 step 0, asked for on 2026-10-18): the current truth separated from history; an
  `AGENTS.md` at the root as the entry point for a contributor and their AI; the ROADMAP log condensed into
  `docs/history.md`; the decisions distilled into `docs/decisions.md`; the corpus report with only the method, the
  current baseline and the gaps; from ~600 KB to a ceiling per growth file (`indexer/scripts/checks/docs_ceilings.txt`), with no total. Phase 0a done on 2026-10-19, with every doc in
  English (H4-D1); phase 0b (the extractor guide, rewritten in English) after H5
- [ ] P1 Redecide H4 with the premise (H10-D1): the H4 proposals that H10-D1 and H11-D1 left open, for the one
  repository, reviewers per language, and a sketch of the docs architecture
- [ ] P2 **The Atlas in its own repository**, named `aidd-atlas` (H10-D1), after the release of the reduced Atlas:
  whether it is a new repository born from one commit with the reduced tree or this one renamed, where the history
  stays, how the new tree is proven, and, if it is a new one, how the install entry passes to it are its design. This
  repository is never deleted or made private
- [ ] P3 English content for the repository (README + `docs/en/`), validated by someone who has never seen the project
- [ ] P3.1 The contributor path (H4.1, `docs/handoffs/H4.1-contributor-path.md`): `CONTRIBUTING.md`, playbooks per
  contribution type, the method explained, PR and issue templates, the method's checks in CI, and an acceptance test
  in which a fresh agent re-enacts past increments and follows the method on its own
- [ ] P4 Languages: a glossary, a style guide, `i18n_check.py` in CI; translations per tier into pt-BR, es and zh-CN
- [ ] P5 Visual assets (manifest `docs/assets/README.md`), community files and GitHub settings for the repository; its
  releases follow H11-D1
- [ ] P6 *(optional)* A docs site, when navigation calls for it

## Candidates

Ideas with no item yet:

- a handoff of its own on code quality gates. Until then the shape ratchet holds (H5-D9);
- `dispatch` for validators reached by the bus pipeline (`SendAsync(cmd)` → `AbstractValidator<cmd>`);
- re-run the .NET Q4 with dispatch.

## Pending decisions

The decided ones (D1, D3, D6–D15, and D5 through H4-D1) are in `docs/decisions.md`; D16 and D17 are superseded by
H10-D1. No decision of this roadmap's own is pending. F1.5 waits for one, and the open decisions of a handoff are in
it: H4's proposals (P1), H7-D2, H7-D4 and H8-D5.

## Left this roadmap

This repository keeps only the Atlas (H10-D1). The process planned around it left, and what was done of it stays here
as the record:

- [x] S0 `scan` v1 with a vault per project (`<tenant>/knowledge/<repo>/<repo>.md`) and `refine-business` v1 (Jira →
  candidates through Qdrant → "what to do" per project → loop → `<tenant>/cards/<card>.md`)
- [x] S0.1 *(2026-10-12: `scan` documents `cards/`, which is where `refine-business` writes)* Align the vault layout:
  `scan` documented `refine-business/` but `refine-business` writes to `cards/` — pick one and fix both SKILL.md
- [x] K1 *(2026-10-13: `docs/knowledge-contract.md`, contract v1)* **The vault contract** (closes S8 for knowledge):

| Id | What it was | Where it went |
|---|---|---|
| S1 | `scan` v2, graph first | its process half moved to the author's private process roadmap; the half that teaches the graph: replaced by F1.22 |
| S2 | a `flow` skill | withdrawn: the narration is the consumer's, and the tool is F1.7's `trace_flow` |
| S3 | an `impact` skill | withdrawn: the consumer composes it, and `impact_of` answers it |
| S4 | `refine-business` v2 | moved to the author's private process roadmap |
| S5 | `refine-tech` | moved to the author's private process roadmap |
| S6 | `implement` | moved to the author's private process roadmap |
| S7 | `review` | moved to the author's private process roadmap |
| S8 | a contract between skills | moved to the author's private process roadmap |
| S9 | the Atlas's effect on AI work | moved to the author's private process roadmap |
| K4 | `refine-business` adopts the knowledge contract | moved to the author's private process roadmap |
| K5 | a human promotes an insight | moved to the author's private process roadmap |
| K6 | sources of insights inside `implement` | moved to the author's private process roadmap |
| K7 | `aidd ingest` of SARIF | moved to the author's private process roadmap |
| K8 | an insight becomes a convention rule | moved to the author's private process roadmap |
| K9 | aging and backup of insights | moved to the author's private process roadmap |
| K10 | the process policy inside a repository | moved to the author's private process roadmap |
| D2 | the execution orchestrator | moved to the author's private process roadmap |
| D4 | a local model for tool calling | moved to the author's private process roadmap; its half on summaries and classification: withdrawn, with F1.6 |
| F1.6 | summaries by a local model | withdrawn: no model writes a record of the graph |
| F1.10 | a `flow` skill | withdrawn: as S2 |
| F2.7 | an `impact` skill | withdrawn: as S3 |
