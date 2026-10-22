# The indexer's checks

Every check the CI runs on a pull request (`.github/workflows/indexer.yml`) is a script here, and runs the same way on
a laptop. The shell scripts run in the indexer's Docker image with this tree mounted read-only. The corpus clones and
runs live in `$AIDD_CORPUS_HOME` (default `~/.cache/aidd-corpus`), outside the repository.

| Script | What it checks | Locally | CI job |
|---|---|---|---|
| `test.sh` | the tests, in the test image | `indexer/scripts/test.sh [pytest args]` | `tests` |
| `corpus.sh`, with `http_corpus.py` and `corpus_metrics.py` | the HTTP extractor on the public corpus and the hold-out: the diff against a baseline, and precision and recall against the expected lists | `corpus.sh --baseline <run>`; `corpus.sh --holdout --baseline <run>` | `corpus` |
| `micro.sh`, with `micro.py` | the micro graph (files, symbols, `CALLS`, `IMPORTS`, violations): full dry-runs of 12 repos by `main` and by the tree, compared record by record | `indexer/scripts/micro.sh` | `micro` |
| `gates.sh`, with `gates.py` | the method's gates over two corpus runs: the precision ratchet, no win lost, the hold-out untouched, a refactor that changes nothing, and the micro graph's verdict. It also decides whether the pull request is a refactor, from its branch and its commits | see below | `gates` |
| `shape.py` | the shape ratchet: no function above complexity 9 and no module above 300 lines that is new, or worse than at the base | `python indexer/scripts/shape.py --against main` (needs `ruff`) | `shape`, required through `gates` |
| `mcp-it.sh` | every atlas tool against a throwaway Neo4j, and the graph the writer leaves read back against a dry-run of each snapshot, by the writer's merge keys | `indexer/scripts/mcp-it.sh` (after `test.sh`, which builds the test image) | `tests` |

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
