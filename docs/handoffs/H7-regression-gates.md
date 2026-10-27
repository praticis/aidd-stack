# Handoff H7 — Regression gates in CI: the method as checks

> Paste this file (or ask for `docs/handoffs/H7-regression-gates.md` to be read) at the start of a new chat. Before
> anything else, the chat should read:
> - `AGENTS.md`, the entry point;
> - `docs/decisions.md`: H2-D4…D21, the method's decisions;
> - `docs/corpus-report.md`: "How it is measured" and the baselines table;
> - `docs/handoffs/H5-indexer-refactor.md`: the regression protocol every step follows;
> - `docs/handoffs/H6-extraction-pipeline.md`: the cache, and "How it is measured";
> - `docs/handoffs/H4.1-contributor-path.md`: the contributors these gates serve. H4.1-D5 (the corpus in CI) is
>   absorbed here;
> - the fifth round of `docs/golden-questions.md`: how PR #5 was validated on a live install.
>
> **State (2026-10-22):** slice 1 merged on 2026-10-19 (PR #10 and PR #11), and slice 1c on 2026-10-22 (PR #22):
> `main` requires `tests` and `gates`. Slices 1b and 2 to 6 are open. The author made decisions D1, D3 and D5 (see
> "Decisions made"); D2 and D4 are still to make.

## Context in one paragraph

Today the method's checks run by hand: the corpus against a baseline, every diff item judged at the source, the
hold-out identical, `0 repo(s) differ` for a refactor, no win lost, the live install before a merge. They work
because the author and one agent run them every time. A contributor, or their AI, may not. H7 turns what is
mechanical in the method into CI gates that fail a PR, and shrinks what needs judgment to a short list, each item
shown with its source line. The gates use only deterministic measures, so they do not flake, and they protect what
H2 and F1.14 achieved from any PR, the author's included.

## What becomes a gate

| Gate | From | Fails when |
|---|---|---|
| **Precision ratchet** | H2-D11 | the list precision of any repo or language is lower on the branch than on the baseline |
| **No win lost** | PR #5's validation | an expected pair the baseline found is missing on the branch, or an item of the `checked` sample judged right is no longer extracted |
| **Hold-out untouched** | H2-D20, H2-D21 | the hold-out's ids change in a PR without the `holdout-measurement` label |
| **A refactor changes nothing** | H5 | a refactor PR (its branch, one of its commits or the `refactor` label) changes any id of the corpus or the hold-out, or any record of the micro set's dry-runs |
| **The micro graph judged** | H6 step 0 | the full dry-runs of the micro set (files, symbols, `CALLS`, `IMPORTS`, violations) differ from the baseline's and the difference has no verdict |
| **One cause per commit** | H5's pitfalls | one commit touches both the extractor (`indexer/aidd_indexer/`) and `indexer/tests/corpus_expected/` |
| **Every diff item judged** | the cycle of a change | an item the classifier marks "to judge" has no verdict (H7-D2) |
| **Cold equals warm** | H6, once the cache is in | a run with the cache gives a different result from one without it |
| **Memory** | F1.13, H6 | a repo's peak memory grows past a tolerance set from H6's measured spread (H7-D4) |
| Tests, hygiene, shape | they exist | as today. The shape has been a ratchet since 2026-10-21 (H5-D9): a function or a module over a target that is new or grew fails; full blocking comes when the author decides (H5-D3) |

**The micro set** is the 12 repos of H5's protocol item 4:

- C#: eshop, jellyfin, btcpayserver, umbraco;
- Go: vikunja, gitea, mattermost, grafana;
- Python: dispatch, netbox;
- TS: ghost, outline.

Each repo runs a full `aidd index --dry-run`, and the result is compared record by record. The HTTP corpus does not
run the resolver, so without this set no gate sees `CALLS`. That is how H6's step 0 found a resolver that was
quadratic in Go and C#, which no corpus run had shown.

Time never gates: shared runners are noisy, and the corpus already varies about 28 % between runs on one machine.
Time is a nightly trend instead.

## What stays judgment, and how CI shrinks it

Judging an item at its source is what keeps the expected lists evidence, and an LLM does not decide it. CI
classifies the diff the way a judgment starts:

- **gain:** a new item that is in the expected list. Nothing to judge;
- **regression:** an expected item that went missing. The gate fails;
- **to judge:**
  - a new item outside the expected list: a false positive, or a real route the list lacks (H2-D15);
  - an item outside the list that went missing: probably a false positive removed;
  - any change outside a list's scope.

The PR comment lists the "to judge" items, each with a link to its `file:line` on GitHub at the pinned SHA and a few
lines of context, so a reviewer, or their AI, judges each one in seconds. The verdicts are recorded (H7-D2), and the
PR does not merge with an item unjudged.

## The pipeline

```
 every push to a PR (minutes)
   tests and fixtures · code hygiene · shape report · docs links and repo paths · the MCP against an ephemeral Neo4j

 a PR that touches indexer/** (to be measured; likely 15–25 min)
   the corpus of the branch vs the baseline of main's tip     ──►  gates + the classified diff, in the job's summary
   the hold-out of the branch vs its baseline                  ──►  gate (a count, never the items)
   the micro set's dry-runs vs the base's                      ──►  gate (the `graph-change` label for a judged change)

 a push to main
   the corpus, the hold-out and the micro set run when no baseline for that code is cached, and are cached as the
   new baselines, keyed by the code's tree (H7-D1); later, the corpus report's numbers come from them

 nightly, on main
   corpus + hold-out, three times: the medians of time and memory per repo as a trend, with an alert past the noise
```

## On GitHub's runners

- **Capacity:** a public repo's standard runners are free, with 4 vCPU and 16 GB, enough for 3 to 4 corpus repos at
  once (the largest peak is mattermost's, 2.2 GiB). The clones are 3.6 GB, cached between runs and keyed by the pins
  in `CORPUS`. `http_corpus.py` already clones each repo at its SHA.
- **The baseline is the merge base's,** not the tip of `main`; otherwise a PR inherits another PR's diff. When the
  merge base has no published baseline, the job runs it first.
- **Forks:** the corpus job runs on `pull_request`, with a read-only token and no secrets. It uploads the report as an
  artifact, and a second workflow (`workflow_run`), which never checks out the PR's code, posts the comment. Never
  `pull_request_target` with the PR's code checked out.
- **Third-party code never runs:** the job parses the corpus repos and builds or tests none of them.

## The live validation

The portfolio's install cannot move to GitHub: its repos are private, and a self-hosted runner on a public repo runs
code from any fork's PR. So it has two parts:

- **Local, for the maintainer:** `indexer/scripts/live-check.sh` automates what PR #5 did by hand: a dry-run of `main`
  and of the branch on each snapshot at its SHA (with `-w` on the mounted code), pictures of the graph before and
  after the reinstall, the MCP's answers recorded through HTTP, and their diff. Its output stays on the machine.
- **In CI, on a demo tenant of public repos** (H4.1-D4): the compose stack starts in the runner, indexes the demo with
  `main`'s image, takes a picture, re-indexes with the branch's image, takes another, and runs golden questions
  written for the demo.

## Slices

| # | Slice | Done when |
|---|---|---|
| 1 | Baselines cached on every push to `main`; the corpus, the hold-out and the micro set on a PR; the gates of precision, no win lost, hold-out, refactor and the micro graph; the classified diff in the job's summary | a PR's checks say `0 repo(s) differ`, and a test PR that drops a route fails |
| 1b | The classified diff as a comment on the PR, through the two-workflow pattern | a fork's PR gets the comment |
| 1c | The MCP and the graph writer against a throwaway Neo4j, in the `tests` job: `mcp-it.sh`, with the graph read back against a dry-run of each snapshot by the writer's merge keys | a writer that drops a record or a field fails a PR |
| 2 | One cause per commit, `CODEOWNERS` on the expected lists, the verdicts recorded and checked | a PR with an unjudged item cannot merge |
| 3 | The nightly trend of time and memory, for the whole pipeline phase by phase, the resolver included | a week of medians with their spread |
| 4 | `live-check.sh`, and the demo tenant in CI | the demo tenant's golden questions in a PR's checks |
| 5 | After H6: the cold-equals-warm gate, and the PR corpus run only on the files the PR changed | a PR's corpus job takes a fraction of a cold run |
| 6 | The shape report blocks (H5-D3) | the author turns it on |

## Slice 1 as built

`.github/workflows/indexer.yml` runs on every pull request and every push to `main`:

| Job | What it does |
|---|---|
| `changes` | decides whether the indexer changed (`indexer/**`, the graph's schema in `neo4j/init/`, or the workflow). The other jobs are skipped when it did not, and a skipped job passes, so a docs-only PR is not blocked |
| `tests` | builds the image (with Docker's layer cache) and runs `test.sh`, then `mcp-it.sh` (slice 1c): every atlas tool against a throwaway Neo4j, and the graph the writer leaves read back against a dry-run of each snapshot |
| `corpus` | restores the base's corpus and hold-out runs from the cache, or computes them at the base; runs the branch's; counts the hold-out repos that changed, so that its items never reach an artifact |
| `micro` | runs `micro.sh` against the base, whose dry-runs come from the cache or are computed |
| `shape` | the shape ratchet: `shape.py --against` the base fails on a function above complexity 9 or a module above 300 lines that is new or grew (H5-D9) |
| `debts` | `debts.py` checks `docs/tech-debt.md` against the debts' tests and the ROADMAP. It runs on every PR, docs-only ones included, so it can be a required check of its own |
| `gates` | reads the PR's labels and its commits' subjects when it runs, and hands them to `gates.sh`. `gates.py` decides whether the PR is a refactor and judges the micro graph, so a local run decides the same. It writes everything to the job's summary and fails when the `shape` job did |

- **The base** is the first parent of the PR's merge commit, which is `main`'s tip. Both sides then hold the same
  other PRs, so a PR never inherits another's diff.
- **The baselines** are keyed by the tree of `indexer/` (the corpus) or of `aidd_indexer/` (the micro set), not by a
  commit. A commit that does not touch the code finds the same baseline.
- **A refactor**, where any difference fails, is read from the PR itself (the author's rule): its branch starts with
  `refact/` or `refactor/`, or one of its commits starts with `refactor:` or `refact:`, with or without a scope. The
  `refactor` label says the same. One refactor commit makes the whole PR strict, so a refactor and a change of behavior
  go in separate PRs.
- **The labels for decisions:**
  - `holdout-measurement`: the hold-out may change. In one of H5's changes of behavior, the author decides it from
    the hold-out's aggregates only, without opening its items (H5-D13);
  - `graph-change`: a difference in the micro graph, judged at its source, passes.

  After adding one, re-run the `gates` job alone. A run started by the label itself would report its skipped checks
  as passing.
- **The checks to require on `main`:** `tests` and `gates`. `gates` runs even when a job it needs fails, and then
  fails, so a broken run never passes as skipped.
- **Locally, the same gates:** `corpus.sh --label` for both sides, `micro.sh`, then `gates.sh` with the branch and its
  commits, and `shape.py --against main` (`indexer/scripts/README.md`).

## Slice 1c: the writer read back

The corpus and the micro set compare dry-runs, so no check reached the writer: only a live install did, and only when
someone looked. The eighth golden round compared the live graph's `CALLS` by hand with the dry-runs of `main` and of
the branch, counted by the writer's merge key, and that comparison now runs on every PR:

- `mcp-it.sh` already wrote a small graph with the real writer for the MCP's tests. It now also leaves a dry-run of
  each snapshot, and `tests/test_graph_writer_neo4j.py` reads every section back from the graph: modules, files,
  symbols, `CALLS`, `IMPORTS`, endpoints, HTTP calls and violations, field by field. A call is counted by its caller,
  callee and line, an import by its file, target and spec, as the writer merges them;
- in a tenant of its own, one repo is written with a file, again without it, and once more at that commit, as the
  refresher does after an upgrade. A record the second write should drop, or one the third should keep, is checked
  too;
- before it joined CI, the test was run against three broken writers, and each failed it: one that kept the orphans
  (caught only by the repo written again without a file, which no MCP test sees), one that wrote no strategy on
  `CALLS`, and one that merged imports without their spec.

## Decisions made (2026-10-19, with the author)

| # | Decision | Why |
|---|---|---|
| H7-D1 | **The baselines live in the Actions cache**, keyed by the code's tree. A push to `main` fills it, and a miss recomputes the base in the PR's run. GHCR comes later, if contributors need to download baselines | The extraction is deterministic, so a baseline is derived data: what must not be lost is in git (the code and the expected lists). No infrastructure, no write token |
| H7-D3 | **The gates run on every PR that touches the indexer**, and every push to `main` fills the baselines | A gate that runs only when someone remembers is not a gate |
| H7-D5 | **Slice 1 now, before H6's step 1** | Better now than later, while the context that built the method is fresh: no gain may be lost |
| H7-D6 | **The judgment of a change of behavior is automated, not checked by a person** (2026-10-27) | A person's check is not feasible; what a script repeats, a person need not redo. It needs H5's per-site attribution (gap G1) and the verdict record (H7-D2) |

## Decisions to make with the author

| # | Decision | Recommendation | Why |
|---|---|---|---|
| H7-D2 | How verdicts are recorded | A file committed with the PR, one verdict and one reason per "to judge" item, checked by CI to cover them all | A checkbox can be ticked without judging; the file is also the record of why a baseline changed |
| H7-D4 | The memory tolerance | About 10 %. In H6's step 0, a container's peak varied 2–4 % across three runs | A tolerance below the noise flakes; one far above it catches nothing |

## Pitfalls

- **A flaky gate gets switched off.** Only deterministic measures gate: ids, precision and recall, the hold-out's ids.
- **Changing the ruler and the measured thing together passes any gate.** That is why one commit never touches both
  the extractor and the expected lists, and why the lists have code owners.
- **The wrong baseline.** The base is `main`'s tip, as the merge commit's first parent: never an older baseline.
- **A skipped job passes a required check.** Hence the `changes` job instead of a path filter, `always()` on `gates`,
  and labels read at run time instead of runs started by a label.
- **Disk on the runner:** clones, the image and Docker's layers. Measure the free space and prune.
- **A pin that changes** re-fetches its clone; the cache key includes the pins.
- **The comment on a fork's PR** needs the two-workflow pattern; a token with write access never meets the PR's code.

## How H7 relates to the others

- **H4.1:** H7 is the "checks in CI" part of the contributor path. H4.1-D4 (the demo tenant) and H4.1-D6 (code owners)
  are shared; H4.1-D5 is replaced by H7.
- **H5:** H7 runs H5's regression protocol on every push.
- **H6:** the cache makes the PR corpus run cheap, and adds the cold-equals-warm gate.

## Constraints and conventions

- Everything in the repo is in English; one-line conventional commits, with no body and no attribution.
- New code meets the shape targets: complexity ≤ 9, modules ≤ 300 lines.
- No real tenant or private project names, in the code, the workflows or the comments the bot posts.
- An LLM is never the parser, and never the judge of a gate.

## Expected deliverables

- The workflows (PR checks, the corpus job, the comment, the baseline publishing, the nightly trend).
- The diff classifier, next to `scripts/corpus_metrics.py`, with tests.
- `indexer/scripts/live-check.sh`, and the demo tenant's setup and golden questions.
- `CONTRIBUTING.md`'s part on what the bot's comment means and how to record verdicts (with H4.1).
- The decisions H7-D1…D5 in `docs/decisions.md`.
