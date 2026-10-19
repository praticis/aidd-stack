# AGENTS.md — the aidd-stack entry point

Read this first, whether you are a person joining the project or that person's AI. In a few minutes it gives the
context and says where everything else is.

## What it is

aidd-stack is a local stack for AI-assisted development across a portfolio of repositories. It indexes each repo's
code into a **graph** (Neo4j, database `atlas`), at two levels:

- **micro:** files, symbols, `CALLS` and `IMPORTS`;
- **macro:** the HTTP routes a service exposes, the calls it makes and the links between services.

The graph's tools reach the process skills (`scan` → `refine-business` → `refine-tech` → `implement`) through the
`atlas` MCP. Alongside come an Obsidian vault, vectors in Qdrant and a `knowledge` service holding what the project
has learned.

Extraction is **deterministic**: tree-sitter today, SCIP as an enrichment later. An LLM is never the parser, for
three reasons:

- the graph must be reproducible, the same commit giving the same graph;
- the graph must be measurable, as in the corpus;
- the graph must be cheap to keep current on every push.

SCIP comes in per repo, where resolution by name is not enough (ADR-002).

## Repo map

| Path | What it holds |
|---|---|
| `setup/` | `install.sh` (installs and updates `~/.aidd`), `install-check.sh` (install health), the `aidd` wrapper, the skills (`scan`, `refine-business`) and an example convention |
| `docker-compose.yml`, `gateway/`, `neo4j/`, `qdrant/`, `obsidian/`, `git/` | the infra: Neo4j with its schema (`neo4j/SCHEMA.md`), Qdrant, the MCPs and the nginx gateway, all on localhost only |
| `indexer/` | the `aidd-indexer` package: the `aidd` CLI, the refresher (`aidd daemon`), the `atlas` MCP and the `knowledge` service |
| `indexer/aidd_indexer/core/` | what all languages share: discovery, extraction, `CALLS` resolution, the HTTP extractor (`http_*`, `integrations.py`), the linker and the graph writer |
| `indexer/aidd_indexer/languages/<lang>/` | Go, TS/JS, C# and Python: tree-sitter queries, symbols, resolution and each language's HTTP scanner (ADR-003) |
| `indexer/conventions/` | architecture conventions as extensions (the reference one is `dotnet-praticis`) |
| `indexer/tests/` | the per-language fixtures (`fixtures/*/expected.json`), the corpus expected lists (`corpus_expected/`) and the tests |
| `indexer/scripts/` | the public corpus (`http_corpus.py`, `corpus_metrics.py`, `corpus.sh`) and the tests (`test.sh`) |
| `docs/` | the ROADMAP, the decisions, the history, the indexer guide, the corpus report, the golden questions, the ADRs and the handoffs |

## The architecture in one figure

```
 workspace repos ──(bare mirror, read-only)──▶ refresher (aidd daemon, every 15 min)
                                                        │ tree-sitter per language
                                                        ▼
            discovery → extract (symbols, imports) → resolve (CALLS) → HTTP (routes, calls)
                                                        │ conventions (roles, layers, violations)
                                                        ▼
                                  Neo4j "atlas" ◀── linker (CONSUMES, CALLED_FROM, DEPENDS_ON)
                                        │
                         atlas MCP (:3005, via gateway) ── 11 tools: atlas_status, repo_map, find_symbol,
                                        │                  who_calls, symbol_context, http_map, who_consumes,
                                        ▼                  impact_of, ref_diff, violations, cypher_readonly
                    process skills + knowledge MCP (:3006) + Obsidian vault + Qdrant
```

Every node and edge carries `tenant`, `repo`, `ref` and `commit_sha`; macro edges carry `confidence` and `evidence`.
A snapshot is one (repo, ref), and a snapshot written by another indexer build stays `outdated` until the refresh
re-indexes it.

## Principles

The full text is in the ROADMAP, under "Principles".

- **Orchestrator-independent:** MCP and skills only.
- **Deterministic extraction:** a gap that needs a type not declared in sight becomes `needs-resolver` for F1.2, with
  no heuristic.
- **Secrets never enter the index:** only the env var's name.
- **Every phase closes with the golden questions passing.**
- **Code shape:**
  - complexity ≤ 9 per function (`ruff C901`) and modules of at most 300 lines;
  - comments say only why, with no reference to docs or plan items.
- **No real tenant, client or private project name** in docs, code, tests or fixtures. The repo is public.

## How to install, test and measure

- **Install or update:** `./setup/install.sh` (asks in the terminal), then `./setup/install-check.sh`, which must end
  in "All checks passed".
