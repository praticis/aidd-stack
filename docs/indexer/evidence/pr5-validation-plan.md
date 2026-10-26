# PR #5's validation plan (2026-10-19)

> **Provenance.** This plan is reconstructed, not original. It was written in Portuguese in a session scratchpad
> (`validation-plan.md`) at 2026-10-19 01:56 UTC, before PR #5 (`feature/f114-close`) merged. The scratchpad was lost
> in a reboot. The text was rebuilt from that session's transcript with
> [`recover.py`](../../../indexer/scripts/recovery/recover.py), then translated to English for the repository (H4-D1).
> The structure, the items and the criteria are the plan's; the wording is the translation's. It names no tenant: the
> live install is described by its shape only.
>
> It is kept because it is where the method's two-phase validation started: an offline phase against the corpus, then
> the live install. Its phase A became the CI gates, and its phase B the live check (V21–V25 in
> [the inventory](../validation-inventory.md)).

Comparison base: `main` = `82f6025` (the merge of #4), live build `0.2.14+8553d8007527`. Branch under test: `aee80b9`.

## What the branch changed (the scope of the risk)

Changed:

- the HTTP extractor (`core/http_*`, `languages/*/http.py` and the new modules);
- the `HttpEndpoint`'s id and `app` field (`ids.py`, `model.py`, `integrations.py`);
- the cleanup of old nodes (`graph.py`);
- two MCP queries (`http_map`, `who_consumes`);
- `SCHEMA.md`, and `INDEXER_VERSION`, which went to 0.2.15.

Unchanged: the resolver, the symbols, `CALLS`, `IMPORTS`, the conventions and the linker.

So any difference outside HTTP is a defect.

## Phase A — offline (the install is not touched)

- **A1. The tests.**
  - Run the suite at the head (expected: 177 passed, 2 skipped).
  - Collect the test ids on `main` and on the head: no test of `main` may be missing.
  - Justify the 2 lines of `test_fixtures.py` and the line removed from `route-patterns-cs/expected.json`.
- **A2. The expected lists.** Classify every line removed from 17 lists (−347 lines):
  - a category cleared because the item is now extracted: fine;
  - an expected item removed: only under H2-D15;
  - a `checked` verdict that went from right to wrong: it blocks.
- **A3. The head reproduces the baselines.**
  - `corpus.sh` at `aee80b9` against `baseline-27`: "0 repo(s) differ".
  - The hold-out against `holdout-26`: identical.
- **A4. `main` against the head on the corpus and the hold-out.**
  - The setup: `82f6025`'s `aidd_indexer` (a `git archive` into the scratchpad), with the head's scripts and lists.
  - Both are scored by today's lists. The criteria:
    - per repo and kind, the list's precision and recall on the head ≥ `main`'s;
    - no expected pair that `main` finds is missing on the head;
    - no `checked` item judged right on `main` is gone on the head.
  - An exception is explained item by item.
- **A5. No win reverted.**
  - For each baseline, from `2026-10-15-v2-baseline` to `-27`, list the expected pairs it found and `-27` does not.
  - Expected: none, or each one explained.
- **A6. Lint** (a report, not blocking):
  - ruff `F`: no new error;
  - `C901` > 9 in the new functions.

## Phase B — the live install (needs authorization)

The starting state: 3 tenants (.NET, Go, TS), 10 snapshots, the refresher every 15 minutes.

- **B1. The "before" picture** (read-only).
  - Per tenant × repo × ref, count: `Symbol`, `File`, `CALLS`, `IMPORTS`, `EXPOSES`, `HANDLED_BY`, `HttpCall`,
    `CONSUMES`, `CALLED_FROM`, `DEPENDS_ON`, `Violation`.
  - List the endpoints (method, `path_key`, handler) and the links (call → endpoint, confidence).
  - Record the golden questions' answers.
- **B2. A dry-run of `main` and of the head, per snapshot.**
  - A `git archive` of each snapshot's sha into the scratchpad, and `aidd index --dry-run` with each code. The
    criteria:
    - outside HTTP, everything identical;
    - in HTTP, each difference judged at the source;
    - `main`'s dry-run matches the "before" picture.
- **B3. Reinstall from the branch.**
  - `install.sh` in upgrade mode.
  - `install-check.sh` all OK, with the selftest and the real `atlas_status`.
- **B4. The refresh.**
  - The 10 snapshots come out `outdated` and are re-indexed once each.
  - A second refresh re-indexes nothing.
  - The logs hold no error and no "cross-file composition skipped".
- **B5. The "after" picture against the "before" one.**
  - Outside HTTP, identical.
  - HTTP changes exactly as B2's diff said.
  - No `HttpEndpoint` is left without `app`, and no endpoint is left orphaned.
  - Every (repo, ref) that exposed routes still exposes them. Watch the TS repo with 2 refs: the cleanup deletes nodes
    shared between refs.
  - `CONSUMES` and `CALLED_FROM`: no link lost, and each new link explained.
- **B6. The MCP on the real graph.**
  - The 11 tools answer.
  - `http_map` and `who_consumes` carry `app`.
  - `cypher_readonly` refuses a write.
  - `atlas_status` shows 0.2.15, with nothing `outdated`.
- **B7. The golden questions.**
  - Q1–Q5, and Q1, Q2, Q4a and Q4b of the .NET pair, with the same answers as the fourth round.
  - Recorded as the fifth round.
- **B8. The scheduled refresher.** After 2 cycles: `last_rc` 0, `stale` false, `changed` 0.

**Rollback:**

- reinstall `82f6025` and run a refresh;
- the graph is derived from the sources: the fingerprint changes and everything is re-indexed;
- `main`'s cleanup deletes the ids with `/app/`.

## Phase C — recording and merge

- PR #5's test plan updated, with no tenant names.
- The fifth round in `golden-questions.md`.
- A defect found: a separate commit with a fixture, and the affected phases run again.
- Then the merge.

**What blocks the merge:**

- a difference outside HTTP without an explanation;
- an expected pair or a `checked` item lost;
- a link lost in the graph;
- a FAIL in `install-check`.

## What came of it

From `docs/golden-questions.md` (the fifth round) and `docs/history.md`: every phase passed after one defect. B5 found
it: two TS wrapper defects that the corpus did not have. It was fixed as F1.14 increment 12 (`dfbc8d7`), with a
fixture, and the phases ran again. The A2, A4 and A5 checks are persisted as
[`a2_gabaritos.py`](../../../indexer/scripts/checks/a2_gabaritos.py),
[`a4_compare.py`](../../../indexer/scripts/checks/a4_compare.py) and
[`a5_chain.py`](../../../indexer/scripts/checks/a5_chain.py); B1 and B2 as
[`foto.sh`](../../../indexer/scripts/live/foto.sh) and
[`dryrun-live.sh`](../../../indexer/scripts/live/dryrun-live.sh), in their later versions. The
[resource catalog](../resource-catalog.md) has the provenance of each.
