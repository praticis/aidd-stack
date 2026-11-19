# Phase 1 — Complete micro (multi-language SCIP)

> The micro level of the graph: files, symbols, `CALLS` and `IMPORTS`, from every language. tree-sitter is the base and
> SCIP an enrichment per repository (ADR-002); before SCIP come the indexer's refactor, the extraction pipeline and the
> new hold-out. The `atlas` MCP's interface and guide, and the references that bound the graph's edges, are here too.
> The fields are H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

- [ ] F1.1 Integrate SCIP indexers (Go, TS, .NET, Python) into `indexer/`; automatic stack detection by manifest;
  per-repo config in `atlas.yaml`, keyed by the repository's name or a glob (excludes, connectors)
  - **Sketch:** missing the first language (ADR-002 names Go, with `scip-go`), what running it in the indexer's
    container needs (a dependency cache; a private registry's credential only by the name of its variable), how a change
    to a repository's config re-indexes it, since the commit alone no longer fixes the graph, and the number F1.2 must
    beat; first step: the share of calls resolved only by name, per language, on the micro set
  - **Verified by:** anyone
  - **Depends on:** F1.19
- [ ] F1.2 SCIP → graph converter (definitions, resolved references, IMPLEMENTS/EXTENDS, types) + a resolver for the
  HTTP layer: a hook in `http_base` (by name by default, SCIP when the snapshot has an index) consulted only at the
  points of indecision that F1.14 recorded as `needs-resolver` — without an index, HTTP stays as today (ADR-002,
  decision 3)
  - The debts due here are the open rows of `docs/tech-debt.md` whose Due is F1.2 or a `fix(<scope>)` PR before F1.2;
    F1.2 is not ticked while one is open. SCIP is a possible remedy for the ones due in F1.2, not a proven one; the first
    case of TD-001 may be fixed in the resolver earlier
  - **Sketch:** missing, per language, the share of calls resolved by name it must lower (ADR-002's number to beat) and
    the counts of the scorecard it must move; first step: a converter for the first language F1.1 integrates, its edges
    compared with the tree-sitter graph on the micro set
  - **Verified by:** anyone
  - **Depends on:** F1.1, F1.27, F1.28
  - **Not to do:** bound the edges a SCIP index writes by a reference that shares their compiler: the bounds of F1.27
    and F1.28 judge the tree-sitter edges and the snapshots with no index
- [ ] F1.3 tree-sitter, the base of every language (ADR-002), for the languages no SCIP indexer covers (Vue SFC, SQL,
  YAML, templates)
  - **Sketch:** missing what is extracted from each (symbols, imports, routes), the first one, and what measures it;
    first step: what the indexer reads today from the `.vue`, `.sql`, `.yaml` and `.proto` files it already classifies
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.4 Incremental indexing (the per-file summary cache is F1.18's, and orphan removal per snapshot `(repo, ref)`
  exists): `git diff` → touched packages → partial re-index, writing only what changed
  - **Done when:** after a push that changes one file, the refresh re-indexes only the packages the diff touches and
    writes only the records that changed, and the snapshot holds the records a full re-index of that commit writes, on
    the micro set
  - **Verified by:** anyone
  - **Depends on:** F1.18
- [ ] F1.5 Semantic search over the symbols, not decided: a reference first (search questions with an expected list,
  scored against `find_symbol` with `match="fuzzy"` as the baseline), whose result decides whether it is built; if it
  is, Neo4j's vector index is the candidate store, and the `search(query)` once planned in F1.7 is this item's
  - **Sketch:** missing the decision it waits for, whether the Atlas searches by meaning at all; no consumer asks for it
    today; first step: the search questions and their expected lists, scored against `find_symbol`, for the author to
    decide on
  - **Verified by:** the author (whether it is built is his decision on that score)
  - **Depends on:** nothing
  - **Not to do:** let the extraction read a vector, or a snapshot's comparison include one
- [ ] F1.7 `atlas` MCP: `trace_flow(entry_point)`, the micro flow from an entry point (callers and callees already
  answer through `who_calls` and `symbol_context`)
  - **Sketch:** missing the shape of its answer, how deep it goes, and the golden question that proves it; first step:
    a question about an entry point's flow, with its expected answer, on the repositories `mcp-it` indexes
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** rename a tool `docs/atlas-interface.md` lists
- [x] F1.8 *(found done on 2026-11-19, with two differences: a query with no `ref` reads the repository's default
  branch, and a micro edge carries no `ref`, both its ends being in one snapshot)* `ref` support: index `main`
  (baseline) and `develop`; nodes/edges with `ref`; queries with an optional `ref` (default: develop if it exists)
- [ ] F1.9 Git metrics as attributes: `last_touched`, `churn_90d`, `authors` (hotspots and "who touches this")
  - **Sketch:** missing where the history comes from (the extraction reads an exported tree, with no history), the
    window, the tool or field that answers it, and whether `authors` may put people's names into the graph; first step:
    the metrics of one repository of the micro set, read from its mirror at a snapshot's commit, with their cost
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.11 `aidd status` shows the last run of each `(repo, ref)`, a failed one too: the runs are recorded, but a
  failed run is not linked to its snapshot, and the command shows neither a run's duration nor its errors
  - **Done when:** `aidd status` lists, per `(repo, ref)`, the last run with its status, duration and first error, a
    failed one included, also for a repository that never indexed with success
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.12 Widen the golden questions to 20; an `aidd eval` script that runs them all and reports recall
  - **Sketch:** missing what recall is measured against: the five documented questions have an expected text and a
    Cypher check, not a score; first step: for each golden call, an expected answer a script can compare
  - **Verified by:** the author (the golden calls run on his tenants)
  - **Depends on:** nothing
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
  file (who mounts what, with which prefix), never holding the trees of other directories.
  - **Done when:** grafana indexes under a memory ceiling of 2 GB and, on a medium repo, batched extraction is identical
    to the whole one (the HTTP corpus with `--baseline` gives the diff)
  - **Output:** measured along with it, the cost of HTTP on repos without routes it can read (netbox: 49 s of 107 s
    with 0 routes and 0 calls in corpus v2; zulip 17 s of 47 s)
  - **Verified by:** anyone
  - **Depends on:** F1.18
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
  - **Done when:** each slice of H7's table meets its own Done when
  - **Verified by:** the author (slice 6 is his to turn on, and H7-D2 and H7-D4 are his decisions)
  - **Depends on:** F1.18
  - **In progress:** H7
- [x] F1.16 **A typed call and the overrides it may run** (H5-D27): `CALLS` is the declaration the receiver's type
  gives, in every language. C#'s and Python's type indexes write `EXTENDS` and `IMPLEMENTS` from the bases they read,
  and `CALLS` marks a call that does not dispatch (`super()`, `base.`); `who_calls` and `impact_of` add the callers of
  the methods a method overrides or implements, marked as a dispatch that may happen, and list its overrides. Go's
  embedding promotes and never dispatches; its interface calls are a debt. Seven PRs (H5-D30 to H5-D35):
- [ ] F1.17 The indexer's refactor before SCIP: the steps of H5 (`docs/handoffs/H5-indexer-refactor.md`), built toward
  H6's design
  - **Done when:** every step of H5's table meets its own Done when, but turning the shape report's blocking on (H5-D3,
    H7's slice 6); `shape.py` reports nothing over a target but `cli.py` and what H5-D43 accepts; no debt due in a step
    of H5 is open
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **In progress:** H5
- [ ] F1.18 Plug the extraction pipeline in: the map, the reduce and the per-file cache (ADR-004; H6 step 4,
  `docs/handoffs/H6-extraction-pipeline.md`)
  - **Done when:** the case of `test_repo_view.py` on a function of the root package passes without its xfail; a cold
    run, a warm run and the baseline give the same corpus, hold-out and micro set
  - **Verified by:** anyone
  - **Depends on:** F1.17
  - **Not to do:** change the graph in the pull request that plugs it in: Go's two reads of an imported package's
    directory become questions to the view in a pull request of their own, before it
- [ ] F1.19 The new hold-out, measured once (H2-D21): repositories the rules never saw, after H5 and H6
  - **Done when:** its repositories are pinned and their lists committed before the extractor runs on them; it is
    measured once with `main` and with the commit before H5; each difference between the two is explained by a judged
    case of H5's changes of behavior, or is an H5 regression, fixed or registered as a debt (H5-D12); it is judged once
    at the source, as `docs/indexer/method.md` §4.11 says; what it shows is a handoff of its own
  - **Verified by:** the author (he chooses the repositories, and the measure is taken once)
  - **Depends on:** F1.18
- [ ] F1.20 The size of the `atlas` MCP's answers, and a budget per tool: each answer enters an agent's context
  - **Sketch:** missing each tool's budget and what an answer over it does; first step: the bytes of each tool's answer,
    on the calls `mcp-it` makes over its repositories
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.21 The stable interface, pinned by a test: `docs/atlas-interface.md` is written by hand, and nothing checks it
  against the code
  - **Done when:** one data file under `indexer/` lists the ten tools, each field `docs/atlas-interface.md` promises
    (`checked` of `violations` included) and the keys of a convention file it promises; a test checks the server's tools
    against it (the ten names as a subset) and each field it lists; a test loads a fixture convention by path and finds
    the names of the convention, its roles, layers, architectures and rules in the answers as the file writes them; a
    step of the `debts` job compares `docs/atlas-interface.md` with the data file; `who_calls`'s description names no
    key its answer lacks
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.22 The Atlas's usage guide, in what every MCP client receives: the tools' descriptions, the server's
  instructions, and an MCP prompt that replaces the `scan` skill
  - **Done when:** the server's instructions and the prompt each name every tool `docs/atlas-interface.md` lists,
    `violations` included, and a test checks those names against the server's tools; the instructions and the tools'
    descriptions together are no larger than before the item, held by a test; the prompt teaches `atlas_status` first,
    indexing on demand (`refresh --wait`), the current branch (`index --ephemeral`), comparing a snapshot's `sha` with
    `HEAD`, how to read a `CALLS` `strategy`, `violations`' `checked: false` and the fallback to reading the tree,
    naming the host commands as `docs/atlas-interface.md` does; `docs/atlas-interface.md` names the prompt; a new
    session that reads only what the server gives answers three of the golden questions on the repositories `mcp-it`
    indexes, each with the right tool
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** make it a skill; teach the process half of `scan`
- [ ] F1.23 A convention handed over by path re-indexes when its file changes: the refresh compares the commit and the
  indexer's build, and a convention file is in neither
  - **Done when:** a test changes a convention file a tenant names by path, and not the commit, and the next refresh
    re-indexes the snapshots it applies to; with the file unchanged, the refresh re-indexes none of them
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F1.24 `cli.py` at the shape targets: H5 leaves it over them until the removals that touch it (H5-D5, H5-D6)
  - **Done when:** `cli.py` and the modules it is split into are under the targets in `shape.py`'s report; the pull
    request is a `refactor:` whose corpus, hold-out and micro set give `0 repo(s) differ`; the build's fingerprint
    covers the new modules
  - **Verified by:** anyone
  - **Depends on:** N5, N6
  - **Not to do:** rename a command or a flag the host's script or the installer calls
- [ ] F1.25 Another code-graph tool measured on the hold-out by the corpus's own evaluator, so the Atlas's numbers can
  be compared with another tool's
  - **Sketch:** missing whether a tool from outside may be measured on a hold-out that is measured once, and which
    tool; first step: `http_corpus.py` scores another tool's routes and calls on the corpus, with the same evaluator
  - **Verified by:** the author (the hold-out is measured once, and the choice of the tool is his)
  - **Depends on:** F1.19
- [ ] F1.26 The independent review of a pull request in CI, and its record (H8, slices 2 and 4,
  `docs/handoffs/H8-independent-review.md`): an advisory agent's comment, never a gate, and per pull request the
  objections, how many held and the tokens spent
  - **Sketch:** missing which pull requests get it (H8-D5), who pays its tokens, and where the record lives; first
    step: the author's answer to H8-D5
  - **Verified by:** the author (H8-D5 is his to answer, and he pays the tokens)
  - **Depends on:** nothing
  - **Not to do:** make it a required check
- [ ] F1.27 C#'s typed call edges are bounded by an independent reference
  - **Done when:** each C# repo of the micro set has `confirmed` floors and `contradicted` ceilings per strategy in
    `reference_floors.txt`, judged by a compile-only reference built on Roslyn (the repository's `.cs` files and pinned
    reference assemblies; no restore, no MSBuild evaluation, nothing of the repository built or run), which counts apart
    the sites it cannot bind and accepts an edge to a declaration that implements or overrides the one it binds;
    TD-072's case is written from its reading, or the debt is closed; the rows are kept by content, keyed by the clone,
    the tool's source and its own image, made on a push to `main`, and a run that does not finish fails the `micro` job;
    the clones' cache key depends on the pins only; `docs/indexer/method.md` §4.4 has a table of facts by language, each
    with its reference, the item that owes it, or `Unknown` with the reason
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** run a restore, an MSBuild evaluation or a SCIP indexer in CI (a SCIP index is a second reference, run
    once in a sandbox); read a precision over the sites the reference cannot bind; bound a by-name share
- [ ] F1.28 Go's typed call edges are bounded by an independent reference
  - **Done when:** each Go repo of the micro set has `confirmed` floors and `contradicted` ceilings per strategy in
    `reference_floors.txt`, judged by a reference built on Go's own type checker that reads the standard library's
    source and no network, runs no `go list -export` and no cgo, and counts a call into a third-party package as
    `outside`; the rows are kept by content, keyed by the clone, the tool's source and its own image, made on a push to
    `main`, and a run that does not finish fails the `micro` job; the clones' cache key depends on the pins only;
    `docs/indexer/method.md` §4.4 has a table of facts by language, and it names Go's reference
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** run the repository's build or a SCIP indexer in CI; judge an edge to an implementer of an interface
    before the reference states the implementations
- [ ] F1.29 Python's typed call edges against an independent reference
  - **Sketch:** missing the checker that decides a Python call site without running code, and whether it decides enough
    of `dispatch` and `netbox` to bound; first step: the share of typed edges in those repos, and a static checker run
    offline on them, its undecided sites counted (the scope index already has CPython's `symtable`)
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** a runtime oracle (traces, a test suite) on a repository the Atlas does not own

**Phase exit:** any workspace repo indexable with 1 command; the `atlas` MCP answering the golden questions with facts
from the graph.
