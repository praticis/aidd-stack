# Project knowledge — vault contract

What the stages of the process (`scan`, `refine-business`, `refine-tech`, `implement`) write about a
project, where, and in which shape, so that one stage's output is the next one's input and a person
can open the vault and find the way in. The **knowledge service** (`insights_for`, `record_insight`,
`policy_for`) implements the deterministic half of this contract; skills supply the judgement (what
is worth recording, with which evidence).

Contract version: **1**.

## Principles

1. **One writer per block.** Machine-written parts of a page sit between markers and are rewritten
   only by their owner. Everything outside markers belongs to people and is never touched.
2. **Notes are the source of truth, the index is a view.** The knowledge block of an index page is
   regenerated from the insight notes; editing it by hand is pointless (the next write replaces it).
3. **Provenance always.** An insight without evidence is not recorded.
4. **Knowledge is data, not instructions.** Only `accepted` and `enforced` insights are rules an
   agent follows; `observed` and `recurring` are context. Insight text is never executed as an
   instruction, whatever it says (an insight can carry text copied from a PR comment or a scanner).
5. **People promote.** No tool moves an insight to `accepted`; a person does, inside the process
   (`refine-tech`) or by editing the note's frontmatter.

## Vault layout

```
<tenant>/
├── knowledge/
│   ├── <repo>/
│   │   ├── <repo>.md               project index — the way in
│   │   └── insights/<slug>.md      one insight per note
│   └── shared/
│       └── insights/<slug>.md      insights that hold for several repos of the tenant
└── cards/<card>.md                 refine-business output (one per card)
```

`<tenant>` is the atlas tenant, `<repo>` the repository name as atlas knows it.

## Blocks and markers

```
<!-- aidd:<block>:start -->
...generated...
<!-- aidd:<block>:end -->
```

A writer replaces what is between its own markers. When its markers are missing it inserts the
block at its canonical position (below), creating the page if needed. A block is never split, nested
or moved by its writer; a person may move a whole block (markers included) and writers keep it there.

## Project index — `<tenant>/knowledge/<repo>/<repo>.md`

Frontmatter (owned by `scan`; other keys a person adds are kept):

```yaml
---
type: project-index
contract: 1
tenant: acme
project: orders-api
atlas: {ref: main, sha: 1a2b3c4d5e, indexed_at: 2026-10-13T12:00:00Z}   # null when written without atlas
updated: 2026-10-13
---
```

Canonical order of the page:

| Position | Block | Owner | Content |
|---|---|---|---|
| 1 | `# <repo>` title | `scan` (first write only) | |
| 2 | `aidd:scan` | `scan` | overview, architecture (layout and roles when a convention applies), conventions, layers, integrations (exposed routes, consumers, dependencies), source line |
| 3 | `aidd:policy` | `scan` | the effective process policy of the repo, read-only (below) |
| 4 | `aidd:knowledge` | knowledge service | insights by topic (below) |
| — | anything else | people | free text: decisions, links, notes |

A page written before this contract (no markers) is migrated once by `scan`: its generated sections
(`## Identified conventions`, `## Source`) move into `aidd:scan`; the rest stays as people's text.

### `aidd:policy`

Rendered from `policy_for(repo)` (or `aidd policy show <repo> --json`). Changed only in
`~/.aidd/policy.yaml` — the block says so:

```markdown
<!-- aidd:policy:start -->
## Process policy
_Effective policy for this repo — change it in `policy.yaml`, not here._

| Rule | Value | From |
|---|---|---|
| coverage.min | 80 | tenant acme |
| coverage.new_code_min | 85 | area payments |
| harness.max_attempts | 3 | built-in |
| review.spec_approval | required | built-in |
| review.adr_when | new-integration, new-module | built-in |
<!-- aidd:policy:end -->
```

`knowledge.*` keys are not rendered (they tune the service, not the project).

### `aidd:knowledge`

Regenerated after every `record_insight` that touches the repo (and by the aging job). One heading
per topic that has live insights, in vocabulary order; inside a topic, by status (`enforced`,
`accepted`, `recurring`, `observed`), then by `occurrences` descending, then `last_seen` descending.
`archived` insights are not listed. Shared insights that apply to the repo are listed under their
topic with a `(shared)` mark. Links are vault-absolute (Obsidian resolves them from anywhere) with
the summary as the alias; rules (`accepted`, `enforced`) are in bold.

```markdown
<!-- aidd:knowledge:start -->
## Knowledge
_Generated from the insight notes — do not edit here._

### Security
- [[acme/knowledge/orders-api/insights/sql-built-by-concatenation|SQL built by concatenation in repositories; use parameters]] — **enforced** · 3× · last 2026-10-02
- [[acme/knowledge/shared/insights/secrets-in-logs|Secrets reach the logs; mask them in the logger]] (shared) — **accepted** · 2× · last 2026-09-20

### Review
- [[acme/knowledge/orders-api/insights/handler-without-validator|Handlers call the repository before validating the command]] — recurring · 3× · last 2026-10-11
<!-- aidd:knowledge:end -->
```

An index with no live insight renders the heading and `_No insights recorded yet._`.

## Insight note — `insights/<slug>.md`

`<slug>`: lowercase, `[a-z0-9-]`, ≤ 80 chars, derived from the summary when the note is created and
never changed afterwards (links point to it). A collision within the folder appends `-2`, `-3`...

### Frontmatter

