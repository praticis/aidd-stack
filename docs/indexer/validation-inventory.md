# The indexer's validation procedures: an inventory and the recovered state

> The first of five documents on how the indexer's changes are validated. This one lists every procedure the
> evidence supports, where each lives and how sure we are of it. The other four will detail them (§10).
>
> **Written on 2026-10-24**, on `main` at `0725d47`, by a new session. The development session that ran H5 so far
> (`6d63c0e8-…`) was blocked and can no longer be continued, so everything here was recovered from what that session
> left behind, then checked against the repository where possible.
>
> **Updated on 2026-10-24** to point each procedure at its resources: the scripts copied from the scratchpads into
> `indexer/scripts/`, and the evidence in `docs/indexer/evidence/`. Each resource's origin, nature, state and safety
> are in [the resource catalog](resource-catalog.md). The copy changed no class below: a script in the repository is
> not, by itself, a run that confirms a procedure.

## How to read this document

Each statement carries a class:

| Class | Meaning |
|---|---|
| **C** | Confirmed in the current repository: a file read on `main` at `0725d47`, or a run on it (CI, `atlas_status`) |
| **R** | Recovered from historical records (the previous session's transcript, its scratchpad, the memory files), not re-run |
| **P** | Partially confirmed: the implementation exists, but part of the claim (its execution, a number, a detail) is only historical |
| **I** | Inferred, not confirmed |
| **U** | Unavailable or not recoverable |

Paths used throughout:

- `$S` is the previous session's scratchpad,
  `/private/tmp/claude-<uid>/<project-dir>/6d63c0e8-8e3f-49a8-a914-057afea0c8be/scratchpad`. It is volatile: a macOS
  reboot empties it, as happened on 2026-10-22, and again on 2026-10-26, after this inventory was written: `$S`
  no longer exists. Its contents named here are history; what survives is in the repository, in `$T`, or in
  `.local/indexer/pr27/` (the catalog).
- `$C` is `~/.cache/aidd-corpus`, which survives a reboot: clones, corpus runs, micro base runs, H6 results and the
  recovery helpers.
- `$T` is that session's transcript, `~/.claude/projects/<project-dir>/6d63c0e8-8e3f-49a8-a914-057afea0c8be.jsonl`
  (about 950 MB).
- "Snapshot N" is a live snapshot by its number in the picture's sorted list. The live install's tenants are never
  named in the repository.
- A link points at a file of this repository. `$S`, `$C` and `$T` are named as sources, and as the places of inputs
  and outputs, never as where a tool lives. In §5, **Where** says where a tool was when it ran, often `$S`, and
  **Resources** where it lives now.

---

## 1. Summary of the recovered state

- **The work in progress is H5 step 5** (`docs/handoffs/H5-indexer-refactor.md`): the `TypeIndex` of ADR-005, one
  language at a time, each a refactor and then a change of behavior (H5-D10). Go is done (PR #17, #20), and so is C#:
  PR #23 (refactor), PR #25 (change of behavior) and PR #27 (`fix(csharp)`, H5-D17, "what a name means in C#"). **C**
- **PR #27 merged into `main` on 2026-10-24 at 06:34 UTC** as `0725d47`, with the `graph-change` label and every CI
  check green. **C**
- **The live install was reinstalled from `main` right after the merge.** `~/.aidd/indexer/aidd_indexer` is identical
  to `main`'s tree, and the 10 snapshots were re-indexed at 06:36–06:37 UTC by build `0.2.15+ccc54d86dbc7`, none
  `outdated`, with the refresher's last run at rc 0. **C**
- **The step after that is not done.** The graph's "after" picture, the golden answers after, the eleventh golden
  round in `docs/golden-questions.md` and the line in `docs/history.md` are still pending. A "before" picture and the
  golden answers before were taken on 2026-10-23 into `$S/livecsn/`, which the reboot of 2026-10-26 emptied; their
  copies of 2026-10-24 are in `.local/indexer/pr27/` (89 of 89 hashes on 2026-10-26). **C** (the copies exist) / **R**
  (what was planned)
- **Next in H5:** step 5 for Python, then TS; then steps 6, 12, 10 and 11; then H6 is plugged in. **C**
- **The validation method has five layers:**
  1. the tests and the case tables;
  2. the HTTP corpus and the hold-out against their baselines;
  3. the micro graph, compared record by record;
  4. the CI gates;
  5. the live install, before and after the merge, with a golden round.

  Layers 1 to 4 are scripts in the repository. Most of layer 5, and every tool used to judge a micro-graph
  difference by case, lived only in `$S`. On 2026-10-24 they were copied into `indexer/scripts/`, not committed, with
  the edits the catalog lists. **C** / **R**
- **31 procedures are inventoried below (§4).**
  - 13 are confirmed in the repository;
  - 16 are partly confirmed: their implementation was only in `$S` (in the repository since 2026-10-24), or their
    execution is only historical;
  - 2 are only historical: the probes (V14) and the equivalence checks of a data refactor (V19), whose scripts were
    not found.
  - The main reproducibility gaps are in §9. Among them: `live-check.sh` (H7 slice 4) is not built, no script
    compares two live pictures, PR #27's private data (the golden calls, the before picture) is kept only on this
    disk, in `.local/indexer/pr27/`, with no backup, the micro judgment's per-site case attribution is not persisted,
    and the verdicts have no recorded format (H7-D2).

## 2. Sources

### Consulted

| Source | What it gave | Class |
|---|---|---|
| `AGENTS.md` | the entry point: the method's commands, the gates, the refactor rule, the plan's order | C |
| `indexer/scripts/README.md` and every script in `indexer/scripts/` (`corpus.sh`, `http_corpus.py`, `corpus_metrics.py`, `micro.sh`, `micro.py`, `gates.sh`, `gates.py`, `shape.py`, `test.sh`, `mcp-it.sh`) | the implementation of layers 2 to 4 | C |
| `.github/workflows/indexer.yml` | the CI jobs, the caches and how the base and the labels are read | C |
| `docs/handoffs/H5-indexer-refactor.md` | the state of H5, its regression protocol, step 5's case tables and judgments, H5-D1…D17, the pitfalls | C |
| `docs/handoffs/H7-regression-gates.md` | the gates, built and planned; slice 1c (the writer read back); H7-D1…D5 | C |
| `docs/handoffs/H6-extraction-pipeline.md` | "How it is measured" (the statistics of timing), the cache's guarantees, the pitfalls | C |
| `docs/handoffs/H4.1-contributor-path.md` | the method as twelve parts to transfer, the failure modes of an AI contributor, the acceptance test | C |
| `docs/indexer-evolution.md` §4–§6 (in Portuguese) | the cycle of a change, how to measure, the checklist | C (partly out of date, §9) |
| `docs/corpus-report.md` | the judging rules, the baselines table, "H5 baseline", "H5 steps", "H6 baseline", "H6 step 1" | C |
| `docs/golden-questions.md` | Q1–Q5 and the rounds 1 to 10; no eleventh | C |
| `docs/decisions.md`, `docs/history.md`, `docs/ROADMAP.md` | H2-D1…D21, H6-D1…D6, H7-D1/D3/D5, the working-process decisions; the milestones; "Where we are" | C (lagging PR #27, §9) |
| `docs/adr/ADR-002` to `ADR-006` | the statuses: ADR-004 to ADR-006 accepted on 2026-10-20; ADR-005 implemented for Go and C# only | C |
| `neo4j/SCHEMA.md` | `Snapshot.indexer_build`, `IndexRun`, the `CALLS` strategies, the merge keys | C |
| `indexer/tests/` | the fixtures, the 55 expected lists and 3 of the hold-out, the case tables, the tests that guard the method itself | C |
| Git: branches, the last 60 commits, `origin/h6/step1-proto` | the commit pattern (`test(…)` then `fix(…)`), the H6 measurement scripts and results kept on a reference branch | C |
| GitHub (`gh`, read-only): PRs #1–#27, their labels, the CI runs, the ruleset | PR #27's checks and the push to `main` after it; the `graph-change` label on #20, #25 and #27; ruleset `main: gates and history` active | C |
| `atlas_status` (the live MCP, read-only) | the build and freshness of the 10 live snapshots after the reinstall | C |
| `~/.aidd/indexer` against the working tree | the install runs `main`'s code | C |
| Memory files (`~/.claude/projects/<project-dir>/memory/*.md`) | the agreed order, the operating pitfalls, the code-shape and comment rules, the commit rules | R |
| `$S` (the previous scratchpad): `h5/`, `val/`, `livecsb/`, `livecsn/`, PR bodies | the per-commit protocol and its 17 runs for PR #27, the judgment tools, the live-check scripts and their outputs | R |
| `$T` (the transcript), visible messages and tool calls only | the last messages, the compaction summary, the commands of the before/after comparison, sample sizes, the PR #5 validation plan | R |
| `$C` (`~/.cache/aidd-corpus`) | 33 corpus baselines and the hold-out's, the micro base runs, `micro-fresh/`, `h6/`, the recovery helpers | C (they exist) |
| The other three transcripts of the project | sessions on the H4 docs, not on validation | R (not relevant) |
| The Obsidian vault and Qdrant, through their MCPs | 3 notes about a tenant's repo; nothing on the indexer's validation | C (nothing relevant) |

### Inaccessible or not used

| Source | Why |
|---|---|
| The reasoning of the previous session | Not recovered, by rule: only its visible messages, tool calls and outputs were read |
| The `knowledge` service's insights | Multi-tenant mode needs a tenant; `aidd-stack` is not a tenant repo, so nothing applies |
| The CI artifacts (`corpus`, `micro`) of PR #27's run | Kept 14 days on GitHub; not downloaded, since their verdict is in the checks |
| The draft release `h6-step1-results` | Not downloaded; the replay records it holds are described in `indexer/scripts/h6-step1/README.md` on `h6/step1-proto` |
| The micro-graph runs behind each judgment (`$C/micro-fresh/csn-n*`) | Present (6.9 GB), but not re-read: their summaries are in `$S/h5/runs/` and `$S/h5/why/out/` |
| The live graph itself | Not queried with Cypher; only `atlas_status` was read, to keep this stage read-only |

## 3. The last identifiable state of the work

### What was in progress

| Item | State | Evidence | Class |
|---|---|---|---|
| The refactor | H5 step 5, C#'s third PR: H5-D17, a `fix(csharp)` that makes a name mean what C# makes it | H5 handoff, "What a name means in C# (H5-D17)"; PR #27 | C |
| The hypothesis | C#'s one answer (PR #25) still read names in ways C# does not: the block namespace, the namespaces around the code, a capitalized member taken for a homonym type, a type parameter taken for a type outside the repo. Reading each as C# does gains edges and removes wrong guesses, with no HTTP change | H5-D17, as widened by the author on 2026-10-23 | C |
| The files | `languages/csharp/type_syntax.py` and `wiring.py` (new); `written.py`, `type_index.py`, `type_facts.py`, `locals.py`, `symbols.py` and `http.py` (1,401 lines, down from 1,407); `indexer/tests/test_cs_names.py`, 42 cases | `git show --stat 0725d47`; the compaction summary in `$T` | C / R (line counts) |
| The decisions already taken | H5-D1…D17, H6-D1…D6, H7-D1/D3/D5; ADR-004 to ADR-006 accepted | `docs/decisions.md`, the handoffs | C |
| What ran | 30 code commits, 13 of cases and 17 of fixes; the protocol on each code commit in its own worktree (`$S/h5/runs/csn-n1`…`n17`); the judgment of each commit against the one before and of `main` against the tip; timing alone; the tests and the shape ratchet; CI; a read-only live check before the merge | `$S/h5/runs/`, `$S/h5/why/out/`, `$S/livecsn/`, PR #27's checks | C (CI) / R (the rest) |
| What it confirmed | Corpus and hold-out `0 repo(s) differ` against `-29` and `-26` at the last commit; micro: the 10 repos of other languages identical, and so were clean-arch-dotnet and rapid-blazor; 13 C# repos changed, judged by case; time unchanged (corpus 259 s on `main`, 255 s on the branch); 609 tests passed; the shape gave "0 new or worse"; on the live install, the 10 snapshots' dry-runs were identical between `main` and the branch, and the graph held `main`'s dry-run | `$S/h5/runs/csn-n17/`, `$S/livecsn/dry_sections.txt`, `$S/livecsn/graph_vs_dry.txt`, the H5 handoff | R, and C for CI |
| What is pending | the "after" picture of the graph and its diff against `$S/livecsn/before`; the golden answers after; the eleventh golden round in `docs/golden-questions.md`; the PR #27 line in `docs/history.md`; the ROADMAP's and the handoff's state (both still say H5-D17 "goes to review") | the last assistant message in `$T` (2026-10-24 06:42) and the compaction summary; `docs/golden-questions.md` ends at the tenth round | C (absence) / R (the plan) |
| The acceptance criteria in use | §5 V07–V11 and V21–V24: corpus and hold-out unchanged, or judged; every xfail gained and no guard lost; micro judged by case, one wrong item in a case blocks; time no worse; shape no worse; live dry-runs identical, or the differences judged; the picture changing exactly as the dry-runs said; the golden answers the same | H5's protocol, H5-D10…D14, the golden rounds | C |
| The next step | after the user's reinstall (done): the after picture, its comparison, the golden answers, the eleventh round in a docs PR (`docs/golden-eleventh-round`), with approval before the push. Then H5 step 5 for Python | the last messages in `$T` | R |
| Operating constraints | commits signed through 1Password, a one-line subject, no body and no trailer; push, PR edits and merges only with the user's approval, and the user merges; the live install is read-only for the agent, and only the user reinstalls; no tenant name in any output that leaves the machine; corpus code never runs; long runs in the background, never two protocols at once | memory files; the compaction summary; `AGENTS.md` | C (AGENTS) / R (the rest) |

### Confirmed on 2026-10-24, beyond the history

- `0725d47` is `main`'s tip and the working tree is clean. **C**, on 2026-10-24, before the recovery's files were
  added. Since then the working tree holds them, staged and uncommitted
  ([the entry point](validation-and-continuity.md), §4).
- The install's code equals `main`'s (`diff -rq ~/.aidd/indexer/aidd_indexer indexer/aidd_indexer` gives nothing). **C**
- `atlas_status`: build `0.2.15+ccc54d86dbc7` everywhere, 10 snapshots indexed between 06:36:48 and 06:37:12 UTC,
  `outdated: false` on all, every tenant's last refresh at rc 0 with `changed: 0`. This answers B4's first criterion
  (each snapshot re-indexed after the upgrade). Whether the next refresh re-indexed none was not checked from logs.
  **C** / **P**
- The image `aidd-indexer:local` was built at 06:35:55 UTC, so its id is new (`f07550cbe2e2`). `$C/micro` holds no
  base for `main`'s `aidd_indexer` tree (`ed46a54b…`) with that image, so the next local `micro.sh` must first run
  `--base-only` (the H5 pitfall on reinstalls). **C**
- Docs that lag: `docs/history.md` has no PR #27 line. The ROADMAP's "Where we are" and the H5 handoff's state call
  H5-D17 "done and goes to review". **C**

### PR #27's open items, checked again on 2026-10-24

- **The "after" side:** the after picture is not taken (`$S/livecsn/after/` does not exist), nor compared with the
  before one, and the golden answers after are not taken.
- **The docs:** the eleventh round, PR #27's line in `docs/history.md`, and the state in the ROADMAP and in the H5
  handoff are not written.
- **The micro base:** none exists for `main`'s tree and the new image, so `micro.sh --base-only` must come before
  the next local protocol.
- **The reinstall:** `install-check.sh`'s output is unknown.
- **Preserved on 2026-10-24, with the author's authorization:** the before picture, the dry-runs, the pre-merge
  logs and the original golden script, copied from `$S` to `.local/indexer/pr27/`, each copy's SHA-256 equal to its
  source's; and the 27 calls as `golden-calls.json`, derived from the script and checked. The folder is ignored by
  git, private and on this disk only: it has no backup. Its `README.md` says how to check and use it.
- **Checked again later on 2026-10-24:** every item above but the preservation is still open.
- **Attempted on 2026-10-26, with the author's authorization:**
  - the micro base was made;
  - the protocol ran on `main`;
  - the pre-merge outputs were re-derived from the local copies, and the dry-runs compared record by record;
  - `install-check.sh` ran.

  The after picture and the golden answers after could not be taken: the install's Neo4j was down. The results are
  in [the PR #27 evidence](evidence/pr27-validation-state.md), §8.
- **Done later on 2026-10-26,** after the author recreated the Neo4j container, at the author's request:
  - the after picture, compared with the before one: identical but for the build and one more `IndexRun` per
    snapshot;
  - the golden answers after: 22 of 27 byte for byte the same, and the other 5 different only in time and build
    fields;
  - `install-check.sh`: "All checks passed".

  The eleventh round and the line in `docs/history.md` wait only for a docs PR (§9 of the same file). **C**

The table, with how each item is done, is in [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md),
§7. **C** (the checks) / **R** (the plan)

---

## 4. The inventory

"Kind" says how a procedure binds:

- **gate**: CI fails the PR;
- **required**: the method requires it locally, and no CI job runs it;
- **conditional**: it runs only on a change of behavior, or only when something differs;
- **exploratory**: a tool that leads a judgment, not a criterion.

The class is the procedure's as a whole; §5 gives each part's. "Doc" is the proposed document of the series (§10).

| ID | Procedure | Stage of the cycle | Kind | Class | Doc |
|---|---|---|---|---|---|
| V01 | Corpus pins and clones | preparation | required | C | 2 |
| V02 | The expected lists and the `checked` sample | preparation; after a judged diff | required | C | 2 |
| V03 | Baselines: the chain, promotion, the CI cache | preparation; closing a change | required (local), gate input (CI) | C | 2 |
| V04 | Hold-out discipline | every run; a measurement point | gate | C | 2 |
| V05 | Cases first: fixtures and strict xfail case tables | before the code | required | C | 3 |
| V06 | The test suite and the tests that guard the method | every commit | gate | C | 5 |
| V07 | Corpus and hold-out diff against the baselines | every code commit | gate | C | 2 |
| V08 | Precision, recall and the gates' classification | every PR | gate | C | 3 |
| V09 | Item-by-item judgment of a corpus diff at the source | when the corpus differs | conditional | P | 3 |
| V10 | The micro graph, compared record by record | every code commit | gate | C | 2 |
| V11 | The micro graph judged by case (H5-D14) | a change of behavior | conditional | P | 3 |
| V12 | Loss analysis: what `main` had and the branch lost | a change of behavior | conditional | P | 3 |
| V13 | The protocol per commit, in worktrees, in a chain | each code commit of a PR | required | P | 5 |
| V14 | Probes of the grammar and of small repos | before the cases | exploratory | R | 3 |
| V15 | The shape ratchet and the line checks | every commit | gate | C | 5 |
| V16 | Code hygiene and the core's neutrality | every commit | gate | C | 5 |
| V17 | Timing a step alone | each PR that changes code | required (judged, never a gate) | P | 3 |
| V18 | Benchmarks, profiles and the H6 replay | design steps (H5 step 0, H6 steps 0–2) | exploratory | P | 3 |
| V19 | Equivalence checks of a data refactor | a refactor that changes a representation | conditional | R | 3 |
| V20 | The MCP and the writer against a throwaway Neo4j, and its mutation test | every PR (`tests`) | gate | C | 4 |
| V21 | The live graph against dry-runs, by the writer's merge keys | before and after a merge | required | P | 4 |
| V22 | The live dry-run of `main` against the branch, per snapshot | before the merge | required | P | 4 |
| V23 | The live graph's picture, before and after the reinstall | around the reinstall | required | P | 4 |
| V24 | Install, post-install checks and the refresh | after the merge | required | P | 4 |
| V25 | The golden round | after the reinstall | required | P | 4 |
| V26 | The CI pipeline: the jobs, the base, the caches, the labels | every PR and every push to `main` | gate | C | 5 |
| V27 | Self-tests of the gates | when a gate is built or changed | conditional | P | 5 |
| V28 | PR and commit discipline | the whole cycle | required | P | 5 |
| V29 | Keeping and recovering the evidence | the whole cycle | required | P | 5 |
| V30 | Operating hygiene for measurement | every run | required | P | 5 |
| V31 | Privacy filters on outputs | every output that leaves the machine | required | P | 5 |

The PR #5 validation plan (phases A1–A6, B1–B8 and C, §5 under V22) is the origin of V21–V25 and of the gates. It is
kept under V22 instead of as a procedure of its own, since the gates and the live check now do what it did.

---

## 5. The evidence map

Each entry gives:

- **Goal** and **stage**;
- **Where:** its files, scripts and settings;
- **In → out:** its inputs, and the outputs and artifacts it leaves;
- **Criteria:** what it measures and what passes;
- **Built:** the evidence of its implementation;
- **Resources:** its canonical files in this repository, and its inputs outside it;
- **Ran:** the evidence of its execution;
- **Needs:** the procedures it depends on;
- **Gaps:** what is missing or uncertain.

### V01 — Corpus pins and clones

- **Goal:** a corpus whose runs stay comparable: each repo at one commit. **Stage:** preparation.
- **Where:** `CORPUS` and `HOLDOUT` in `indexer/scripts/http_corpus.py` (55 repos, "pinned 2026-10-13"); `MICRO` and
  `EXTRA_PINS` (grafana `044dd4f9…`) in `micro.py`; clones in `$C/repos`; H2-D2 and H2-D3.
- **In → out:** a slug and a sha per repo → a clone at that sha (`H.checkout`), listed largest first (`--list`,
  `--prepare`).
- **Criteria:** a pin moves only on purpose, with the baseline re-run in the same change. `gates.py` notes a changed
  pin ("ids may differ for that reason alone").
- **Built:** C (the code). CI caches the clones keyed by `hashFiles('indexer/scripts/http_corpus.py')` (and
  `micro.py` for the micro job).
- **Ran:** C (`$C/repos` holds 3.9 GB of clones).
- **Needs:** none.
- **Gaps:** the corpus repos are third-party code. They are parsed only in the indexer's container with read-only
  mounts, and never built or run (H2-D4, `AGENTS.md`).
- **Resources:** [`http_corpus.py`](../../indexer/scripts/http_corpus.py) and
  [`micro.py`](../../indexer/scripts/micro.py), in the repository; the clones in `$C/repos`, outside it.

### V02 — The expected lists and the `checked` sample

- **Goal:** a ruler that is evidence, not output. **Stage:** preparation; after a judged diff.
- **Where:** `indexer/tests/corpus_expected/<repo>.json` (55) and `holdout/` (3); the format is in the docstring of
  `corpus_metrics.py`; the rules are H2-D4, D5, D6, D12–D17; `http_corpus.py --sample N --seed S` and
  `--reuse runs/<run> --expected`.
- **In → out:**
  - in: a committed spec checked against the code, a route dump, or files read end to end within a `scope` fixed
    first;
  - out: `endpoints` and `calls` (each miss with a `category`), and `checked` (a seeded sample of 20 routes and 20
    calls, judged at the evidence line).
- **Criteria:**
  - matching by `(method, path_key)`; ANY matches any method; ASP.NET matches without case;
  - a lost prefix is wrong;
  - a call is expected only when its path is a literal or a template;
  - one category per miss, the most specific;
  - an item counts in its file's language.
- **Built:** C.
- **Ran:** C (the lists exist). The judged edits of F1.14 are in git history.
- **Needs:** V01.
- **Gaps:**
  - The rule "expected-list edits in their own commit, never with the extractor" is followed by hand. The "one cause
    per commit" gate and `CODEOWNERS` on the lists (H7 slice 2, H4.1-D6) are not built.
  - `--reuse` only rescores; it never measures a change to the extractor.
  - The `checked` entries record `ok` and `category`, not how each verdict was reached. In `$T`, the first
    hold-out's tools (2026-10-17) marked a sampled item right when it matched the list, and gave the others a default
    verdict with exceptions by index; H2b's `gab.py` (2026-10-15) wrote one verdict per item. Neither is persisted
    (the catalog, §4).
- **Resources:** [`corpus_metrics.py`](../../indexer/scripts/corpus_metrics.py); the lists in
  [`indexer/tests/corpus_expected/`](../../indexer/tests/corpus_expected/); the offline classification of a list's
  changes, [`checks/a2_gabaritos.py`](../../indexer/scripts/checks/a2_gabaritos.py) (reconstructed from `$T`, not
  run).

### V03 — Baselines: the chain, promotion, the CI cache

- **Goal:** a fixed point to diff against, promoted only after judgment. **Stage:** preparation; closing a change.
- **Where:**
  - local: `$C/runs/<date>-v2-baseline-N` (33 corpus baselines saved, from `2026-10-13-baseline` to
    `2026-10-18-v2-baseline-29`) and `2026-10-18-v2-holdout-26`; the table in `docs/corpus-report.md`, "Baselines";
  - CI: `runs/base-<indexer tree>` in the Actions cache (H7-D1), and `micro/base-<aidd_indexer tree>-<image key>`.
- **In → out:** a judged run → a new `-N+1`, named in the corpus report, `AGENTS.md` and the ROADMAP.
- **Criteria:** "a new baseline is saved only after its diff against the previous one was judged item by item". A
  refactor never promotes one. A change of behavior promotes one only when the corpus changed: `-29` came from Go's
  change of behavior, and C#'s three PRs kept `-29`.
- **Built:** C.
- **Ran:** C (the runs exist; CI's cache was filled by the push to `main`, run `40070748413`, success).
- **Needs:** V07, V09.
- **Gaps:**
  - The baselines are not published (H4.1-D1 is open), so an outsider cannot reproduce the quoted numbers.
  - A CI baseline is derived from the base's code and is recomputed on a miss. Locally the named baseline is a
    directory on one machine.
- **Resources:** [`corpus.sh`](../../indexer/scripts/corpus.sh); the saved baselines in `$C/runs` and the CI cache,
  outside the repository: a baseline is derived data (H7-D1).

### V04 — Hold-out discipline

- **Goal:** a set the rules never saw, so that a gain is not overfitting. **Stage:** every run; a measurement point.
- **Where:** `HOLDOUT` (Kavita, go-boilerplate, sftpgo); `corpus.sh --holdout`; `gates.py --holdout-count` and
  "Hold-out untouched"; the `holdout-measurement` label; H2-D20, H2-D21, H5-D12, H5-D13.
- **In → out:** the branch's and the base's hold-out runs → a count of the repos that changed. CI moves only that
  count between jobs ("its items never reach an artifact").
- **Criteria:**
  - any change fails without the label;
  - in a change of behavior, it is read only in aggregate (the repos that changed, and precision and recall), and
    its items are never opened;
  - the author decides the label.
- **Built:** C.
- **Ran:** C/R: `0 repo(s) differ` at every commit of PR #27 (`$S/h5/runs/csn-n*/holdout.txt`), and CI passed.
- **Needs:** V03, V07.
- **Gaps:**
  - The lists are public, so the hold-out is blind only by rule (H4.1-D2 is open).
  - The new hold-out, measured once on H5's code and on the commit before H5 (H2-D21), waits for H5 and H6.
- **Resources:** [`corpus.sh`](../../indexer/scripts/corpus.sh) `--holdout`,
  [`gates.py`](../../indexer/scripts/gates.py) `--holdout-count`; the lists in
  [`indexer/tests/corpus_expected/holdout/`](../../indexer/tests/corpus_expected/holdout/).

### V05 — Cases first: fixtures and strict xfail case tables

- **Goal:** a test that fails without the rule, and names the rule that broke. **Stage:** before the code.
- **Where:**
  - the fixtures: `indexer/tests/fixtures/*/expected.json` (17), with `gaps` as an xfail until they appear;
    `test_fixtures.py`;
  - step 5's case tables: `test_go_types.py`, `test_go_declared_types.py`, `test_cs_types.py`,
    `test_cs_declared_types.py`, `test_cs_extension_methods.py` and `test_cs_names.py` (42 cases, each checked on
    the resolver's edges and on the scanner's calls).
- **In → out:** a case and its counterexample, with `xfail(strict=True, reason=…)` on the side that is wrong today →
  a `test(<lang>): …` commit; the next `fix`/`feat` commit removes the marks.
- **Criteria:** the case fails for the written reason before the fix. A change of behavior must gain every xfail and
  lose no guard (H5-D10). Expected values are checked at the source, never copied from the output.
- **Built:** C (the tables; the commit pairs in `git log`: `e74bc41`/`53a87c0`, `a9e8173`/`4108aef` …).
- **Ran:** C (CI); R (each step: "the ten xfails fail for the written reasons", in `$T`).
- **Needs:** V14.
- **Gaps:** removing the marks and the per-side machinery was done with throwaway scripts (`$S/h5/unmark.py`,
  `unmark_cases.py`), not in the repo.
- **Resources:** the fixtures in [`indexer/tests/fixtures/`](../../indexer/tests/fixtures/) and the case tables, such
  as [`test_cs_names.py`](../../indexer/tests/test_cs_names.py). The scripts that removed the marks (`unmark.py`,
  `unmark_cases.py`) stay out, as one-off edits (the catalog, §4).

### V06 — The test suite and the tests that guard the method

- **Goal:** a green suite, including tests of the measuring tools themselves. **Stage:** every commit.
- **Where:** `indexer/scripts/test.sh` (the test image: the indexer image plus pytest, the tree mounted read-only);
  tests of the method's tools:
  - `test_gates.py`: each gate fails on its case only, and the hold-out's items are never shown;
  - `test_micro.py`, `test_shape.py`;
  - `test_corpus_metrics.py`, `test_matching.py`.
- **In → out:** the tree → pytest's summary.
- **Criteria:** all pass. The last recorded counts are 609 passed, 26 skipped and 1 xfailed (H6's root package), for
  PR #27.
- **Built:** C.
- **Ran:** C (CI `tests` on PR #27, 1m59s); R (the counts).
- **Needs:** V05.
- **Gaps:** none found.
- **Resources:** [`test.sh`](../../indexer/scripts/test.sh); [`test_gates.py`](../../indexer/tests/test_gates.py),
  [`test_micro.py`](../../indexer/tests/test_micro.py), [`test_shape.py`](../../indexer/tests/test_shape.py).

### V07 — Corpus and hold-out diff against the baselines

- **Goal:** prove that the HTTP extraction did not change, or show exactly what did. **Stage:** every code commit.
- **Where:** `indexer/scripts/corpus.sh [--label] --baseline <run> [--holdout]`; `http_corpus.py --baseline`;
  `AGENTS.md`.
- **In → out:**
  - in: the tree, the clones and a baseline;
  - out: `runs/<label>/<repo>.json`, and in `runs/<label>.logs/` each container's log with its peak memory,
    `summary.txt` and `report.txt`, ending in "N repo(s) differ".
- **Criteria:**
  - a refactor gives `0 repo(s) differ` on both sets;
  - otherwise, each id that entered or left is judged (V09);
  - exit 1 when a repo failed, for instance over its memory cap.
- **Built:** C.
- **Ran:**
  - C: CI `corpus` on PR #27, 7m18s;
  - R: 17 local runs for PR #27. Commits n2–n4 had smartstore differ (a false `GET /images/flags`), n5–n9 had
    bitwarden differ (seven relay calls dropped), and n1 and n10–n17 gave `0 differ`.
- **Needs:** V01, V03.
- **Gaps:**
  - A label must be new on every run (Docker Desktop, V30).
  - The containers run 3, 2 or 1 at once, depending on Docker's memory.
- **Resources:** [`corpus.sh`](../../indexer/scripts/corpus.sh); per commit,
  [`protocol/protocol.sh`](../../indexer/scripts/protocol/protocol.sh) (V13). PR #27's runs are summarized in
  [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md), §2.

### V08 — Precision, recall and the gates' classification

- **Goal:** turn a diff into gains, failures and a short list to judge. **Stage:** every PR.
- **Where:** `indexer/scripts/gates.py` (through `gates.sh`), with `corpus_metrics.score`, `diff_runs` and
  `checked_precision`.
- **In → out:** the base's and the branch's runs, the labels, the branch name, the commit subjects and `micro.sh`'s rc
  → a Markdown report. Each item to judge links to its line at the pinned sha.
- **Criteria:** five gates:
  1. **the precision ratchet:** per repo and kind, and pooled per language, an exact `Fraction`, never lower;
  2. **no win lost:** no expected pair the base found is missed, and no `checked` item judged right is gone;
  3. **the hold-out untouched:** see V04;
  4. **a refactor changes nothing;**
  5. **every repo measured.**

  Then the micro verdict: rc 0 passes, rc 1 needs `graph-change` and is never allowed under `refactor`, any other rc
  fails.
- **Built:** C.
- **Ran:** C (CI `gates`, 35 s on PR #27); R (PR #12, a gate check meant to fail, V27).
- **Needs:** V02, V04, V07, V10.
- **Gaps:**
  - Run locally without `--micro-rc`, `gates.py` skips the micro verdict (it passes when the rc is absent).
  - "Every diff item judged" and "one cause per commit" are listed in H7 but not built (slice 2).
  - The "no win reverted across the whole chain of baselines" check of PR #5 (A5) has no CI equivalent: CI compares
    the base and the head only.
- **Resources:** [`gates.sh`](../../indexer/scripts/gates.sh), [`gates.py`](../../indexer/scripts/gates.py); offline,
  [`checks/a4_compare.py`](../../indexer/scripts/checks/a4_compare.py) (`main` against the head, both scored by
  today's lists) and [`checks/a5_chain.py`](../../indexer/scripts/checks/a5_chain.py) (no win reverted across the
  chain of baselines), both reconstructed from `$T` and not run.

### V09 — Item-by-item judgment of a corpus diff at the source

- **Goal:** decide whether each changed item is right, by reading the code at its evidence line. **Stage:** when the
  corpus differs.
- **Where:** the guide §5, step 4; H2-D11 (precision before recall); H2-D14 (an inherited defect counts, but does not
  block); H2-D15 (lists corrected with evidence); the "To judge at the source" section of `gates.py`'s report.
- **In → out:** each item that entered or left → a verdict: right or wrong, and why.
- **Criteria:**
  - every item that leaves must have been wrong before, and every item that enters must be right;
  - a change the rule does not explain is a defect of the rule, even when precision and recall rise;
  - no repo may regress.
- **Built:** P: the rules are written down, and CI lists the items. Recording the verdicts is not built (H7-D2 is
  open).
- **Ran:** R: PR #27's two intermediate differences, judged and undone by later commits; Go's change of behavior
  (vikunja's `POST /api/v2/mcp`, memos' `ANY /`, both right and outside their lists' scope).
- **Needs:** V07, V08, V02.
- **Gaps:**
  - The verdicts live only in prose: the handoffs, the corpus report and the PR bodies.
  - An LLM never decides a verdict that a gate reads (H7). A person, or an agent reading the source, judges.
- **Resources:** the "To judge at the source" section of [`gates.py`](../../indexer/scripts/gates.py)'s report;
  [`checks/a2_gabaritos.py`](../../indexer/scripts/checks/a2_gabaritos.py) for the lists' edits. No format exists for
  the verdicts (the catalog, §5).

### V10 — The micro graph, compared record by record

- **Goal:** see `CALLS`, symbols, files, `IMPORTS` and violations, which the HTTP corpus cannot see because it never
  runs the resolver. **Stage:** every code commit.
- **Where:** `indexer/scripts/micro.sh [--base REF] [--base-only] [repo …]` and `micro.py --compare`. The set:
  - C#: eshop, jellyfin, btcpayserver, umbraco;
  - Go: vikunja, gitea, mattermost, grafana;
  - Python: dispatch, netbox;
  - TS: ghost, outline.
- **In → out:**
  - out: `micro/base-<tree>-<image>/` and `micro/<label>/`, a `<repo>.json.gz` and a log each;
  - the report: each repo `identical` or `DIFFERS`, with the records gone and new per list, ending in "N repo(s)
    differ".
- **Criteria:**
  - each list compared as a multiset of whole records, so a field that changes anywhere shows;
  - exit 0 when identical, 1 when a repo differs or was not compared, 3 when a dry-run failed;
  - a refactor must give 0.
- **Built:** C.
- **Ran:**
  - C: CI `micro` on PR #27, 6m35s;
  - R: 17 local runs on an extended set of 23 repos (the 12, plus 11 C# corpus repos in `$S/h5/cs-extra.txt`). Go's
    PRs used 25 repos (the 12, plus 13 Go repos).
- **Needs:** V01. Base runs are reused only by the same `aidd_indexer` tree and the same image.
- **Gaps:**
  - CI runs only the 12. The extended sets of the C# and Go PRs are a local practice, recorded only in `$S` and in
    the handoff's prose.
  - `micro.sh` defaults its base to `main`'s tip, while `$S/h5/micro-fresh.sh` uses `merge-base main HEAD`, and CI
    uses the merge commit's first parent. Each is right for its case; a document must say which one to use when.
  - After a reinstall the image id changes, and the base runs must be made again (§3).
- **Resources:** [`micro.sh`](../../indexer/scripts/micro.sh), [`micro.py`](../../indexer/scripts/micro.py);
  [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh) (adapted original), which compares
  through fresh paths. The extended sets of the C# and Go PRs are listed in
  [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md), §2.

### V11 — The micro graph judged by case (H5-D14)

- **Goal:** decide a change of behavior that moves thousands of edges, without judging a million `CALLS` one by one.
  **Stage:** a change of behavior.
- **Where:**
  - the rule: H5-D14;
  - the tools, in `$S/h5/why/` only:
    - `edges_lib.py`: a site is (file, line), and its edges are (callee, strategy);
    - `chain_diff.py`: each changed site by the class of its strategy (typed, `typed~amb`, `inherited`, `name`,
      `name~amb`) and by kind (`strategy`, `added`, `dropped`, `widened`, `narrowed`, `changed`), with seeded
      samples per kind;
    - `edges_join.py` and `kinds.py`: the same per case of the language's table, from a per-site attribution
      (`why_a.py`, Go);
    - `show.py` and `samples_view.py`: each sample with its source line;
    - `site_edges.py`: given sites across several runs;
    - `cmp-micro.sh`: the summary lines only.
- **In → out:** two directories of micro dry-runs (each commit against the one before, and `main` against the tip) →
  counts per class and kind, and seeded samples judged at the source. The totals go into the handoff ("+18,137 and
  −2,480 typed edges …").
- **Criteria:**
  - each changed edge is explained by a case of the table;
  - one wrong item in a case blocks the PR;
  - a wrong guess that goes away counts for the change (the handoffs list "the guesses by name that go were wrong";
    no document calls it a gain), and an edge lost that `main` found by luck is closed in the same PR
    (H5-D15, D16) or recorded as a gap with a case to start from (H5-D17 widened).
- **Built:** P: the rule is in the repo. The tools were only in `$S` until 2026-10-24, when they were copied into
  `indexer/scripts/judgment/`. `why_a.py` (141 lines) was lost with the reboot. `heredoc.py` rebuilds it from `$T`
  only in part, so it is not persisted (the catalog, §4).
- **Ran:** R:
  - the seed is `20261021`;
  - N is 4 to 12 per kind between consecutive commits; from `main`, it was 6 in PR #25 and 40 in PR #27;
  - the outputs are in `$S/h5/why/out/` (`n5`…`n17`, `main-n9`, `main-n16`, `main-n17`, with `.view.txt` holding
    the judged samples).
- **Needs:** V10, V05, V13.
- **Gaps:**
  - H5-D14 says "a seeded sample per case and repo". `chain_diff.py` samples per kind across repos, and only Go had a
    per-site case attribution. For C#, each commit closed one case, so the commit-to-commit diff stood for the case
    (**I**).
  - The sample sizes are in commands, not in a document.
  - Nothing records which sampled items were judged right, one by one (H7-D2).
- **Resources:** in [`judgment/`](../../indexer/scripts/judgment/):
  [`chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py), which reproduced its PR #27 counts on 2026-10-24
  (its stdout; its seeded samples do not reproduce, as
  [the benchmark protocols](benchmark-and-statistical-protocols.md) show in §8),
  [`edges_lib.py`](../../indexer/scripts/judgment/edges_lib.py), [`show.py`](../../indexer/scripts/judgment/show.py),
  [`samples_view.py`](../../indexer/scripts/judgment/samples_view.py) and
  [`site_edges.py`](../../indexer/scripts/judgment/site_edges.py); and, needing the per-site attribution file that
  `why_a.py` wrote and that is not persisted, [`edges_join.py`](../../indexer/scripts/judgment/edges_join.py),
  [`kinds.py`](../../indexer/scripts/judgment/kinds.py), [`cases.py`](../../indexer/scripts/judgment/cases.py) and
  [`view.py`](../../indexer/scripts/judgment/view.py). PR #27's totals are in
  [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md), §3.

### V12 — Loss analysis: what `main` had and the branch lost

- **Goal:** find edges that `main` had and the branch lost, decide whether they were right, and fix them, or record
  why not. **Stage:** a change of behavior.
- **Where:** `$S/h5/ext/` (`ext_sites.py`, `ext_back.py`, `ext_judge.py`, `this_kind.py`) and `$S/h5/why/`
  (`ext_loss.py`, `lost_ext.py`); the handoff's "What stays lost" (Go, C#) and "What stays out" (H5-D17, 13 items).
- **In → out:**
  - the sites that lost an edge to an extension method of the repo, with the old strategy, what `this` takes and what
    the site has now;
  - which of them a later commit brought back;
  - the sites that lost an edge into a file with C# 14 `extension(…)` blocks.
- **Criteria:** each loss is either a wrong guess the receiver's type now disproves, or a gap with its case named. A
  loss of the same kind as the PR's goes in the PR (the author's rule of 2026-10-23).
- **Built:** P: the tools were only in `$S`, and were copied into `indexer/scripts/judgment/` on 2026-10-24.
- **Ran:** R:
  - 188 extension edges lost in PR #25, classified;
  - 45 sites lost to extension blocks in PR #27 (43 in smartstore, 2 in elsa), which led to the fix at n17;
  - eshop's one site lost to a per-repo DI registration, recorded as gap 7.
- **Needs:** V11.
- **Gaps:** the same as V11; and the method for choosing between "fix now" and "record" depends on a decision of the
  author's each time.
- **Resources:** in [`judgment/`](../../indexer/scripts/judgment/):
  [`ext_sites.py`](../../indexer/scripts/judgment/ext_sites.py) (smoke-tested on 2026-10-24),
  [`ext_back.py`](../../indexer/scripts/judgment/ext_back.py),
  [`ext_judge.py`](../../indexer/scripts/judgment/ext_judge.py),
  [`this_kind.py`](../../indexer/scripts/judgment/this_kind.py),
  [`ext_loss.py`](../../indexer/scripts/judgment/ext_loss.py) and
  [`lost_ext.py`](../../indexer/scripts/judgment/lost_ext.py).

### V13 — The protocol per commit, in worktrees, in a chain

- **Goal:** measure every code commit of a PR on its own, so that a difference is placed at the commit that made it.
  **Stage:** each code commit.
- **Where:** `$S/h5/protocol.sh LABEL [REPO…]` (the corpus against `-29`, the hold-out against `-26`, then
  `micro-fresh.sh` on the 12 plus any repos given); the chains `csn-chain.sh`, `protocol-chain.sh` and
  `protocol-cs-chain.sh`; the worktree paths in `$S/h5/csn-n*-wt.txt`; H5's regression protocol, items 1 to 6.
- **In → out:** a worktree per commit (`AIDD_REPO`) → `$S/h5/runs/<label>/{corpus,holdout,micro}.txt` and
  one-line summaries.
- **Criteria:** the same as V07 and V10. Commits run one after another, never two protocols at once (they would share
  the containers and the machine).
- **Built:** P: only in `$S` until 2026-10-24.
- **Ran:** R: `csn-n1`…`csn-n17` (2026-10-23); `2026-10-21-h5-go-{b,g1,g2,g3}` (Go), recorded in the scripts.
- **Needs:** V07, V10, V30.
- **Gaps:**
  - `protocol.sh` was not in the repository before 2026-10-24. A worktree under `$S` is lost on a reboot, and git
    then lists it as `prunable`.
  - Each worktree is measured on a fresh path because of Docker Desktop (V30).
- **Resources:** [`protocol/protocol.sh`](../../indexer/scripts/protocol/protocol.sh) (adapted original: its outputs
  now go to `$AIDD_PROTOCOL_RUNS`, by default `~/.cache/aidd-corpus/protocol`), with
  [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh). The per-PR chains stay out: each was a
  loop over one PR's worktrees (the catalog, §4).

### V14 — Probes of the grammar and of small repos

- **Goal:** see what tree-sitter gives and what the resolver does on a form, before writing a case. **Stage:** before
  the cases.
- **Where:** `$S/h5/probe/probe.py` (builds a small C# repo from a JSON dict and prints the `CALLS` out of the
  methods named `*Run`); `probe/tree.py` (prints a snippet's tree, with field names); the guide §7 ("first look at
  the tree").
- **In → out:** a snippet → its tree or its edges.
- **Criteria:** none; it informs a case.
- **Built:** R.
- **Ran:** R (2026-10-23: the extension block `extension(byte[] value)`, which the image's grammar reads).
- **Needs:** none.
- **Gaps:** an exploratory tool; it should be documented as an aid, not as a criterion.
- **Resources:** [`probes/probe.py`](../../indexer/scripts/probes/probe.py) and
  [`probes/tree.py`](../../indexer/scripts/probes/tree.py), originals, not run.

### V15 — The shape ratchet and the line checks

- **Goal:** no function over complexity 9 and no module over 300 lines that is new or grew. **Stage:** every commit.
- **Where:** `indexer/scripts/shape.py --against REF` (ruff `C901`, `wc -l`-style counts); the CI job `shape`, which
  `gates` requires; `$S/h5/shape.sh [REF] | --c901 PATH…` (the same, run in the image); H5-D3, D6, D9.
- **In → out:** the tree and a ref → "0 new or worse", or a list.
- **Criteria:**
  - a module over the limit may stay while it does not grow, and a function that moved files is the same function;
  - by the author's rule, `csharp/http.py` must not grow;
  - long lines over 120 columns are compared with `HEAD`, so that none is new.
- **Built:** C (`shape.py`, CI); R (the long-line check, done by hand).
- **Ran:** C (CI `shape`, 10 s on PR #27); R (`$S/shape-now.json`: 13 modules over 300 lines, with no function list,
  since ruff was missing on the host).
- **Needs:** none.
- **Gaps:** full blocking (H5-D3, H7 slice 6) is the author's call; `cli.py` stays off target until P2.
- **Resources:** [`shape.py`](../../indexer/scripts/shape.py);
  [`protocol/shape.sh`](../../indexer/scripts/protocol/shape.sh), run on 2026-10-24 ("0 new or worse").

### V16 — Code hygiene and the core's neutrality

- **Goal:** comments that say only why, with no doc references and no project names; a core that names no language.
  **Stage:** every commit.
- **Where:** `test_code_hygiene.py`, `test_core_neutral.py` and `test_repo_view.py` (only the view walks the
  directories); H5-D4.
- **In → out:** the tree → pass or fail.
- **Criteria:** as stated.
- **Built:** C.
- **Ran:** C (CI `tests`).
- **Needs:** V06.
- **Gaps:** reviewing what each comment says (H5 step 10) is still to do.
- **Resources:** [`test_code_hygiene.py`](../../indexer/tests/test_code_hygiene.py),
  [`test_core_neutral.py`](../../indexer/tests/test_core_neutral.py),
  [`test_repo_view.py`](../../indexer/tests/test_repo_view.py). The hygiene test reads `aidd_indexer/` only, not the
  scripts.

### V17 — Timing a step alone

- **Goal:** a step's time, no worse than the previous one, unless justified (H5 protocol item 5). **Stage:** each PR
  that changes code.
- **Where:**
  - `$S/h5/time-cs.sh` and `time-csn.sh` (the corpus's wall time on `main`'s worktree and then the branch's, then one
    full dry-run at a time of umbraco, elsa, bitwarden and smartstore, with the resolver's `[resolve]` line from each
    log), and `time-pair.sh`;
  - H6's "How it is measured"; H4.1, part 7; the corpus report's "H5 steps".
- **In → out:** two worktrees on one image → wall or summed times, and the resolver's time.
- **Criteria:**
  - measured alone on the machine, on one image;
  - medians of at least 3 interleaved runs, with their range, when comparing options;
  - a difference counts only beyond the run-to-run range. The corpus moves about 28 % between runs of the same code,
    so a small effect is measured with a microbenchmark on the same trees;
  - time never gates CI.
- **Built:** P: in `$S`, and copied into `indexer/scripts/protocol/` on 2026-10-24.
- **Ran:**
  - R: PR #27, the corpus at 259 s on `main` and 255 s on the branch (wall), and the dry-runs within 2 s;
  - C: PR #25 and earlier, in the corpus report (summed times).
- **Needs:** V30.
- **Gaps:**
  - The corpus report's table mixes summed and wall times (§9).
  - Single runs were used for the PR-level comparison, not the median of 3 that H6 states.
  - The nightly trend (H7 slice 3) is not built.
- **Resources:** [`protocol/time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh), adapted from `time-csn.sh`
  (a new label per run, `AIDD_TIME_REPOS`). PR #27's numbers are in
  [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md), §4.

### V18 — Benchmarks, profiles and the H6 replay

- **Goal:** design decisions from measurements: where the time goes, which pipeline option is cheaper, whether a
  cache key is sound. **Stage:** H5 step 0, H6 steps 0–2.
- **Where:**
  - cProfile profiles of mattermost, umbraco, ghost and vikunja (corpus report, "H5 baseline");
  - the walk benchmark on the same trees (2.67 s → 1.08 s);
  - H6 step 0's phase-by-phase measurement (`$S/h6/measure.py`, lost and recovered from `$T`);
  - H6 steps 1–2's scripts in `indexer/scripts/h6-step1/` on the reference branch `origin/h6/step1-proto`, never to
    merge: `bench.sh`, `run_bench.sh`, `push_bench.sh`, `replay.py`, `evaluate.py`, `store_bench.py`,
    `aggregate.py`, `same.py`, `count_reads.py`, `gc_patch.py`;
  - the results in `results/` there, the replay records in the draft release `h6-step1-results`, and the raw runs
    in `$C/h6/`.
- **In → out:** repos and pushes → medians with ranges, cache misses per policy, store timings.
- **Criteria:** correctness first. Each prototype's output is compared three ways: with the HTTP baseline, with
  `main`'s micro dry-runs, and warm with cold. Configurations are compared interleaved in one bench run, never across
  runs.
- **Built:** P (on the reference branch, not on `main`).
- **Ran:** C/R (in the corpus report: "H6 baseline", "H6 step 1" and its step 2 sections).
- **Needs:** V07, V10.
- **Gaps:** the scripts target the prototype's code, not `main`'s.
- **Resources:** on the reference branch only, never to merge: `h6/step1-proto`, local and on `origin`, both at
  `6ccf4a0`. `indexer/scripts/h6-step1/` (16 scripts and a README) and its `results/` (201 files) exist there and
  not on `main`, and so does the prototype they measure (`core/pipeline.py`, `core/pipeline_pkg.py`). The scripts
  that run the indexer need the branch's code, so they run from a worktree of the branch, which leaves the main
  checkout's branch as it is; the ones that only read results run anywhere. Also the draft release
  `h6-step1-results`. H6 step 0's `measure.py` can be rebuilt from `$T`, but it stays out: 353 lines, written for
  the code before H5. The catalog has the details (§2, "V18").

### V19 — Equivalence checks of a data refactor

- **Goal:** prove that a new representation holds the same data as the old one, beyond the graph's identity.
  **Stage:** a refactor that changes a representation.
- **Where:** only in history:
  - Go's typed facts equal to the old dicts on 21,624 Go files, and C#'s on 35,255 C# files, in their order;
  - `tools/list` byte-identical after the MCP split, and the 70 Cypher strings identical;
  - the AST of each file unchanged after the comment edits (H5 step 10);
  - the baseline rescored line for line after `core/matching.py`.
- **In → out:** old and new values side by side → equal or not.
- **Criteria:** equal.
- **Built:** for the checks the handoff names, no script was found in `$S` or in the repo. In `$T`, two were found
  on 2026-10-24: `walkcmp.py`, the walk's own check (Resources), and C#'s type facts check,
  `h5/csfacts/scripts/dump.py` (2026-10-22 12:14 UTC). That one dumped every C# file's facts with `main`'s code and
  with the branch's, and a `cmp` of the two dumps gave `IDENTICAL`. It was rebuilt whole with `heredoc.py` from
  its one write, and persisted on 2026-10-26, with the author's authorization, as `checks/dump.py`. Go's,
  `tools/list`'s and the ASTs' checks were not found in the recovered sources.
- **Ran:** R: the H5 handoff and the corpus report. For C#, `$T` also holds the run's output (2026-10-22 12:17
  UTC): 35,255 files on each side, two dumps of 21,626,222 bytes, and `IDENTICAL`.
- **Needs:** V01.
- **Gaps:** Go's, `tools/list`'s and the ASTs' checks were not found; they may have been inline commands.
- **Resources:** [`checks/walkcmp.py`](../../indexer/scripts/checks/walkcmp.py), reconstructed from `$T` (the cursor
  walk against the old stack walk), not run; [`checks/dump.py`](../../indexer/scripts/checks/dump.py),
  reconstructed from `$T` (C#'s type facts, as PR #23 compared them), not run. How it ran is in the catalog, §2.

### V20 — The MCP and the writer against a throwaway Neo4j, and its mutation test

- **Goal:** prove the Cypher and the writer, which every dry-run check skips. **Stage:** every PR (`tests` job).
- **Where:**
  - `indexer/scripts/mcp-it.sh`: a throwaway Neo4j on its own network, the schema applied, `tests/mcp_it` indexed
    (a Go service on two branches, an ASP.NET one, a TS client), and a dry-run of each snapshot;
  - a tenant `it-writer` written with a file, again without it, and once more at that commit, as the refresher does
    after an upgrade;
  - `test_mcp_neo4j.py` and `test_graph_writer_neo4j.py`; H7 slice 1c.
- **In → out:** the tree → pytest's result. Everything is removed at the end.
- **Criteria:** every tool answers as expected. Every section the writer leaves (modules, files, symbols, `CALLS`,
  `IMPORTS`, endpoints, HTTP calls, violations) matches the dry-run field by field, with each record counted by the
  writer's merge keys; orphans go and records to keep stay.
- **Built:** C.
- **Ran:**
  - C: CI `tests`;
  - R: before slice 1c joined CI, `$S/h7/mutate.sh` ran it against three broken writers, and each one failed it.
    The broken writers kept the orphans, wrote no strategy on `CALLS`, or merged imports without their spec.
- **Needs:** V06.
- **Gaps:**
  - `mutate.sh` was rebuilt from `$T` and is now in `indexer/scripts/checks/`; it was not run again.
  - The H5 handoff says "14 cases" for `test_mcp_neo4j.py`. That was its count when written: a static count gives
    14 at `849b2cd` and 15 now, after `7268642` added a function (contradiction 6).
- **Resources:** [`mcp-it.sh`](../../indexer/scripts/mcp-it.sh),
  [`test_mcp_neo4j.py`](../../indexer/tests/test_mcp_neo4j.py),
  [`test_graph_writer_neo4j.py`](../../indexer/tests/test_graph_writer_neo4j.py);
  [`checks/mutate.sh`](../../indexer/scripts/checks/mutate.sh), reconstructed with its later edit replayed, not run.
  Its three mutations are in the catalog, §3, and each anchor still matches once on `main`.

### V21 — The live graph against dry-runs, by the writer's merge keys

- **Goal:** prove that the live graph holds exactly what the dry-runs computed: `main`'s before the reinstall and the
  branch's after it. **Stage:** before and after a merge.
- **Where:** `$S/val/graph_vs_dry.py BEFORE AFTER DRY` (per snapshot, `CALLS` by (caller, callee, line)) and
  `$S/val/dry_compare.py` (per section, `main`'s dry-run against the live counts). The eighth to tenth golden rounds
  describe it.
- **In → out:** the picture's `calls_edges.txt` and the dry-runs → per snapshot, "all match" or the failing check:
  - before = main;
  - after = head;
  - removed = main − head;
  - added = head − main;
  - the strategies after = head's.
- **Criteria:** "mismatching snapshots: 0". A dry-run may count more `CALLS` and `IMPORTS` than the graph, since the
  graph merges an edge by its key; counted by those keys, they match.
- **Built:** P (only in `$S` until 2026-10-24; CI's V20 does the same on the fixture repos).
- **Ran:** R: PR #27 before the merge (`$S/livecsn/graph_vs_dry.txt`, before against before, 10 of 10 match); PR #20
  (the two Go snapshots' `CALLS` changed exactly as the dry-runs said).
- **Needs:** V22, V23.
- **Gaps:** for PR #27, the run with the after picture has not been made.
- **Resources:** [`live/graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py), which reproduced its PR #27
  output on 2026-10-24, and [`live/dry_compare.py`](../../indexer/scripts/live/dry_compare.py), whose output names the
  tenants.

### V22 — The live dry-run of `main` against the branch, per snapshot

- **Goal:** see the change on real code that the corpus lacks: PR #5's increment 12 was found this way. **Stage:**
  before the merge.
- **Where:**
  - `$S/val/dryrun-live.sh SCRATCH HEAD_INDEXER MAIN_INDEXER LIVE_DIR`: each snapshot exported at its sha with
    `git archive`, as the refresher does, and indexed with `--dry-run` by each code, `-w /code` and the install's
    `atlas.yaml` read-only;
  - `$S/val/dry_sections.py`: per section, the records that differ, and `CALLS` by strategy, with snapshots as
    numbers;
  - `$S/val/live-csn.sh`, the whole chain;
  - `docs/decisions.md` (working process); `AGENTS.md` ("Before a merge").
- **In → out:** the before picture's snapshot list, and rsync'd copies of `main`'s and the branch's `indexer/`
  (`$S/livecsn/{main_src,head_src}`) → `$S/livecsn/dry/*__{main,head}.json` and a summary per snapshot.
- **Criteria:** outside the scope of the change, identical; inside it, each difference judged at the source. Before
  the run, the copied code is checked against `git ls-files` with `shasum`, against stale mounts.
- **Built:** P (only in `$S` until 2026-10-24; H7 slice 4's `live-check.sh` is meant to replace it).
- **Ran:**
  - R: PR #27 (2026-10-23 22:17 UTC), 10 of 10 snapshots identical, the C# ones included. On 2026-10-26 the
    preserved dry-runs were compared record by record in every list: 10 of 10 identical (C);
  - R: PR #25 and #23, identical;
  - R: PR #20, the 2 Go snapshots changed only in `CALLS`, judged.
- **Needs:** V23 (its snapshot list), V30, V31.
- **Origin:** PR #5's validation plan, rebuilt from `$T` and translated in
  [`evidence/pr5-validation-plan.md`](evidence/pr5-validation-plan.md):
  - phase A, offline:
    - A1, the tests, with no test of `main` missing;
    - A2, each change to the expected lists classified (`val/a2_gabaritos.py`);
    - A3, the head reproduces the baselines;
    - A4, `main` against the head, both scored by today's lists (`val/a4_compare.py`);
    - A5, no win reverted across the chain of baselines (`val/a5_chain.py`);
    - A6, lint;
  - phase B, live:
    - B1, the before picture;
    - B2, the dry-runs;
    - B3, the reinstall;
    - B4, the refresh;
    - B5, the after picture;
    - B6, the MCP;
    - B7, the golden questions;
    - B8, the scheduled refresher;
  - phase C, recording and merge;
  - what blocks a merge: a difference outside the change without an explanation, an expected pair or `checked` item
    lost, a link lost in the graph, or an `install-check` FAIL.
- **Gaps:**
  - The first version of the dry-run script lacked `-w /code`, so `python -m` ran the image's code. This is the H5
    pitfall, and `dryrun-live.sh` fixed it.
  - The phase A scripts were recovered from `$T`. The edit of `a4_compare.py` that `recover.py` reported as not
    applied is the transcript's second copy of one that did apply, so the file is the last version.
- **Resources:** [`live/dryrun-live.sh`](../../indexer/scripts/live/dryrun-live.sh),
  [`live/dry_sections.py`](../../indexer/scripts/live/dry_sections.py) (which reproduced its PR #27 output) and the
  chain [`live/pre-merge.sh`](../../indexer/scripts/live/pre-merge.sh) (adapted from `live-csn.sh`), not run here. Its
  prerequisite, the two copies of the code checked with `shasum`, is described in the catalog. PR #5's plan is in
  [`evidence/pr5-validation-plan.md`](evidence/pr5-validation-plan.md), and its phase A checks are in
  [`checks/`](../../indexer/scripts/checks/).

### V23 — The live graph's picture, before and after the reinstall

- **Goal:** prove that the graph changed only as the dry-runs said. **Stage:** around the reinstall.
- **Where:** `$S/val/foto.sh OUT_DIR`, read-only Cypher through `docker exec` on the Neo4j container, with 15 sorted
  lists:
  - `snapshots`, `labels`, `counts_micro`, `counts_macro`;
  - `endpoints`, `endpoint_nodes`, `http_calls`, `consumes`, `called_from`, `depends_on`;
  - `symbols`, `calls_edges`, `imports_edges`, `violations`, `modules`.
- **In → out:** the live graph → `before/` and `after/` directories. Before the merge of PR #27: 10 snapshots, 23,682
  `CALLS` edges, 10,607 symbols, 286 endpoint rows (`$S/livecsn/foto_before.txt`).
- **Criteria:** every list identical but for the build on `snapshots`, one more `IndexRun` per snapshot in `labels`,
  and exactly what V22 judged.
- **Comparison:** done with commands typed in the session, recovered from `$T` (2026-10-22 18:46):
  - per list, `diff before/X after/X`, counting `+` and `−`;
  - `snapshots` diffed with the build masked;
  - `labels` diffed with the tenant masked.
- **Built:** P (the picture script only in `$S` until 2026-10-24; no comparison script).
- **Ran:** R (PR #25, `$S/livecsb/{before,after}`: identical but for the build and `IndexRun`). PR #27: the before
  picture, R; the after picture, C (2026-10-26, `.local/indexer/pr27/after/`). Its 13 other lists are byte-identical,
  `snapshots` differs only in the build and `labels` in one `IndexRun` per snapshot, and `graph_vs_dry.py` reports
  "mismatching snapshots: 0".
- **Needs:** V24, V31.
- **Gaps:**
  - There is no script for the comparison.
  - A before picture lost on a reboot must be retaken before the reinstall. Afterwards it cannot be retaken.
- **Resources:** [`live/foto.sh`](../../indexer/scripts/live/foto.sh), original. No dedicated script compares two
  pictures: `graph_vs_dry.py` compares their `CALLS` with the dry-runs, and the other lists were diffed with inline
  commands. PR #27's before picture is preserved in `.local/indexer/pr27/``before/`: private, ignored by git, on
  this disk only. Its copy matches its source by SHA-256, and the versioned manifest in
  [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md), §5.

### V24 — Install, post-install checks and the refresh

- **Goal:** the live install runs the reviewed code, and every snapshot is re-indexed once with it. **Stage:** after
  the merge.
- **Where:**
  - `setup/install.sh`, which copies the working tree into `~/.aidd`, so `main` is checked out first;
  - `setup/install-check.sh`, which ends in "All checks passed";
  - `Snapshot.indexer_build` and `outdated` (`neo4j/SCHEMA.md`, `atlas_status`);
  - the refresher's logs (`docker logs aidd-refresher`, with names masked).
- **In → out:** the reinstall → a new image and build, and the snapshots re-indexed.
- **Criteria:**
  - B4: each snapshot is re-indexed once, the next refresh re-indexes none, and the logs hold no error;
  - B8: after two cycles, `last_rc` 0, `stale` false, `changed` 0;
  - the install's code equals the ref meant to run.
- **Built:** C (`install.sh`, `install-check.sh`, the build fingerprint).
- **Ran:**
  - C: 2026-10-24, the install equals `main`, and `atlas_status` shows the 10 snapshots at the new build, none
    outdated, every last refresh at rc 0 with `changed: 0`;
  - **U:** `install-check.sh`'s output for this reinstall (the user ran it; not seen);
  - C: 2026-10-26, after the Neo4j container was recreated:
    - `install-check.sh`: rc 0, 70 OK, "All checks passed";
    - each snapshot has exactly one `IndexRun` since the before picture, that of 2026-10-24, `ok`;
    - 10 refresher cycles, each at rc 0 with 0 snapshots changed;
    - the install's and the running MCP's code equal `main`'s.
- **Needs:** V28 (the merge).
- **Gaps:** only the user reinstalls. A reinstall from a branch puts unreviewed code live (the memory of 2026-10-21).
- **Resources:** [`setup/install.sh`](../../setup/install.sh),
  [`setup/install-check.sh`](../../setup/install-check.sh); `atlas_status` through the MCP.

### V25 — The golden round

- **Goal:** the answers the skills rely on, unchanged or changed only as judged. **Stage:** after the reinstall.
- **Where:**
  - `docs/golden-questions.md`: Q1–Q5, each with its MCP tool, its Cypher and its expected shape;
  - `$S/val/golden.py OUT_DIR`: 27 calls through the MCP's HTTP (`localhost:3005/mcp`), the five questions and one
    call of each of the 11 tools, including a write that `cypher_readonly` must refuse, each saved as JSON.
- **In → out:** the live MCP → `golden/<call>.json`, before and after → a new round in `docs/golden-questions.md`, in
  a docs PR (`docs/golden-<n>-round`, as #21, #24 and #26 were).
- **Criteria:**
  - each call byte for byte the same (`cmp`), or different only in its time and build fields;
  - `atlas_status` with no `outdated`;
  - Q1–Q5 ✅;
  - the round records what changed since the last one, both phases, and any finding.
- **Comparison:** recovered from `$T`: `python -m json.tool` diffs with ISO timestamps masked, and
  `json_paths_diff.py` (leaf paths, names kept out), which was lost, recovered from `$T`, and is now in
  `indexer/scripts/live/`.
- **Built:** P: the questions are in the repo. The script was only in `$S`; since 2026-10-24 the repository holds a
  sanitized rewrite of it.
- **Ran:** C (rounds 1–10 in the doc); R (PR #27's before answers in `$S/livecsn/before/golden/`: 26 calls without
  an error, plus the refused write). PR #27's after answers: C (2026-10-26, `.local/indexer/pr27/after/golden/`).
  - 22 of 27 are byte for byte the same.
  - The other 5 differ only in time and build fields.
  - The write is still refused, and no snapshot is `outdated`.
  - The eleventh round is not written yet.
- **Needs:** V24, V23.
- **Gaps:**
  - The original `golden.py` holds the live tenants' and repos' names, so it is not versioned. The rewrite reads its
    calls from a private file. For PR #27 that file is `.local/indexer/pr27/``golden-calls.json`, on this disk only. H7
    slice 4 and the demo tenant (H4.1-D4) remain the way to a check that runs anywhere.
  - One argument was edited in place on 2026-10-22. The calls as they ran for PR #27 are frozen only in the local
    copy, not in the repository.
- **Resources:** [`live/golden.py`](../../indexer/scripts/live/golden.py), a sanitized rewrite that reads its calls
  from a file kept outside the repository, with
  [`live/golden-calls.example.json`](../../indexer/scripts/live/golden-calls.example.json) for the shape;
  [`live/json_paths_diff.py`](../../indexer/scripts/live/json_paths_diff.py), reconstructed. The live install's calls
  file is `.local/indexer/pr27/``golden-calls.json`: 27 calls, derived on 2026-10-24 from the original script, which
  is kept verbatim beside it. Both are local and private.

### V26 — The CI pipeline: the jobs, the base, the caches, the labels

- **Goal:** the mechanical part of the method on every PR, for anyone. **Stage:** every PR and every push to `main`.
- **Where:** `.github/workflows/indexer.yml`, which runs the jobs `changes`, `tests`, `shape`, `corpus`, `micro` and
  `gates`; the ruleset `main: gates and history`, which requires `tests` and `gates`; the labels `graph-change` and
  `holdout-measurement`; H7-D1, D3, D5.
- **In → out:** a PR → the checks, a job summary with the gates' report, and the `corpus` and `micro` artifacts,
  kept 14 days.
- **Criteria:**
  - the base is the merge commit's first parent;
  - the baselines are keyed by the code's tree;
  - the labels are read when `gates` runs, so after adding one, only `gates` is re-run;
  - a skipped job passes, hence `changes` and `always()`.
- **Built:** C.
- **Ran:** C (PR #27 run `40032444886` and `main` run `40070748413`, both successful).
- **Needs:** V06–V10, V15.
- **Gaps:** H7 slices 1b, 2, 3, 4, 5 and 6 are open.
- **Resources:** [`.github/workflows/indexer.yml`](../../.github/workflows/indexer.yml),
  [`gates.py`](../../indexer/scripts/gates.py).

### V27 — Self-tests of the gates

- **Goal:** a gate that is known to fail when it should. **Stage:** when a gate is built or changed.
- **Where:** `test_gates.py` (synthetic runs); PR #12 (`refactor/gate-check`, closed): it dropped minimal API `GET`
  routes on purpose to see the gates fail; V20's mutation test.
- **Criteria:** each gate fails on its case and only on it.
- **Built:** C (`test_gates.py`); R (PR #12, closed without a merge, and `mutate.sh`).
- **Ran:** C/R.
- **Needs:** V26.
- **Gaps:** nothing re-runs the mutation test.
- **Resources:** [`test_gates.py`](../../indexer/tests/test_gates.py);
  [`checks/mutate.sh`](../../indexer/scripts/checks/mutate.sh).

### V28 — PR and commit discipline

- **Goal:** keep "0 differ" and a judged diff meaningful, and keep the author in control. **Stage:** the whole cycle.
- **Where:** `AGENTS.md` ("For contributors", the refactor rule); `gates.py` (`refactor_by`); H5's pitfalls; the PR
  bodies kept in `$S` (`pr25-body.md`, `pr26-body.md`, `h5/docs/pr-body.md`).
- **The practice:**
  - a refactor goes in a `refactor/…` branch with `refactor:` commits, and a change of behavior in a `feat/` or
    `fix/` branch, with `test(<lang>)` commits before each fix and the docs in a last commit;
  - a PR body follows "The rule(s) / Commits / Judged / Test plan", with the checklist ticked only when done;
  - the docs go in the same PR: the handoff's "Done", the decisions, the guide's rows, the corpus report's row, the
    ROADMAP and the README;
  - after the merge, a docs PR with the golden round.
- **Criteria:**
  - one cause per commit;
  - a one-line conventional subject, signed, with no body and no attribution;
  - no tenant name in a PR;
  - push, PR edits and merges only with the user's approval, and the user merges.
- **Built:** C (the refactor rule in `gates.py`); R (the rest is practice).
- **Ran:** C (`git log`; PRs #17–#27).
- **Needs:** none.
- **Gaps:** "one cause per commit" is not checked (H7 slice 2).
- **Resources:** [`AGENTS.md`](../../AGENTS.md); `refactor_by` in [`gates.py`](../../indexer/scripts/gates.py). The PR
  bodies are on GitHub (#25–#27).

### V29 — Keeping and recovering the evidence

- **Goal:** a result can be found, cited and rebuilt after the session or the machine goes away. **Stage:** the whole
  cycle.
- **Where:**
  - durable: git (the code, the expected lists, the docs with each PR's numbers), `$C` (runs, baselines, micro bases,
    H6 raw data), the reference branch `h6/step1-proto`, the draft release `h6-step1-results`, and the memory files;
  - volatile: `$S` (scripts, worktrees, run summaries, live pictures, PR bodies).
- **Recovery:** `$C/recover/recover.py` replays the Write and Edit calls of a path from `$T`; `$C/recover/heredoc.py`
  rebuilds files that a Bash heredoc wrote, and lists the in-place edits it does not replay.
- **Criteria:** every number in a doc names its run or its PR. A lost before picture is retaken before the next
  reinstall.
- **Built:** P.
- **Ran:** R: the 2026-10-22 reboot emptied `$S`, and the live scripts were rebuilt from `$T`. In this session,
  `validation-plan.md`, `val/a*.py`, `h6/measure.py`, `why_a.py`, `h7/mutate.sh` and `json_paths_diff.py` were
  rebuilt the same way, into this session's own volatile scratchpad. Those worth keeping were persisted on
  2026-10-24 (the catalog, §2 and §3).
- **Needs:** none.
- **Gaps:**
  - Until 2026-10-24 the method's live and judgment tools existed only in a volatile place. They are now in the
    working tree, not committed. The private inputs, the golden calls and the live pictures, are in
    `.local/indexer/pr27/` since 2026-10-24, on this disk only; `$S` was emptied on 2026-10-26.
  - `$T` is 950 MB, and a blocked session cannot be resumed.
- **Resources:** [`recovery/recover.py`](../../indexer/scripts/recovery/recover.py) and
  [`recovery/heredoc.py`](../../indexer/scripts/recovery/heredoc.py); [`the resource catalog`](resource-catalog.md);
  the evidence in [`evidence/`](evidence/).

### V30 — Operating hygiene for measurement

- **Goal:** the run measures the code you think it measures. **Stage:** every run.
- **Where:** the H5 handoff, "Pitfalls"; the memory files; `$S/h5/micro-fresh.sh`, now
  `indexer/scripts/protocol/micro-fresh.sh`.
- **The practice:**
  - **Docker Desktop on macOS:**
    - a folder deleted and made again at the same path cannot be mounted again, so each run gets a new label and
      `micro.sh` runs once per tree state;
    - a file just written can be read cut short through another mount, so a run's folder is copied to a fresh path
      before it is compared;
    - an edited script can be served stale, so `wc -c` is compared on the host and in the container;
    - a run that prints nothing and exits 0 is checked first.
  - **The code that runs:** `python -m` in the image runs the image's code, so use `-w` on the mounted code and check
    the log's first line.
  - **The worktrees and the queue:** never edit the mounted code during a run; measure in worktrees; run one
    protocol at a time; run long work in the background.
  - **Python on the host** runs only with `-I`, and only on our own outputs.
  - **zsh:** no backticks or `====` in commands, and edit scripts go into files.
- **Built:** P (prose and `micro-fresh.sh`).
- **Ran:** R (several incidents recorded with dates).
- **Needs:** none.
- **Gaps:** none of it is checked mechanically.
- **Resources:** [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh); the pitfalls of the H5
  handoff (`docs/handoffs/H5-indexer-refactor.md`).

### V31 — Privacy filters on outputs

- **Goal:** no tenant or private name leaves the machine. **Stage:** every output.
- **Where:** `AGENTS.md`; `test_code_hygiene.py`; the live scripts print snapshots by number (`dry_sections.py`,
  `graph_vs_dry.py`, `json_paths_diff.py`); `sed` masks on logs; PR bodies are checked before the push.
- **Criteria:** no real tenant, client or private project name in docs, code, tests, fixtures, PRs or replies. Public
  corpus repos may be named.
- **Built:** C (the rule and the test); R (the masks).
- **Ran:** R.
- **Needs:** none.
- **Gaps:** `golden.py` and `foto.sh`'s raw lists hold names on the machine. Any tool that moves into the repo must
  read them from configuration.
- **Resources:** [`test_code_hygiene.py`](../../indexer/tests/test_code_hygiene.py); the live scripts that print
  snapshots by number ([`dry_sections.py`](../../indexer/scripts/live/dry_sections.py),
  [`graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py),
  [`json_paths_diff.py`](../../indexer/scripts/live/json_paths_diff.py)); `golden.py`'s calls file, kept outside the
  repository.

---

## 6. The validation flow, end to end

Two kinds of PR go through the same frame; what differs is what counts as a pass. The order below is the one PRs #17
to #27 followed (**R**, confirmed by their commits, labels and checks: **C**).

```
 preparation
   V01 pins and clones · V02 lists · V03 baselines (-29, holdout -26) · micro base for the base's tree and image (V10)
   live: V23 "before" picture + V25 golden answers before, while the graph still holds main      [before any reinstall]
        │
 the change, commit by commit
   V14 probes ──▶ V05 cases (test(lang), strict xfail, a reason per side)
        ──▶ the fix (feat/fix(lang)), marks removed ──▶ V06 tests · V15 shape · V16 hygiene
        ──▶ V13 the protocol on the commit's worktree: V07 corpus + hold-out, V10 micro (12 + extended set)
        ──▶ refactor: anything that differs is a defect of the commit → fix it, back to the cases
            behavior: V09 corpus items, V11 micro by case, V12 losses → each wrong item blocks; a loss of the
            same kind gets a new case and a fix; another kind is recorded as a gap with a case
        │
 the PR
   V17 timing alone (main and tip) · the docs commit (handoff, decisions, guide, corpus report, ROADMAP)
   V28 push + PR, with approval; the label graph-change only after the judgment
   V26 CI: tests (V20) · shape · corpus · micro · gates (V08); re-run gates after a label
   V22 live dry-runs main × branch, per snapshot (+ V21 the graph holds main's dry-run)
        │
 the merge (the user) and the reinstall (the user, from main)
   V24 the install equals main · each snapshot re-indexed once · no outdated · the refresher at rc 0
   V23 "after" picture, diffed with "before" · V21 the graph holds the branch's dry-run
   V25 golden answers after, compared · a round in golden-questions.md · a line in history.md
   V28 docs PR (docs/golden-<n>-round), with approval
        │
 closing
   V03 a new baseline only when the corpus changed and was judged · V29 the evidence named in the docs
```

| Step | Refactor PR | Change of behavior PR |
|---|---|---|
| Corpus and hold-out | `0 repo(s) differ` (gate) | judged item by item; the hold-out only in aggregate, and `holdout-measurement` only by the author's decision |
| Micro | identical (gate) | judged by case, `graph-change` after the judgment |
| Cases | the existing ones stay green | every xfail gained, no guard lost |
| Baseline | unchanged | new only if the corpus changed |
| Live dry-runs | identical | identical outside the change; inside it, judged |
| Picture and golden | identical but for the build and `IndexRun` | as the dry-runs said |

Mandatory, conditional and exploratory, as the evidence shows them:

- **Gates (CI):** V04, V06, V07, V08, V10, V15, V16, V20 and V26.
- **Mandatory, local:** V13, V17, V22, V23, V24, V25 and V28–V31. They are required by the method's docs or the
  author's practice, but no job checks them.
- **Conditional:** V09, V11 and V12 (when something differs or in a change of behavior), V19 (a change of
  representation) and V27 (a gate changed).
- **Exploratory:** V14 and V18.

## 7. Dependencies

```
V01 ─▶ V02 ─▶ V03 ─▶ V07 ─▶ V08 ─▶ V26
 │             │      │      └─▶ V09 ─▶ V03 (promotion)
 │             └─▶ V04 ┘
 └─▶ V10 ─▶ V11 ─▶ V12
       └──────▶ V08 (--micro-rc)
V05 ─▶ V06 ─▶ V26          V14 ─▶ V05
V13 = V07 + V10 per commit, on V30
V15, V16 ─▶ V26            V20 ─▶ V26            V27 ─▶ V08, V20
V23 (before) ─▶ V22 (its snapshot list) ─▶ V21 (before) ─▶ [merge] ─▶ V24 ─▶ V23 (after) ─▶ V21 (after) ─▶ V25
V28, V29, V30, V31 apply to every step
```

- **The hard order:**
  - V23's before picture must be taken while the graph still holds `main`'s build, so before the reinstall;
  - V10's base must exist for the base's tree and image before the head's dry-runs;
  - a label (V26) is added only after the judgment it records (V09, V11).
- **The soft order:** V17 runs when nothing else is running. That is why it comes after the chain of V13.

## 8. A preliminary coverage matrix

What each procedure sees.

- **G:** a CI gate;
- **L:** local, required by the method;
- **J:** judged by a person when it differs;
- **P:** planned, not built;
- **–:** not covered.

| What can regress | Tests and cases (V05, V06) | Corpus (V07–V09) | Hold-out (V04) | Micro (V10–V12) | Neo4j IT (V20) | Live dry-run (V22) | Picture (V23, V21) | Golden (V25) | Shape and hygiene (V15, V16) | Time (V17, V18) |
|---|---|---|---|---|---|---|---|---|---|---|
| HTTP endpoints and calls (ids) | G (fixtures) | G, J | G (count) | G | G | L, J | L | L (Q1, Q2, Q5) | – | – |
| HTTP precision and recall against the lists | – | G (ratchet) | J (aggregate) | – | – | – | – | – | – | – |
| Files, symbols, `IMPORTS` | G (fixtures) | – | – | G | G | L | L | L (repo_map, symbol_context) | – | – |
| `CALLS` and their strategies | G (case tables, fixtures' `edges`) | – | – | G, J by case | G | L, J | L (by merge key) | L (Q4, who_calls) | – | – |
| Violations, roles and layers | G (convention fixtures) | – | – | G | G | L | L | L (violations) | – | – |
| Macro links (`CONSUMES`, `CALLED_FROM`, `DEPENDS_ON`) | G (`test_linker.py`) | – | – | – | G (who_consumes) | – | L | L (Q1, Q3) | – | – |
| The writer: persistence, merge keys, orphan GC | – | – | – | – | G | – | L | – | – | – |
| MCP answers | G (`test_mcp_protocol.py`, fake store) | – | – | – | G | – | – | L | – | – |
| Refresh after an upgrade (`outdated`, re-index once) | partial (`test_daemon.py`, not read) | – | – | – | G (written again at the commit) | – | L (V24) | L (atlas_status) | – | – |
| Time | – | reported | – | reported | – | reported | – | – | – | L, J; nightly P |
| Memory | – | reported (peaks) | – | – | – | – | – | – | – | P (H7-D4) |
| Code shape, comments, neutrality | – | – | – | – | – | – | – | – | G | – |
| Cache: cold equals warm | – | P (H6) | – | P | – | – | – | – | – | – |
| The new hold-out, H5 against the commit before | – | – | P (H2-D21) | – | – | – | – | – | – | – |

The matrix is preliminary. Two cells were not read: `test_daemon.py`, and how much of the macro links `mcp-it.sh`'s
three small repos exercise.

## 9. Gaps, contradictions and uncertainties

### Artifacts that are missing or volatile

1. **There is no `live-check.sh` (H7 slice 4).** V21–V25's scripts existed only in `$S/val`, which a reboot empties.
   They were lost once (2026-10-22) and rebuilt from `$T`. Since 2026-10-24 they are in `indexer/scripts/live/`, not
   committed, and not yet run from there against the install.
2. **No dedicated comparison script for the after state.** `go_graph_diff.py`, one repo's `CALLS` in two pictures by
   merge key, is in `$T` (2026-10-21, PR #20) and is not persisted. `graph_vs_dry.py` compares two pictures' `CALLS`
   with the dry-runs. Diffing the other lists and the golden answers was done with commands typed in the session
   (recovered, V23 and V25).
3. **`golden.py` holds private names.** The repository holds a sanitized rewrite that reads a private calls file.
   For PR #27 that file, and the original, are in `.local/indexer/pr27/`, on this disk only, with no backup.
4. **The micro-graph judgment tools** (V11, V12) and the per-commit protocol (V13) were only in `$S`; they are now in
   `indexer/scripts/`. `why_a.py` (Go's per-site case attribution) was lost, and its reconstruction is partial, so it
   is not persisted (the catalog, §4).
5. **No recorded verdicts (H7-D2).** The judgments of V09, V11 and V12 survive only as prose and totals in the
   handoffs and PR bodies. Which sampled items were judged, and how, is not recoverable item by item.
6. **Few scripts for V19.** Two are persisted, both reconstructed from `$T`: the walk's own check (`walkcmp.py`)
   and C#'s type facts check (`dump.py`). Go's, `tools/list`'s and the ASTs' checks were not found in the
   recovered sources.
7. **Baselines not published (H4.1-D1).** Locally they are directories on one machine.
8. **`install-check.sh`'s output** for the 2026-10-24 reinstall was not seen. A run on 2026-10-26, after the Neo4j
   container was recreated, passes; it shows the install that day, not on 2026-10-24.
9. **PR #27's live data has no backup.** The before picture, the dry-runs and the golden calls were copied on
   2026-10-24 from the volatile `$S` to `.local/indexer/pr27/`, checked by SHA-256. That folder is ignored by git and
   private, and lives only on this disk. Being ignored by git is not a backup, and no other copy was checked.
10. **The image behind PR #27's micro base runs is untagged.** `$C/micro` holds a base for `main`'s tree at `274d63b`
    only with the image `927f5b4115c5`, which Docker keeps on 2026-10-26 without a tag, so a prune would remove it.
    Without it, those base runs cannot be extended to another repo with the same image. Found on 2026-10-26.
    Later that day `f07550cbe2e2`, the image of the base made for `main`'s tree, lost its tag as well. The tag now
    names `9e6dd3753826`, which has the same layers and differs only in compose's service label. So `micro.sh` will
    make a new base on its next run.
11. **The live install was down after the reboot of 2026-10-26.** Its Neo4j looped on restart: `neo4j.conf`, in the
    container's own layer, held NUL bytes, and a setting was appended at each start (§3; the operational workflow,
    §3.4). Until the author recreates the container, no live step can run, and the live state cannot be read.
    **Resolved later on 2026-10-26.** The author recreated the container. The `neo4j_data` volume kept the graph: 10
    snapshots and 16,030 nodes, which is the before picture's 16,020 plus one `IndexRun` per snapshot.

### Contradictions between the docs and the facts

1. **PR #27 is merged, but the docs say otherwise:** the ROADMAP ("is done and goes to review") and the H5 handoff's
   state ("done on 2026-10-23, before its review") say otherwise, and `docs/history.md` has no line for it. The
   pattern of PR #26 is to update them in the golden round's docs PR. **On 2026-10-26** the ROADMAP's and the
   handoff's state were corrected in the working tree to "merged as PR #27 on 2026-10-24, its validation after the
   merge still open", which GitHub confirms. That edit is uncommitted. `history.md` and the eleventh round wait for
   the validation. The validation passed later that day; they now wait only for a docs PR.
2. **The guide's §5 and §6** (`docs/indexer-evolution.md`, in Portuguese) are out of date:
   - they say "42 repos fixados por SHA, 41 com gabarito" (55 and 54 now);
   - they place the current baseline in `H2-roadmap.md` (it is in the corpus report);
   - they say the script's docstring gets the new counts (H5 step 9 removed the counts from it);
   - §6 still points at `mcp/server.py` and `build_server(store=Fake)`, from before the MCP split.

   H4 phase 0b rewrites the guide after H5.
3. **H5-D14 asks for a sample "per case and repo"**, and PR #25's body says its samples were so, while the C# PRs' tool
   sampled per kind of change across repos
   (V11).
4. **H5's protocol item 4 names 12 repos,** and the step 5 PRs judged 23 or 25. The extended sets are recorded only
   in `$S`.
5. **The corpus report's "H5 steps" table** gives summed times on every row but the last one (H5-D17: "255 s wall").
   A wall time and a summed time are not comparable.
6. **`test_mcp_neo4j.py`:** "14 cases" in the H5 handoff and the corpus report, and 12 test functions in the file
   now. **Resolved on 2026-10-26 by a static count, not a pytest collection.** At `849b2cd` (2026-10-19) the file had
   11 functions, two of them parametrized with 5 values in all, so 14 cases. `7268642` (2026-10-21) added a twelfth
   function, so 15 cases now. The two docs give the count of their date.
7. **H7 lists "One cause per commit" and "Every diff item judged" among its gates,** and `gates.py` has five gates,
   neither of them among the five.
8. **The base of the micro comparison** differs by context: `micro.sh` uses `main`'s tip, `micro-fresh.sh` the merge
   base, and CI the merge commit's first parent (V10).
9. **The H6 timing rule** (the median of 3 interleaved runs) is not what the PR-level comparisons did (single runs
   alone on one image, V17).
10. **PR #27's body ticks an item that was not done.** The last line of its test plan on GitHub, "[x] After the merge:
    the graph's picture after, and the eleventh golden round", is ticked, and neither exists (§3). Found on
    2026-10-26; the PR was not edited. Later that day the picture after was taken; the round still does not exist.

### Uncertainties

- **I:** for C#, a commit's diff stood for a case's attribution. This is inferred from the commit order and the
  per-commit runs; no per-site C# attribution file was found.
- **P:** "the next refresh re-indexed none" after the 2026-10-24 reinstall. `changed: 0` on the latest scheduled
  runs suggests it, but the logs were not read.
- **I:** that the eleventh round should follow the tenth's format and branch name (`docs/golden-eleventh-round`).
  This is from the pattern of #21, #24 and #26; nothing fixes it.
- **U:** the content of the CI artifacts of PR #27's run, and of the draft release `h6-step1-results`.
- The previous session's last two requests (the 5.1 handoff, and a first version of this inventory as
  `docs/indexer/01-validation-inventory.md`) were stopped before any file was written. This document uses the path
  the current request gives.

## 10. Next steps for the four following documents

The split below is a proposal. Each document should give, for its procedures, the exact commands, the inputs and
outputs, the pass criteria and a worked example from a past PR. It should also close the gaps above that belong to
it, at least by writing down what the code does not hold yet.

| # | Proposed document | Procedures | What it must settle |
|---|---|---|---|
| 2 | **Reference sets and runs** (`docs/indexer/reference-sets-and-runs.md`) | V01–V04, V07, V10 | how to prepare the clones, run the corpus, the hold-out and the micro set locally and read their reports; the labels; the base to use and when (contradiction 8); the extended micro sets as a named list (contradiction 4); promoting a baseline; the micro base after a reinstall; the hold-out's rules |
| 3 | **Judgment and statistics** (`docs/indexer/judgment-and-statistics.md`) | V05, V08, V09, V11, V12, V14, V17–V19 | the decision rules (accept, reject, fix in the same PR, record as a gap), with H2-D11/D14, H5-D10…D17 and the author's widening rule; the classes and kinds of `CALLS` changes; sampling: the seed, N per kind or per case, and how a case is attributed (contradiction 3); the loss analysis; timing statistics (contradictions 5 and 9); a format for verdicts to propose for H7-D2 |
| 4 | **Graph and live validation** (`docs/indexer/graph-and-live-validation.md`) | V20–V25 | the two phases before and after the merge, from PR #5's plan to the tenth round; the picture's 15 lists and how to diff them; the merge keys; the golden calls described without names, and how a tenant-free version could live in the repo (gaps 1–3); what `live-check.sh` must do (H7 slice 4) |
| 5 | **The refactor cycle, runbook and continuity** (`docs/indexer/refactor-cycle-runbook.md`) | V06, V13, V15, V16, V26–V31 | the per-PR runbook for a refactor and for a change of behavior; CI and its labels; the commit and PR discipline; the scratchpad's layout and what must move to `$C` or the repo; recovery from a transcript; the Docker and zsh pitfalls; privacy |

**The second document was written on 2026-10-26**, under the name its request gave:
[`benchmark-and-statistical-protocols.md`](benchmark-and-statistical-protocols.md). It covers the measured part of
rows 2 and 3:

- the runs, their comparisons, formulas and thresholds (V07, V08, V10–V13, V17–V19, V21–V23 and V25);
- V03 and V04, as inputs and as rules.

It leaves the rest of rows 2 and 3 to the later documents: preparing the clones and the lists, the decision rules, and
a format for verdicts.

**The third document was written on 2026-10-26**, also under the name its request gave:
[`semantic-judgment-and-regressions.md`](semantic-judgment-and-regressions.md). It takes the decision rules of row
3 (V05, V09, V11, V12) and the golden round's verdicts (V25). It maps the sources' own terms for gains, losses,
errors and regressions, and proposes a verdict record for H7-D2, labelled as a recommendation. Preparing the clones
and the lists (V01, V02) is still for a later document.

**The fourth document was written on 2026-10-26**, as requested:
[`operational-workflow-and-continuity.md`](operational-workflow-and-continuity.md). It takes the continuity part of
row 5 (V29, V30), the authorization boundaries for running things, and the order of the phases. Row 5's runbook for
CI and the commit discipline (V26, V28) is referred to there, not detailed.

**The fifth, written on 2026-10-26, is the entry point:**
[`validation-and-continuity.md`](validation-and-continuity.md). It indexes the others, gives the state of H5 and PR
#27, a coverage matrix, and the audit of the series made that day, with its corrections and the contradictions it
left open.

Before or alongside these documents, the evidence suggests three actions. Each needs the author's decision:

1. **Finish PR #27's validation:**
   - take the after picture into `.local/indexer/pr27/``after/`;
   - diff it with `.local/indexer/pr27/``before/`, after checking that copy with its `SHA256SUMS`;
   - run V21 with both pictures;
   - take the golden answers after;
   - write the eleventh round, the `history.md` line and the ROADMAP and handoff states.

   The before picture exists, and the graph now holds the new build. Since 2026-10-24 a reboot no longer loses the
   before picture, but deleting the local folder would.
2. **Copy the volatile tools out of `$S`.** Done on 2026-10-24 for everything safe to version, into
   `indexer/scripts/` (the catalog). The private part, PR #27's golden calls and live data, was copied on the same
   day, with the author's authorization, to `.local/indexer/pr27/`, outside git. It still has no backup.
3. **Make the micro base for `main`'s current tree and image** (`micro.sh --base-only`) before the next local protocol
   run.
