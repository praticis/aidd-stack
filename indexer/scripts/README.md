# The indexer's checks

Every check the CI runs on a pull request (`.github/workflows/indexer.yml`) is a script here, and runs the same way on
a laptop. The shell scripts run in the indexer's Docker image with this tree mounted read-only. The corpus clones and
runs live in `$AIDD_CORPUS_HOME` (default `~/.cache/aidd-corpus`), outside the repository.

The image is `aidd-indexer:local`. CI builds it from `indexer/` alone (`docker build -t aidd-indexer:local indexer`),
with no `.env`. The stack's `docker compose build` builds the same image, but needs an installed `.env`, since the
compose file requires its variables. On a machine that runs the stack, rebuilding the tag also changes the image the
live install uses.

| Script | What it checks | Locally | CI job |
|---|---|---|---|
| `test.sh` | the tests, in the test image: the indexer image, pytest, and Node with a pinned `typescript`, which TS's type cases and scope index are checked against (rebuilt when its recipe changes) | `indexer/scripts/test.sh [pytest args]` | `tests` |
| `corpus.sh`, with `http_corpus.py`, `corpus_metrics.py` and `corpus_totals.py` | the HTTP extractor on the public corpus and the hold-out: the diff against a baseline, and precision and recall against the expected lists, per repo and summed by language | `corpus.sh --baseline <run>`; `corpus.sh --holdout --baseline <run>` | `corpus` |
| `micro.sh`, with `micro.py` | the micro graph (files, symbols, `CALLS`, `IMPORTS`, `hierarchy`, violations): full dry-runs of 12 repos by `main` and by the tree, compared record by record; `--ignore calls.virtual` leaves a field out, to show what else a change that adds it changed | `indexer/scripts/micro.sh` | `micro` |
| `gates.sh`, with `gates.py` | the method's gates over two corpus runs: the precision ratchet, no win lost, the hold-out untouched, a refactor that changes nothing, and the micro graph's verdict. It also decides whether the pull request is a refactor, from its branch and its commits | see below | `gates` |
| `shape.py` | the shape ratchet: no function above complexity 9 and no module above 300 lines that is new, or worse than at the base | `python indexer/scripts/shape.py --against main` (needs `ruff`) | `shape`, required through `gates` |
| `debts.py` | the register of technical debts: each case it names is a case of the debts' tests and the reverse, and the ROADMAP's lists of the open debts by due agree with it | `python3 -I indexer/scripts/debts.py` | `debts`, on every pull request |
| `mcp-it.sh` | every atlas tool against a throwaway Neo4j, and the graph the writer leaves read back against a dry-run of each snapshot, by each record's key in the graph | `indexer/scripts/mcp-it.sh` (after `test.sh`, which builds the test image) | `tests` |

## The gates, as CI runs them

Run the corpus and the hold-out with `--label` on both sides (the base at `main`, the branch in the tree), then:

```sh
indexer/scripts/micro.sh; micro=$?
git log --format=%s origin/main..HEAD \
  | indexer/scripts/gates.sh --base runs/<base> --head runs/<branch> \
      --holdout-base runs/<base>-holdout --holdout-head runs/<branch>-holdout \
      --branch="$(git branch --show-current)" --commits - --micro-rc "$micro"
```

A branch named `refactor/…` or `refact/…`, or one commit whose subject starts with `refactor:` or `refact:` (with or
without a scope), makes the whole pull request a refactor, where any difference fails. The labels `holdout-measurement`
and `graph-change` (`--label`) let a judged change through.

## Local tools, which CI does not run

Each answers a question of the method (`docs/indexer/`). Their inputs and outputs stay outside the repository
(`$AIDD_CORPUS_HOME`, `.local/`).