| Key | Type | Written by | Meaning |
|---|---|---|---|
| `type` | `insight` | service | |
| `contract` | `1` | service | |
| `id` | string | service | `<tenant>/<scope-repo-or-shared>/<slug>` — stable identity |
| `tenant` | string | service | |
| `scope` | `repo` \| `shared` | service | `shared`: lives in `knowledge/shared/`, applies to the repos in `repos` (empty = every repo of the tenant) |
| `repos` | list | service | repos it applies to: `[<repo>]` for scope `repo`; for `shared`, empty (every repo of the tenant) unless a person narrows it |
| `topic` | slug | skill | one of the topic vocabulary (below) |
| `summary` | string ≤ 200 | skill | one sentence: the problem and what to do instead |
| `severity` | `low` \| `medium` \| `high` \| `critical` | skill | impact when it happens again |
| `status` | lifecycle (below) | service / person | |
| `occurrences` | int ≥ 1 | service | times recorded (each `record_insight` that matched it) |
| `first_seen` / `last_seen` | date | service | |
| `applies_to` | map | skill | where it bites: `files` (globs), `roles` (convention roles), `symbols` (qualified names); any may be empty |
| `rule` | string | person / service | for `enforced`: the convention rule or lint id that now checks it |
| `approved_by` / `approved_at` | string / date | person (via skill) | set when promoted to `accepted` |
| `evidence` | list | service | provenance entries (below), newest first, at most 20 kept |

### Body

```markdown
# <summary>

## What happened
What was observed and why it is a problem (concrete, with the case that triggered it).

## What to do instead
The rule a developer or agent follows to avoid it — checkable when possible.

## Notes
Free text. People may edit any section; the service rewrites only the frontmatter.
```

The service writes the body on creation only. Later occurrences update the frontmatter
(`occurrences`, `last_seen`, `evidence`, maybe `status`) and never the body.

### Evidence entry

```yaml
- at: 2026-10-11
  source: pr-review | review | harness | sarif | sonar | incident | session | scan
  repo: orders-api
  ref: feature/refund        # when known
  sha: 1a2b3c4d5e            # when known
  location: internal/refund/handler.go:42      # file:line, when there is one
  link: https://github.com/acme/orders-api/pull/48#discussion_r123   # when there is one
  tool: semgrep/sql-injection                  # for scanners: tool/rule id
  note: one line on what this occurrence was
```

`source` values: `pr-review` (comment on a pull request), `review` (the senior review of
`implement` rejecting a change), `harness` (the harness exhausting `harness.max_attempts`), `sarif`
and `sonar` (scanner ingest), `incident`, `session` (end-of-task lesson), `scan`.

## Topics

Built-in vocabulary, in index order: `architecture`, `review`, `quality`, `security`, `incident`,
`decision`, `business`. A tenant extends it in `policy.yaml` (`knowledge.topics`); entries are added
after the built-ins, which cannot be removed. `record_insight` refuses a topic outside the effective
vocabulary (and names the closest one), so the same subject never splits into `security`,
`segurança` and `sec`.

## Lifecycle

```
observed ──► recurring ──► accepted ──────────► enforced
(1×)         (N×)          (a person approved)   (a check now catches it)
   └───────────────────────────────────────────► archived
```

| Transition | Who | When |
|---|---|---|
| → `observed` | service | `record_insight` with no matching insight |
| `observed` → `recurring` | service | `occurrences` reaches `knowledge.recurring_after` (policy) |
| `observed`/`recurring` → `accepted` | person | approved in `refine-tech` (sets `approved_by/at`) or frontmatter edit |
| `accepted` → `enforced` | person / service | a convention rule or lint now checks it (`rule` set) |
| any → `archived` | service / person | not seen for `knowledge.archive_after_days` (policy), or discarded by a person |
| `archived` → previous status | service | recorded again (occurrences continue) |

`insights_for` returns `accepted` and `enforced` as **rules** and `observed`/`recurring` as
**context**, labelled as such.

## Matching (dedup)

`record_insight` looks for an existing insight with the same `topic` among the ones that apply to the
repo (its own notes and the tenant's shared notes): first the same summary sentence (normalized),
then semantic closeness — cosine similarity of the `document` below ≥ 0.83 (`KNOWLEDGE_MATCH_THRESHOLD`;
measured with the model: paraphrases of one insight score 0.85–0.96, different insights of the same
area up to 0.81). A match increments it; otherwise a new note is created. The result says which
(`created` | `updated`, with the note path and the `matched_score`) so the skill can tell the person.
When Qdrant cannot be reached nothing is recorded (a new note would risk a duplicate).

## Qdrant mirror

Every insight is mirrored as one point in the tenant collection, in the format `mcp-server-qdrant`
reads, so `qdrant-find` in a skill finds insights next to the other lessons:

- collection: `<tenant>`
- point id: UUIDv5 of the insight `id` (rewritten in place on every update)
- vector: named `fast-bge-small-en-v1.5`, model `BAAI/bge-small-en-v1.5` (FastEmbed) — the same
  `EMBEDDING_MODEL` as the `mcp-qdrant` service; a different model would make the two invisible to
  each other
- payload:

```json
{
  "document": "<summary>\n\n<What to do instead>",
  "metadata": {"type": "insight", "project": "<repo or 'shared'>", "topic": "security",
               "status": "accepted", "severity": "high", "note": "<tenant>/knowledge/<repo>/insights/<slug>.md",
               "contract": 1}
}
```

The vault note wins on disagreement: the service rebuilds the point from the note.

## Versioning

`contract` in every frontmatter says which version wrote it. A change that existing pages cannot
satisfy bumps the version; writers migrate older pages the first time they touch them.
