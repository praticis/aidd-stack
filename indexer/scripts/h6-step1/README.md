# H6 step 1: the measurement scripts

The prototype in `aidd_indexer/core/pipeline.py` replaces `extract_tree` on this branch (`AIDD_PIPELINE=0` runs the
old one). These scripts measured it; the results are in `docs/corpus-report.md`, "H6 step 1". Outputs go to
`$AIDD_H6_OUT` (default `~/.cache/aidd-corpus/h6/step1`).

| Script | What it does |
|---|---|
| `fetch.sh NAME SLUG SHA` | a shallow window (40 commits) of a public repo's history, for the replay |
| `replay.py` | each commit of the window indexed cold, with each file's key, summary and scan digests, and what its scan read |
| `evaluate.py DIR...` | per cache policy: the scans re-run per push and the keys that missed a change |
| `bench.sh` | one full dry-run in its own container: wall time and the cgroup's peak memory |
| `run_bench.sh ROUNDS REPO...` | today against the prototype with 1, 2 and 4 workers, cold and warm, each compared with today's |
| `push_bench.sh REPO K...` | the cache on real pushes: cold, filled on the commit before, warm, warm again; warm compared with cold |
| `same.py A B` | two dry-runs compared record by record |
| `chain.sh`, `chain2.sh` | the order the runs were made in |
