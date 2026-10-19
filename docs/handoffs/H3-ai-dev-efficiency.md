# Handoff H3 — Measure the effect of the atlas and of knowledge on AI-assisted development

> Paste this file (or ask for `docs/handoffs/H3-ai-dev-efficiency.md` to be read) at the start of a new chat. Before
> anything else, the chat should read `docs/ROADMAP.md` (the skills and knowledge tracks), `docs/golden-questions.md`
> (what the atlas answers and how it is checked) and `docs/knowledge-contract.md`. For the measurement discipline —
> expected list, baseline, judging the diff, the error's category — the model is H2's (`docs/handoffs/H2-roadmap.md`).
>
> **State (2026-10-16):** registered, not started. It was born from a question during H2b: does the framework reduce
> the tokens of AI-driven development, or is the main gain somewhere else? The answer given was an estimate, not a
> measurement; this handoff is to turn it into data.

## Context in one paragraph

The stack gives the agent facts about the code it does not need to rediscover: the atlas graph (symbols, calls,
imports, HTTP routes and calls linked across repos and across refs, through MCP) and the process knowledge
(`policy_for`, `insights_for`, `record_insight`). Building that is costly: indexing, an HTTP extractor measured on a
corpus, the linker, the knowledge service. There is still no number that says how much it gives back, or in what.
Without that number, it is not possible to prioritize what is missing (more extractor recall? leaner MCP answers?
skills S1–S7?) or to defend the cost.

## Hypotheses to confirm or overturn

The estimate of 2026-10-16, without measurement:

1. **A task within one repo:** the token saving is modest. An agent with grep is already efficient there, and most of
   the tokens go to reading the code that will change, reasoning, writing and testing — the graph only shortens the
   discovery.
2. **A task across repos** (changing an HTTP contract, finding who consumes a route, the impact of a branch): the
   difference is large, above all in **completeness**. Without the graph, the agent does not even know which repos to
   look in; a forgotten consumer is a silent break.
3. **The main gain is less rework, not less reading:** an invented dependency, a forgotten consumer and an error
   already fixed before (which process knowledge prevents) cost a whole round of review, test and fix.
4. **Risks that may cancel the gain:**
   - an outdated graph, or one with low recall, creates undue confidence — the agent stops looking;
   - large MCP answers (a whole `repo_map` of a 10-thousand-file repo) cost more tokens than a well-made grep.

## Experiment design

**Tasks.** About 10 real tasks from the portfolio, half within one repo and half across repos, each with a known
answer. The cheapest way to get an expected answer is to **re-enact already merged PRs**:

- start from the commit before the PR;
- give the agent the original card or description;
- compare with what the PR actually changed (files, repos, adjusted consumers, tests).

Deliberately include tasks where the original PR forgot something that later broke, if there are any: they are the
ones that test hypothesis 2.

**Conditions.** The same tasks in each, with the same model, the same prompt or skill, the same starting commit and a
new session per run:

- **A** — no atlas and no knowledge (reading, grep, git);
- **B** — with the atlas;
- **C** — with the atlas and the process knowledge (only when there are accumulated insights in the area).

At least 2 or 3 repetitions per task and condition: the model's variance between runs may be larger than the effect.

**Metrics, per run:**

- input, output and cache tokens. Claude Code's transcripts (`~/.claude/projects/<project>/<session>.jsonl`) record
  the usage per message; a script sums it per session;
- how many of those tokens came from MCP answers and how many from reading files;
- the number of tool calls and the wall time;
- **completeness** against the expected answer: the right files and repos, the consumers found;
- **defects:** broken tests, what review would point out and the iterations until green.

**Analysis.** Per task type (local × across repos), with the median and the spread; no conclusion from a small n
without stating the sample size. The expected result is a map of where the atlas pays off, not a single number.

## Prerequisites

- Enough extractor recall in the tasks' languages. H2 measures that; see the current numbers in
  `docs/handoffs/H2-roadmap.md` before choosing the tasks, and prefer the languages already closed.
- The experiment's repos indexed in the atlas, on the right refs, and the linker run.
- For condition C: insights recorded in the tasks' area; without them, C is the same as B.

## Constraints and conventions

- No real project or tenant names in the docs: the report describes tasks and results in shape, not in content (like
  `golden-questions.md`). The task list and the expected answers stay outside the public repo, in the tenant's space.
- Completeness and defects are judged by the expected answer and the tests; when judgment is needed, a person checks
  a sample. An LLM does not judge its own result.
- Do not optimize the stack in the middle of the measurement: a change to the atlas between runs invalidates the
  comparison. Changes become a new round.

## Expected deliverables

- A script that sums the token usage per session from the transcripts, separating MCP from file reading.
- A report (`docs/ai-dev-efficiency-report.md`, like `corpus-report.md`): the method, the tasks in shape and the
  results per task type and condition.
- An actionable conclusion: where the atlas pays off, where it does not and what to change. For example: trimming
  large MCP answers, prioritizing recall in certain languages, or bringing skills forward or postponing them.
- ROADMAP: item S9 checked, with the summary in `docs/history.md`.
