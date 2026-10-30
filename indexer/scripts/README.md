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
| `test.sh` | the tests, in the test image | `indexer/scripts/test.sh [pytest args]` | `tests` |
| `corpus.sh`, with `http_corpus.py` and `corpus_metrics.py` | the HTTP extractor on the public corpus and the hold-out: the diff against a baseline, and precision and recall against the expected lists | `corpus.sh --baseline <run>`; `corpus.sh --holdout --baseline <run>` | `corpus` |
| `micro.sh`, with `micro.py` | the micro graph (files, symbols, `CALLS`, `IMPORTS`, violations): full dry-runs of 12 repos by `main` and by the tree, compared record by record | `indexer/scripts/micro.sh` | `micro` |
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
| `protocol/` | `protocol.sh`, `micro-fresh.sh`, `time-alone.sh`, `shape.sh` | the regression protocol on a commit's worktree; the micro graph through fresh paths; time alone; the shape ratchet in the image | Docker |
| | `resume-test.sh` | whether a new session can resume from a pushed commit: a headless, read-only `claude` run in a fresh clone, with its report and its tool calls in files | `claude`, network |
| `judgment/` | `chain_diff.py`, `show.py`, `site_edges.py` | which `CALLS` edges changed between two dry-runs, by kind; the sampled sites' source lines; one site's edges | `python3 -I` |
| | `attribution.py` | which changed `CALLS` edges a difference in what two trees answer at the site explains, by case and kind, and which nothing explains; each repo's `CALLS` by strategy on both sides, and the share found among several homonyms, of the edges and of the sites; the receivers each side leaves untyped, by the reason the language gives | `python3 -I` |
| | `attribution.sh` with `answers.py` | what each of two trees' extraction types the receivers of a language's method calls as, or why it gives one no type, then `attribution.py` over the two dry-runs | Docker, two trees |
| | `csharp_extensions.py` | the edges to the repo's C# extension methods that went away or came: `sites`, `back`, `classes`, `this-kind`, `blocks` | `python3 -I` |
| `checks/` | `expected_lists_diff.py`, `expected_lists_chain.py` | what changed between two sets of expected lists; no win reverted across the saved runs | the image, `PYTHONPATH=/src:/src/scripts` |
| | `dump.py` | every file's type facts (`csharp`, `go`, `python`), to compare two codes | the image, as root |
| | `python_scopes.py` | whether Python's scope index classifies every name of every Python file as CPython's `symtable` does | the image, `PYTHONPATH=/src`, the repos at `/corpus` |
| | `mutate.sh` | the writer's mutation test, through `mcp-it.sh` | Docker |
| `lists/` | `expected_lists.py` | edits the expected lists (`new`, `add`, `cat`, `set`, `judge`), draws a list's first sample (`sample`) and keeps its checked samples true to a corpus run (`sync`, `resample`, `found`, `pending`); a list is written back in the order it was read. `--holdout` works on the hold-out's lists: `new` needs a pin, and a measured one is not opened | `python3 -I`; it writes the repository's lists |
| `probes/` | `probe.py`, `tree.py` | the `CALLS` edges of a small repo; a snippet's tree | the image, as root |
| `live/` | `validate.sh` (`before`, `after`, `rotate`) with `validate_summary.py`; what it chains: `pre-merge.sh`, `graph-picture.sh`, `golden.py`, `dryrun-live.sh`, `dry_sections.py`, `graph_vs_dry.py`, `json_paths_diff.py` | the live install before and after a merge, read-only; the numbers as counts | the install, with the author's authorization |

The image's grammar cache belongs to root, so tools that parse run without `--user`. A tool's arguments are in its
docstring.