- **Indexer tests:** `indexer/scripts/test.sh`, in the test container, with the tree's code mounted.
- **HTTP corpus (the extractor's yardstick):** `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-28`.
  - It must give `0 repo(s) differ`, or a diff judged item by item.
  - The hold-out: `--holdout --baseline 2026-10-18-v2-holdout-26`.
  - The clones live in `~/.cache/aidd-corpus`, and the numbers in `docs/corpus-report.md`.
- **The micro graph (files, symbols, `CALLS`, `IMPORTS`):** `indexer/scripts/micro.sh` dry-runs 12 corpus repos with
  `main` and with the tree, and compares the results record by record.
  - The HTTP corpus does not run the resolver, so a change to `CALLS` shows only here.
  - A refactor must give `0 repo(s) differ`. Any other difference is judged at the source, like a corpus diff.
- **The gates, in CI on every PR that touches the indexer** (`.github/workflows/indexer.yml`):
  - it runs the tests, the corpus, the hold-out and the micro set against `main`;
  - `indexer/scripts/gates.sh` then fails the PR when a precision drops, a win is lost, the hold-out changes or a
    refactor changes anything;
  - a refactor (a branch `refact/…` or `refactor/…`, or a commit `refactor:` or `refact:`) must change nothing;
  - the labels `holdout-measurement` and `graph-change` allow, after judgment, a hold-out measurement and a change to
    the micro graph. After adding one, re-run the `gates` job;
  - the same gates run locally with `corpus.sh --label` on both sides and `gates.sh`.
- **A change to the extractor follows the cycle** in the guide (`docs/indexer-evolution.md` §5):
  1. a fixture case that fails without the rule;
  2. corpus `--baseline`;
  3. judgment at the source;
  4. expected lists (H2-D15);
  5. a new baseline.
- **Before a merge**, also validate on a live install: a dry-run of `main` against the branch on each snapshot (with
  `-w` on the mounted code) and pictures of the graph before and after.
- **Golden questions:** `docs/golden-questions.md`, repeated after changes to the graph, the linker or the MCP.

## Where we are

- **Phase 0** (foundation) is done.
- **H2/F1.14** (the HTTP extractor measured on a public corpus of 55 repos) closed on 2026-10-19.
  - Precision against the lists: 98–100 % in every language.
  - The numbers are in the corpus report.
- **The order up to SCIP:**
  1. design **H6**, the extraction as a parallel map, a reduce and a per-file cache
     (`docs/handoffs/H6-extraction-pipeline.md`);
  2. **H5**, the indexer refactor that changes no behavior, built toward H6's design
     (`docs/handoffs/H5-indexer-refactor.md`);
  3. plug H6 in;
  4. the new hold-out;
  5. P2 (the indexer in its own repo);
  6. SCIP (F1.1, F1.2).
- The current state is in the ROADMAP, under "Where we are".

## Where to find things

| Question | Where |
|---|---|
| What is open, and in what order | `docs/ROADMAP.md` |
| Why a choice was made | `docs/decisions.md` and `docs/adr/` (ADR-002 tree-sitter vs SCIP, ADR-003 per-language modules) |
| What happened, and when | `docs/history.md`; the full old text is in git (`git show 1d73bb0:docs/ROADMAP.md`) |
| How the indexer decides (rules, the cycle of a change, the code map) | `docs/indexer-evolution.md` |
| The HTTP extractor's numbers and what is missing | `docs/corpus-report.md` |
| The graph model | `neo4j/SCHEMA.md` |
| The indexing process (sources, refs, refresh) | `docs/indexing-process.md` |
| The vault and knowledge contract | `docs/knowledge-contract.md` |
| Work in progress | `docs/handoffs/` (active: H3, H4, H4.1, H5, H6, H7; closed: H1, H2, reduced to summaries) |

## For contributors (people or agents)

- **Commits:** a one-line conventional subject that names the capability, with no body and no attribution trailer;
  signed.
- **New code meets the shape targets from the start**; H5 brings the old code up to them.
- **Corpus repos belong to third parties:** never run their code. Read and measure through the indexer's container.
- **Long commands** (corpus, refresh) run in the background. Don't edit the indexer or the expected lists during a
  corpus run, because the code is mounted in the containers.
- **Everything in the repo is in English:** code, commits, PRs and docs (H4-D1). One doc is still in Portuguese
  until it is rewritten: the indexer guide (`docs/indexer-evolution.md`, H4 phase 0b).
