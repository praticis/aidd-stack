<!--
The template of a pull request to the indexer. The rules are in docs/indexer/method.md, "The pull request body".

- Copy this file to a scratch file, fill it, delete every comment, and open the PR with
  `gh pr create --title "type(scope): ..." --body-file FILE [--label graph-change]`. Do not use `--template` or `--fill`.
- The title is about 60 characters, conventional, and names the capability. No attribution line in the title, the body or a
  commit: CI refuses it (indexer/scripts/checks/pr_text.py).
- The comment at the end of a heading lists the kinds of PR that carry the block. Delete a block whose list leaves out the
  PR's kind; do not write "N/A". The top lines, "What and why", "Contracts, boundaries and proof" and "Left out on purpose"
  stay in every PR.
- Numbers go in the body, one line each: a comment on GitHub does not reach the merge commit.
- The body is final at the merge, and is the long record of the change. Live validation is written in the next PR's docs.
-->
Kind: refactor | fix | feat | chore(scripts) | docs
Records: <decision ids (H5-Dnn); debts opened or closed (TD-nnn, each with its strict xfail test); the date the plan was approved>
Labels: none | graph-change | holdout-measurement
Gates: <one line: corpus 0 differ · hold-out 0 · micro 12/12 · scorecard at its floors · tests N · shape 0 new; for docs, the check that ran>
Author decides: <what only the author can answer, or could not be tested; or "nothing">

## What and why
<What changed, then why: the commit says the capability, this says the reason.>

## Contracts, boundaries and proof
- **Contract:** <what the change reads or couples to; what already answers the question>
- **Boundary:** <where each piece of knowledge lives>
- **Reference:** <the independent reference that proves it, and over which real data>
- **Unknown:** <what stays `Unknown`, and why>
- **Alternative one level up:** <taken or not, and why> <!-- refactor fix feat -->
- **Differs from the plan:** <delete the line if it does not>

## Measures <!-- refactor fix feat chore(scripts) -->
<The criterion, declared before the measure, and what it said. A refactor: the corpus, the hold-out and the micro set `0 repo(s) differ`, and the shape. A fix or feat: the per-site judgment by cause (the counts, the causes by count, "no site reached X"), the firing probe, mutants killed N of M, the cost in pairs. A chore(scripts): what ran, with a mock or on real input.>

## Independent review <!-- refactor fix feat -->
<The tier, then one line per objection: fixed, a debt, or answered, and how.>

## Graph change <!-- fix feat, and any PR with the label graph-change -->
<Expected against found. The consumers it touches: an MCP tool's output, the schema, a skill, a golden question. Rollback: revert, then the refresh re-indexes.>

## Debts <!-- when one is opened or closed -->
<TD-nnn, with the path of its strict xfail test.>

## Left out on purpose
<What this PR does not do, and why.>

Live validation: <after the merge (the counts go in the next PR's history line) | not needed: why>
