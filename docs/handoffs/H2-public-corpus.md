# Handoff H2 — widen the public corpus and measure the extractor's precision/recall (closed)

The briefing asked for four things:

- take the HTTP extractor's calibration corpus (15 repos) to ~40 repos, with real frameworks and apps;
- one expected list per repo (a committed spec or reading the code);
- precision and recall per language, with the errors by category;
- fix what was a general rule.

The original text is in `git show 1d73bb0:docs/handoffs/H2-public-corpus.md` (in Portuguese). The plan and the
decisions are in `H2-roadmap.md` and `docs/decisions.md`.

**Closed (2026-10-18).** The briefing's deliverables were met, and F1.14 took to the extractor what H2b and the
hold-out left.

- **Corpus:** 55 public repos, 54 of them with an expected list (a committed spec checked in the code, or a list read
  from the code), pinned by SHA.
- **Hold-out:** 3 repos kept out of tuning. The new hold-out comes after H5 (H2-D21).
- **Instrument:** `http_corpus.py`, `corpus_metrics.py` and `corpus.sh`.
- **Final numbers** (P / R against the expected lists):

  | | C# | Go | Python (FastAPI/Flask) | TS/JS |
  |---|---|---|---|---|
  | Routes | 100 / 99.3 % | 98.9 / 93.3 % | 99.3 / 98.6 % | 98.1 / 91.7 % |
  | Calls | 100 / 99.0 % | 100 / 93.6 % | — | 98.4 / 99.0 % |

- **Where everything is:**
  - the report and where each gap goes: `docs/corpus-report.md` ("Closing F1.14 and H2");
  - the summary: `H2-roadmap.md`; the decisions: `docs/decisions.md`; the milestones: `docs/history.md`;
  - the rules: `docs/indexer-evolution.md`.
