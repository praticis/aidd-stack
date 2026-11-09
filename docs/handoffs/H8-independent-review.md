# Handoff H8 — The independent reviewer: a read-only adversary for plans and PRs

> Paste this file (or ask for `docs/handoffs/H8-independent-review.md` to be read) at the start of a new chat. Before
> anything else, the chat should read:
> - `AGENTS.md`, the entry point;
> - `docs/design.md`: the contracts, boundaries and proof a plan declares, which is what this reviewer attacks;
> - `docs/handoffs/H7-regression-gates.md`: the deterministic gates this reviewer complements and never replaces;
> - `docs/handoffs/H5-indexer-refactor.md`: the changes of behavior (H5-D48 to H5-D51) whose plans were the first
>   material it reviewed.
>
> **State (2026-11-08):** designed and used three times: on the plan of H5-D50 (TS call receivers), on its diff, and
> on the plan and the diff of H5-D51 (the full Tier 1). It found a gap in D50's acceptance criterion that the author
> and one agent had both missed, and in D51 a regression the first fix had opened. The reusable script exists
> (`indexer/scripts/review/independent-review.js`, called by path from any worktree, with its orchestration tested with
> simulated agents). Nothing runs in CI yet, and the reviewer is not yet a step of the process skills.

## Context in one paragraph

The method already has deterministic gates (H7) and a rule that a change of behavior declares its acceptance
criterion before it is measured (`docs/design.md`). What those cannot catch is a criterion that cannot fail, a
population the criterion forgot, a number that came from a defective tool, or a recommendation that ignored a risk
written in another document. The author of a change is the worst reader of it. H8 adds a reader that did not write
the change, starts from a clean context, is told to refute, may check the data but cannot touch the repo, and answers
in a form that can be verified. It advises. It never gates (H7's constraint: an LLM never decides a CI gate).

## The pattern

Three roles, each in its own context. Only the third is always run.

| Role | What it does | Always? |
|---|---|---|
| **Researchers** | One agent per open question, each measuring on copies outside the repo and returning a report with evidence, `how_verified` and a mandatory `not_verified` list | no, only for a real design choice (Tier 2) |
| **Synthesizer** | Reads the reports and the plan, decides keep, amend or change, says which report it believes where two disagree, and refuses a recommendation whose evidence says "not verified" | no, with the researchers |
| **Challenger, or a panel of lenses** | Tries to refute the synthesis (a plan) or the diff, with read-only access to the raw data | yes |

**What made the review useful in its first use:**

1. **It received the raw reports as well as the conclusion.** The blocking objection came from a log the synthesis had
   summarized away. A reviewer given only the conclusion can only argue with its wording.
2. **Its task was to refute, with a named list of failure modes:** a measurement that does not support its claim, a
   number without its source, a risk another document raised and the plan ignored, an amendment that breaks a repo
   rule, a hidden cost, a simple alternative dismissed, an unverified claim treated as fact, a criterion that cannot
   fail or was relaxed after seeing the data, a population the criterion does not cover.
3. **It could check, not change.** Read-only scripts (`python3 -I`) over the data and the code; no edit, no corpus
   code, no Docker. The objections therefore had to come from data that already existed.
4. **Its output was falsifiable:** each objection carries a severity, the place to look, the command that reproduces
   it, and the review ends with "what would change my mind".
5. **A blocking objection was verified at the source before anyone acted on it.** The orchestrator re-read the code
   and counted the lines in the log. A reviewer is a model and can be wrong too.

**For a diff the reviewer is given the code, not the author's conclusion** (the diff, the criterion declared before
measuring, the oracle), so the author's account does not anchor it. For a plan it must see the conclusion, since that
is the thing under attack.

### The lenses of a diff

One agent per lens, same inputs, different questions. Their objections are pooled and merged by place in plain code,
not by another agent.