| Folder | Tools | Question | Runs |
|---|---|---|---|
| `protocol/` | `protocol.sh`, `micro-fresh.sh`, `time-alone.sh`, `cost-pairs.sh` with `cost_pairs.py`, `shape.sh` | the regression protocol on a commit's worktree; the micro graph through fresh paths; time alone; main against the branch in alternating pairs, the change in time and in peak memory per repo; the shape ratchet in the image | Docker |
| | `resume-test.sh` | whether a new session can resume from a pushed commit: a headless, read-only `claude` run in a fresh clone, with its report and its tool calls in files | `claude`, network |
| `judgment/` | `chain_diff.py`, `show.py`, `site_edges.py`, `ts_vs_checker.py`, `scorecard.py` | which `CALLS` edges changed between two dry-runs, by kind; the sampled sites' source lines; one site's edges; for TS, the typed edges a change adds and the by-name ones it drops against what TypeScript's checker declares; a whole tree's numbers (the share of typed `CALLS`, and for TS the precision and the recall against the checker) against their floors | `python3 -I` |
| | `attribution.py` | which changed `CALLS` edges a difference in what two trees answer at the site explains, by case and kind, and which nothing explains; each repo's `CALLS` by strategy on both sides, and the share found among several homonyms, of the edges and of the sites; the receivers each side leaves untyped, by the reason the language gives | `python3 -I` |
| | `attribution.sh` with `answers.py` | what each of two trees' extraction types the receivers of the method calls of a language, or of several read together (`typescript,tsx,javascript`), as, or why it gives one no type, and what its resolver makes of each receiver, then `attribution.py` over the two dry-runs | Docker, two trees |
| | `hierarchy.py`, `dispatching.py` | what a tree's types' bases give each repo: the `EXTENDS` and `IMPLEMENTS` edges, whether their closure is the ancestry the resolver walks, the names two types of one file share, the calls that do not dispatch by what they reach, Python's `super()` calls its receiver does not decide by how many edges each has or why none, the `OVERRIDES` edges against the methods of one name through the types' edges, each pair left out by why, and the callers they add to `who_calls`, the overrides a dispatching call's `receivers` keep against those the language runs on them, Go's interface calls with no edge, and the seconds | the image, as root, `PYTHONPATH=/src` |
| | `csharp_extensions.py` | the edges to the repo's C# extension methods that went away or came: `sites`, `back`, `classes`, `this-kind`, `blocks` | `python3 -I` |
| `checks/` | `expected_lists_diff.py`, `expected_lists_chain.py` | what changed between two sets of expected lists; no win reverted across the saved runs | the image, `PYTHONPATH=/src:/src/scripts` |
| `checks/` | `pr_text.py`, with `pr_text_deny.txt` | whether a pull request's title, body or commit messages hold a line the list refuses (an attribution footer or trailer): a rule is a line of the list, `id :: regex :: reason` | the `debts` job of every PR; locally `python3 -I`, with the text in files |
| `checks/` | `docs_size.py`, with `docs_ceilings.txt` | the files of `docs/` that grow, against a ceiling in bytes each: one over it, or gone, is refused; to raise a ceiling is a line of the list | the `debts` job of every PR; locally `python3 -I` |
| `checks/` | `mutants.sh`, with `mutants.py` | each rule of a change broken once on a copy of the tree, and whether a test fails: `DIES` or `SURVIVES` per mutant, status 1 if one survives, 2 if it cannot judge (a wrong file, a red baseline, tests that did not run) | the host, one `test.sh` per mutant; takes the heavy-job lock |
| | `dump.py` | every file's type facts (`csharp`, `go`, `python`, `typescript`, `tsx`, `javascript`), to compare two codes | the image, as root |
| | `python_scopes.py` | whether Python's scope index classifies every name of every Python file as CPython's `symtable` does | the image, `PYTHONPATH=/src`, the repos at `/corpus` |
| | `ts_scopes.py`, `ts_scopes.js` | whether TS's scope index binds every name and `this` of every TS and JS file as TypeScript's binder does | the test image, `PYTHONPATH=/src`, the repos at `/corpus` |
| | `ts_heritage.py`, `ts_heritage.js` | whether TS's type index resolves every heritage clause of every TS and JS file to the declaration TypeScript's checker does, each file with its config's `paths`, the link a package manager makes for a workspace package or a `file:` dependency and a referenced project's output read as its source, a value a class extends by the checker's base type, and a class a module's statement declares by an expression, named as the index names it | the test image, `PYTHONPATH=/src`, the repos at `/corpus` |
| | `ts_modules.py`, `ts_modules.js`, `ts_link.js` | whether TS's module resolution gives every import of every TS and JS file the file TypeScript's does, with the file's config, the link a package manager makes for a workspace package or a `file:` dependency, and, where the config references a project, its output read as its source | the test image, `PYTHONPATH=/src`, the repos at `/corpus` |
| | `ts_configs.js`, `ts_checker.js` | the config TypeScript reads a file with, and a program that reads a referenced project's output as its source, for every TS oracle; the declarations the checker resolves each method call to, with the link a package manager makes for a workspace package or a `file:` dependency | the test image |
| | `ts_runs.js` | what JS runs on an instance of each class of a test's own case, which it compiles and runs: for the tests only | the test image |
| | `reference.sh`, `reference_floors.txt` | the graph of a tree against its references and the floors that judge it: the checker's rows for the TS repos with a floor (kept by clone, checker and image recipe), then `judgment/scorecard.py` over the micro dry-runs; the micro job runs it on every pull request, and `gates.py` fails a number under its floor, or a floor lowered without `graph-change` | Docker, the test image; `--run DIR` is a tree's `micro/<label>` |
| | `mutate.sh` | the writer's mutation test, through `mcp-it.sh` | Docker |
| `lists/` | `expected_lists.py` | edits the expected lists (`new`, `add`, `cat`, `set`, `judge`), draws a list's first sample (`sample`) and keeps its checked samples true to a corpus run (`sync`, `resample`, `found`, `pending`); a list is written back in the order it was read. `--holdout` works on the hold-out's lists: `new` needs a pin, and a measured one is not opened | `python3 -I`; it writes the repository's lists |
| `lib/` | `heavy-lock.sh` | one heavy Docker job at a time on the machine: the scripts that start one (`corpus.sh`, `micro.sh`, `test.sh` unless an argument names a file, a test or a folder under `tests/`, `mcp-it.sh`, `protocol/protocol.sh`, `time-alone.sh` and `micro-fresh.sh`, `judgment/attribution.sh`, `live/validate.sh before` and `after`, `dryrun-live.sh`) take `~/.cache/aidd-corpus/heavy.lock`; a second one ends with 75 and names the holder, or waits with `AIDD_HEAVY_WAIT` | sourced by those scripts |
| `probes/` | `probe.py`, `tree.py` | the `CALLS` edges of a small repo; a snippet's tree | the image, as root |
| `live/` | `validate.sh` (`before`, `after`, `rotate`) with `validate_summary.py`; what it chains: `pre-merge.sh`, `graph-picture.sh`, `golden.py`, `dryrun-live.sh`, `dry_sections.py`, `graph_vs_dry.py`, `json_paths_diff.py`; `round.py` drafts the golden round and its history line from the in-flight folder | the live install before and after a merge, read-only; the numbers as counts | the install, with the author's authorization |
| `review/` | `independent-review.js`, `research-round.js` | whether a plan or a diff survives agents that did not write it and are told to refute it (objections by severity, the blocking ones re-checked by a second reader); for a design with real alternatives, one read-only researcher per open question, a synthesis that decides and a challenge of it | the Workflow tool: `Workflow({scriptPath, args})`; read-only, advisory, never a gate |

The image's grammar cache belongs to root, so tools that parse run without `--user`. A tool's arguments are in its
docstring.
