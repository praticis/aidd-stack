# H2 — public corpus and HTTP extractor precision/recall (closed)

> A **closed** handoff (F0.4.3a, F0.4.3b and F1.14).
>
> - The plan, the phases, the daily log and each step's tables were removed in the recycling of 2026-10-19 (H4 phase
>   0a) and stay in git: `git show 1d73bb0:docs/handoffs/H2-roadmap.md` (in Portuguese).
> - The decisions H2-D1…D21 are in `docs/decisions.md`; the milestones, in `docs/history.md`; the numbers and the
>   method, in `docs/corpus-report.md`.

## Summary

- **H2 is closed.** F0.4.3a, F0.4.3b and F1.14, which took to the extractor what H2b and the hold-out left, are all
  `[x]` in the ROADMAP.
  - **Instrument:**
    - `http_corpus.py` (`--baseline`, `--expected`, `--sample`, `--holdout`, `--reuse`) and `corpus_metrics.py`;
    - `corpus.sh`, which runs the corpus in parallel, one container per repo;
    - the expected lists in `indexer/tests/corpus_expected/`.
  - **Corpus:** from 15 repos (v1) to 55, 54 of them with an expected list; the hold-out keeps 3 repos (Kavita,
    go-boilerplate, sftpgo).
  - **Final numbers** (P / R against the expected lists, baseline `2026-10-18-v2-baseline-28`):

    | | C# | Go | Python | TS/JS |
    |---|---|---|---|---|
    | Routes | 100 / 99.3 % | 98.9 / 93.3 % (97.7 % without memos' Connect RPCs) | 99.3 / 98.6 % outside Django | 98.1 / 91.7 % |
    | Calls | 100 / 99.0 % | 100 / 93.6 % | — | 98.4 / 99.0 % |

  - **The hold-out of 2026-10-17 showed overfitting.** On the 13 of its repos that F1.14 worked on, route recall
    went:
    - C#: from 32.2 to 99.8 %;
    - Go: from 0 to 79.3 % (95.7 % without Connect);
    - Python: from 83.8 to 100 %;
    - TS/JS: from 74.1 to 99.2 %.

    TS/JS call recall went from 76.5 to 100 %.
  - **What is left has a destination:**
    - Django: out, until a portfolio asks for it;
    - prefixes known only at run time: a limitation;
    - Connect: F2.1;
    - test app folders: F1.1;
    - a type not declared in sight: `needs-resolver`, for F1.2.

    The table is in `docs/corpus-report.md`, "Closing F1.14 and H2".
  - **The new hold-out comes after H5 (H2-D21).**
  - **Next:**
    1. H4 phase 0a;
    2. H5;
    3. the new hold-out and its handoff;
    4. P2;
    5. SCIP.

## How to measure today

- The corpus: `indexer/scripts/corpus.sh --baseline 2026-10-18-v2-baseline-28`. The hold-out: `--holdout --baseline
  2026-10-18-v2-holdout-26`.
- The tests: `indexer/scripts/test.sh`.
- The cycle of a change to the extractor is in the guide, `docs/indexer-evolution.md` §5.