| Lens | Asks |
|---|---|
| **correctness** | Does the change do what the criterion says on every path? Does each new test fail without the change? Does the oracle truly bound the behavior? Is there a proof that passes for the wrong reason? |
| **rules** | Does it keep the repo's rules: complexity ≤ 9, modules ≤ 300 lines, comments only the why, no private names, only the files the plan lists, one cause per commit, a refactor changes nothing, extraction stays deterministic, no secret enters the index? |
| **losses** | What does it lose, break or cost that the criterion does not measure? Hidden time or memory, inputs the corpus lacks, a regression a debt or a handoff warns about, a simpler alternative skipped, a claim in a commit or doc that the code does not support? |

### The second reader

Each `blocking` objection goes to one more agent that is told only the objection, where it is and the command, not how
the first reviewer reached it. It answers `confirmed` true or false with what it saw. This is cheap (one short agent per
blocking objection) and removes the failure of a confident, wrong reviewer.

## The first use: H5-D50

The plan's approved path was "type the receiver, keep the scope builder eager, accept +25 % time". Before
implementing, the author asked whether that was the best technical path. The round had six researchers, a synthesizer
and a challenger.

| | |
|---|---|
| Agents | 8 (six researchers, one synthesizer, one challenger) |
| Output tokens | 760k in all (the runtime counted 1.79 M subagent tokens, input included) |
| Tool calls | 605 |
| Wall clock | 68 min: the researchers 56 (bound by the slowest), the synthesizer 5, the challenger 7 |
| Review layer (synthesizer and challenger) | **12 % of the output tokens**: 41k and 49k, 55 tool calls of 605 |
| Research layer | 88 %: 151k, 133k, 122k, 104k, 80k, 79k per researcher |

**What the researchers settled:** an optimized eager builder halves the scope builder's cost (an end-to-end cost of
+22.9 % falls to +11.6 % on ghost, with output identical in bytes); three alternatives were rejected with their
reason, and the by-name fallback for a typed receiver was kept dropped. About 45 % of the research tokens (310k of 670k)
went into the three alternatives that were then rejected, which is a result, but a costly one.

**What the challenger found** (verdict "weakened": 1 blocking, 3 significant, 3 minor):

- *Blocking.* The criterion's gate on lost edges could not pass: in one repo, an end-to-end test package links a local
  package by `file:`, so it is not a workspace member, and the plan's rule did not reach it (357 call sites in the
  head's log). The orchestrator confirmed it in the code and in the log before acting.
- *Significant.* The synthesis explained a discrepancy between two numbers as "different units", which cannot be right
  (edges recovered are at least the sites lost); the fallback chosen for a class with an unreadable base had been
  measured imprecise in one repo and the synthesis did not say so; the order "refactor first" was argued from one
  side only.
- *Minor.* An overstated "tie" between two cost levers; a criterion relaxed after seeing the data, applied to one
  gate and not to its twin; an inference claim measured on one subtree.

Four of the seven changed the plan (version 2 of the plan, approved by the author the same day): the criterion's
population, the unreadable-base rule, the symmetry of the relaxation, and the order of the two PRs. The round also
exposed a defect in the checker script, which hid 11,145 sites as "no site"; it was fixed before the plan was measured.

### The second use: the diff of H5-D50, a Tier 1 panel

