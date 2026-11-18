# Handoffs

A handoff is the brief of a piece of work that spans more than one chat: a plan, a design, a request, or the result a
request brought back. Each one has a row here, with its kind, its state and what it waits for. The state in full is the
"State" line at the top of the file; a pull request that changes that line changes the row too.

- **A request or a result** is written (the request exists), answered (a result is in), judged (the main chat recorded,
  finding by finding, what it accepted, changed or refused) or closed (the decisions that depended on it were taken).
- **A plan or a design** is not started, in progress or closed.

| Handoff | Files | Kind | State | What it waits for |
|---|---|---|---|---|
| H1 | `H1-reference-apps.md` | plan | closed | nothing. The Go, TS and Python conventions it left open are not planned here: a convention's content may be written outside this repository and handed over by path (H10, section 1.1) |
| H2 | `H2-public-corpus.md`, `H2-roadmap.md` | request and result | closed | nothing. The new hold-out it left (H2-D21) comes after H5 |
| H3 | `H3-ai-dev-efficiency.md` | request | written | nothing: it never ran, and it stays as a record. It measured the Atlas together with the `knowledge` service, which leaves (H10, section 1.1) |
| H4 | `H4-public-docs.md` | plan | in progress | a new decision: it plans for the indexer to leave this repository, and the premise reverses that (H10, section 1). Step 0a is done |
| H4.1 | `H4.1-contributor-path.md` | plan | in progress | `CONTRIBUTING.md`, the templates, `CODEOWNERS` and the path check |
| H5 | `H5-indexer-refactor.md` | plan | in progress | the end of H10's reorganization; then its "Next" |
| H6 | `H6-extraction-pipeline.md` | design and plan | in progress | H5; then plugging it in |
| H7 | `H7-regression-gates.md` | plan | in progress | slices 1b and 2 to 6, and its decisions D2 and D4 |
| H8 | `H8-independent-review.md` | design | in progress | a step in CI and a record per pull request. Its hooks into the process skills leave with them (H10, section 1.1) |
| H10 | `H10-roadmap-reorganization.md` | request | judged | its ten pull requests. Until the last one merges, no other pull request enters `main` |
| H11 | `H11-release-and-distribution.md` | request | judged | the end of H10's reorganization, which writes its items into the roadmap; then its first step |