After the code was written, a panel of three lenses (correctness against the checker, the repo's rules, the losses)
read `main...HEAD` with the plan's criterion and the data, and a second reader re-checked each blocking objection.

| | |
|---|---|
| Agents | 5 (three lenses, two second readers) |
| Model and effort | Sonnet 5.5 at `xhigh` in each: both inherited, since the script passed no `effort` |
| Cost | 902k subagent tokens (input included, about half of the research round's 1.79 M), 291 tool calls, 39 min |
| Objections | 18 after the lenses' overlaps: 2 blocking (both confirmed by the second reader), 4 significant, 12 minor |

What it found, each reproduced at the source before the author acted: three typed edges the sample had explained away
(a receiver the flow narrows by `instanceof`, the result of an overloaded function, a module a JS file implements beside
its `.d.ts`), a class with another base beside a package with no entry and a star export of it that lost an edge, a
criterion measured over fewer edges than it said, a mutant called equivalent that no test pinned, a docstring false for
another language, and a name of a live install in two lines of the docs. Nothing it raised was wrong outright: one
objection (a commit subject with two causes) was declined with a reason, and the second reader corrected one count. The author then chose to fix the `instanceof` form in the same PR and to leave the `.d.ts` pair to its own
(it changes which edge a call gets, the declaration or the class that runs, which is a decision).

Lessons for the script: the lenses overlapped (two found the same mixed-base gap and the same A1 denominator), so a
shared list of what each lens must not repeat would save tokens; the second reader corrected a count and found the
objection stronger than stated, which is what it is for; and at `xhigh` each lens spent 120 to 180 tool calls, so the
lenses should run at `medium` and keep `xhigh` for the second reader, which the script now does by default (`effort`,
`verifyEffort`). That was a guess; the third use below is its measure.

### The third use: H5-D51, a challenger and two panels (Tier 1, as designed)

The first full pass of Tier 1 on one change: a challenger on the plan before the author approved it, then a panel of
three lenses on the diff, then a second panel on the diff after the first one's fixes. The lenses ran at `medium`; no
objection was blocking, so no second reader ran.

| | Plan challenger | Panel 1 | Panel 2 |
|---|---|---|---|
| Agents | 1 | 3 (correctness, rules, losses) | 3 |
| Cost | 72k tokens | 208k tokens | 228k tokens |
| Objections | 7: 4 significant, 3 minor | 10: 4 significant, 6 minor | 12: 3 significant, 9 minor |
| Verdicts | weakened | weakened, holds, weakened | weakened in all three |

The three together, 508k tokens, cost 56 % of the H5-D50 panel alone (902k at `xhigh`, 5 agents) and found as many
significant objections per round, so `medium` for the lenses kept the yield; `xhigh` stays for the second reader.

What each round changed, each checked at the source before the author acted:

- **The challenger, on the plan:** the prototype that gave `0 repo(s) differ` was not the code the plan said would ship
  (the plan's line limits forced another structure), the hold-out has no TS repo so its zero says nothing about TS, the
  library branch could show an effect only through false positives, and the cost paragraph understated the plan's own
  first run. The plan was rewritten, and the final code re-measured, before approval.
- **Panel 1, on the diff:** the library rule missed `await x.get<T>(..)` (the callee was read before the grammar's
  `await` was lifted out), and three gaps the change itself opened (a class that overrides a wrapper takes its base's,
  two classes of one name share a wrapper key, a rule by package took `AxiosHeaders.get` for a request) that the
  author then fixed in the PR, which led to the rule that a change fixes what it opens when that is viable
  (`AGENTS.md`, Principles).
- **Panel 2, on that design:** a chain of wrappers, registered under the simple key only, that `new X()` reached and a
  typed receiver did not (a regression of the first fix), the namespace form `ax.AxiosInstance`, a cost margin that held
  only by the declared reading (three of six noisy pairs were above the limit, now said as it is), and three stale lines
  of the docs.

Lessons: a second panel after a round of fixes earned its cost where the fixes opened new surface (it found a chain the
first fix had made unreachable); no objection of either panel was wrong outright, and none was blocking, so the
second-reader step is for the rare blocking one, as designed; the lenses still overlapped on the cost margin, so the
list of what each lens must not repeat is still open. The records of the runs, with every objection and its evidence,
are kept outside the repo, in `.local/plans/review-records/`.

## Cost, and when to run what

The round above was a research round, not a review. The review itself was 12 % of it. Most changes need only the
review.

| Tier | When | What runs | Cost |
|---|---|---|---|
| **0** | Docs, a mechanical change, a one-line fix with a test | Nothing beyond the CI gates | none |
| **1** | A change with a criterion declared before measuring and a deterministic oracle: most PRs of the indexer | One challenger on the plan, before approval. After the code, a panel of three lenses on the diff, and a second reader for each blocking objection | about 5 agents; one challenger cost 49k output tokens and 7 min; H5-D50's panel on the diff cost 902k subagent tokens and 39 min at `xhigh` |
| **2** | A design choice with real alternatives, a new ADR, a cost lever, a criterion that may be wrong (H5-D50 was this) | The challenger first on the bare plan. Then researchers only for the questions it leaves open. Then a synthesizer, and the challenger again | H5-D50: 760k output tokens, 68 min |

**Keeping Tier 2 short:**

- challenge first: a one-agent pre-mortem of the plan says which questions are really open, so the researchers answer
  those and not all six;
- at most four researchers, each with a stop rule and a tool-call budget (the six used 71 to 114 calls);
- compute shared data once and hand it over (the dry-runs the researchers all needed were run once, before the round);
- serialize heavy container runs: they share one machine, and a loaded machine moved the baseline of the end-to-end
  timing by 10 % during the round;
- a researcher whose answer cannot change the plan's decision is not worth a slot: say so up front and drop it;
- log what was left out, never drop silently.

## How it fits the process

| Stage | The reviewer's part |
|---|---|
| **refine-tech** | When the plan's "Contracts, boundaries and proof" declares a change of behavior, a choice among alternatives, or a cost over a limit: a Tier 1 challenge of the plan before the author approves it; Tier 2 if an alternative is open |
| **implement** | Before the PR opens: the panel of lenses on the diff. Its objections are judged by the author of the change (or its orchestrator), each with a verdict |
| **CI** | An advisory review of the PR as one comment, never a required check (slice 2) |
| **knowledge** | An objection that was right and would prevent a repeat is recorded with its evidence (`record_insight`), so the next plan in that area meets it |

**Judging what comes back.** Each objection gets one verdict, written next to the plan or in the PR, never a silent
discard: *accepted* (the plan or code changes), *refuted* (the source or data says otherwise, with the command), *deferred*
(a registered debt with a strict xfail), or *out of scope*. A blocking objection is reproduced at the source first. The
reviewer's `not_checked` list is read too: it is the measurement it could not make, and may be the next researcher's
question.

## Slices

| # | Slice | Done when |
|---|---|---|
| 1 | The reusable script (`independent-review`: a plan, or a diff with its lenses and the second reader), its prompts and schemas in the repo, and a first use on a real diff | an agent that did not write a PR returns severities and verified blocking objections |
| 2 | The PR-side advisory agent in CI | a maintainer's label starts it and one comment appears on the PR |
| 3 | The stage hooks: `refine-tech` runs the Tier 1 challenge by its rule; `implement` runs the panel before the PR | a plan that declares a change of behavior cannot reach approval unreviewed |
| 4 | The record: per PR, the objections, their severity, how many were confirmed, how many changed the plan, the tokens spent | a quarter of data that says whether the review pays |

**Where the slices stand (2026-11-08).** Slice 1 is done: the script ran on five reviews (a plan and a diff of H5-D50, a
plan and two diffs of H5-D51), and it is now in the repository, `indexer/scripts/review/independent-review.js` with its
prompts and schemas, called by path from any worktree, and its orchestration is tested with simulated agents (`tests/test_independent_review.py`: the merge of one place's
objections, who gets a second reader, the efforts and the limits in each prompt). The runs' records are in `.local/plans/review-records/`, which is the start of slice 4's
data: 5 reviews, 508k tokens for D51's three and 902k for D50's, and no objection yet that the author found wrong.
The researchers' role (Tier 2) has its script too, `indexer/scripts/review/research-round.js`, with the caps H5-D50's round
lacked (at most four questions, a tool-call budget per researcher, `medium` effort), tested the same way.

## Constraints on the CI agent

The PR's code, comments and text are untrusted input to an LLM, and a public repo takes PRs from forks.

- **Never a gate.** Its comment is advice. The gates stay deterministic (H7).
- **Read-only, no secrets in reach.** No write token, no network but the model's, no repo secret in the job's
  environment. The model key is a secret that fork PRs never see.
- **The two-workflow pattern of H7:** the review job runs on `pull_request` with a read-only token and uploads its
  result as an artifact; a second workflow (`workflow_run`), which never checks out the PR's code, posts the comment.
  Never `pull_request_target` with the PR's code checked out.
- **Started by a maintainer,** by a label, or only on PRs from branches of the repo itself. A fork's PR does not start
  it by itself.
- **The comment is data:** the objections are rendered as text, never executed, and the prompt marks everything from the
  PR as data.
- **Third-party code never runs:** it reads the corpus repos and builds none.
- **Cost is bounded:** a cap of agents and tokens per run, and the run says when it hit the cap.

## Decisions made (2026-11-07, with the author)

| # | Decision | Why |
|---|---|---|
| H8-D1 | **The review of a change is done by an agent that did not write it** | The author of a change is the worst reader of it. This was the author's own rule for H5-D50 |
| H8-D2 | **The pattern is to be available at once, in the next rounds, without waiting for CI** | The benefit is in the review, not in where it runs. Slice 1 is a script a chat can run today; CI follows |
| H8-D3 | **The prompts, schemas and the script live in `indexer/scripts/review/`, in English, with a test that runs the script against mocked agents** | A CI agent and a chat must use the same text, and the orchestration (merge, verify, caps) is code that can be tested without a model. Built in #87 and #88 |
| H8-D4 | **The lenses run at `medium` effort and the second reader at `xhigh`; no model is named, so each agent inherits the session's** | At `xhigh` a panel cost 902k tokens (H5-D50); at `medium` the lenses found as many significant objections for 56 % of the cost, and the second reader only reproduces. This replaces the first recommendation, a cheaper model for the second reader |

## Decisions to make with the author

| # | Decision | Recommendation | Why |
|---|---|---|---|
| H8-D5 | Which PRs get the panel in CI | Every PR that carries `graph-change`, `holdout-measurement` or a `refactor` commit, by label; others on request | Those are the PRs whose judgment H7-D6 wants outside the author. The rest stay with the gates |
| H8-D6 | Whether a confirmed objection becomes a recorded insight by itself | Proposed to the author, one click, never automatic | A rule enters the knowledge store only when a person approves it (`rules` versus `context`) |

## Pitfalls

- **The refute bias inflates minor objections.** The severity scale, the cap of eight, and "hold" as a valid verdict
  keep it honest; read the blocking ones first.
- **Same model, same blind spots.** Lenses help; a different model for one lens helps more. Do not read "no objection"
  as "proved".
- **The synthesis can be wrong in a new way.** In the first use it explained a discrepancy with a reason that could
  not hold. Only a reviewer with the raw data caught it. Always hand the reviewer the data.
- **A reviewer that cannot measure is bounded by the data it is given.** A new measurement needs a researcher.
- **Anchoring.** For a diff, never put the author's summary in the prompt.
- **Scratch data is lost** on a reboot or when a job ends. Keep the report and the evidence it cites (in CI, as an
  artifact).
- **A tool the reviewer trusts can be defective.** The checker script of the first use hid 11,145 sites as "no site"
  by comparing a path with an extension to one without. A number an objection depends on is reproduced by a second
  route.
- **Do not let it set a criterion after the data.** Relaxing a limit after seeing the measurement is exactly what the
  challenger flagged; any such change goes to the author, applied to every gate it touches.

## Constraints and conventions

- Everything in the repo is in English; one-line conventional commits, with no body and no attribution trailer.
- No real tenant, client or private project name in the prompts, the script, the artifacts or the comments the bot
  posts. The reviewers' scratch data may name private repos, so it is never committed.
- An LLM is never the parser, and no CI gate is decided by one.
- New code meets the shape targets: complexity ≤ 9, modules ≤ 300 lines.

## Expected deliverables

- The reusable review script, its prompts and schemas, and a test of its orchestration with mocked agents (slice 1).
- The advisory workflow and its comment (slice 2).
- The `refine-tech` and `implement` hooks, with the rule for when each tier runs (slice 3).
- The per-PR record and its report (slice 4).
- The decisions H8-D1…D6 stay in this handoff while it is active, and move to `docs/decisions.md` when it closes. A line
  for H8 is in `AGENTS.md` and the ROADMAP.
