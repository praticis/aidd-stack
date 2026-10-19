# Handoff H4 — Public documentation: aidd-stack, the indexer in its own repo, and four languages

> Paste this file (or ask for `docs/handoffs/H4-public-docs.md` to be read) at the start of a new chat. Before
> anything else, the chat should read `AGENTS.md`, `docs/ROADMAP.md` ("Where we are", "Principles" and the tracks),
> the current `README.md` and `indexer/README.md`, ADRs 002 and 003, `docs/knowledge-contract.md`, `neo4j/SCHEMA.md`,
> `docker-compose.yml` (services), `setup/install.sh` (steps) and the skills in `setup/skills/`.
>
> **State (2026-10-19):** step 0a done; the rest not started. The visual assets (brand, banner, featured diagram,
> social preview) are made in another process; this handoff defines where they go and what the docs ask of them. H2b
> left `feature/h2-corpus` (PR #4, 2026-10-18), and splitting out the indexer waits for H5 (see "Order"). On
> 2026-10-18 the author added **step 0**: recycle the working docs before writing the public ones. On 2026-10-19 the
> author decided H4-D1: every doc in the repo is written in English, the working docs too. The same day the author
> registered **H4.1** (`docs/handoffs/H4.1-contributor-path.md`): how someone outside, working with an AI, evolves
> the project with the same method. `CONTRIBUTING.md`, the playbooks, the PR and issue templates, the CI checks of the
> method and an acceptance test with a fresh agent come from it.

## Context in one paragraph

`praticis/aidd-stack` is public and the README is minimal (what it is, the installer's `curl`, and links). The
documentation that exists was written for whoever continues the work, not for newcomers: the ROADMAP, the handoffs
and the indexer guide; contracts and reference (`SCHEMA.md`, `knowledge-contract.md`, `corpus-report.md`,
`indexer/README.md`). Until 2026-10-19 the working docs were in Portuguese; they are in English now (H4-D1). Two
changes call for product documentation: the indexer moves to a repository of its own, usable without the rest of the
stack, and the documentation comes to exist in English, Portuguese, Spanish and Chinese. This handoff designs both
together, because the docs follow the code's boundary: writing the documentation before deciding what stays in each
repo would be writing it twice.

## The names the docs need to separate

Today a newcomer finds five things without knowing which is which:

| Name | What it is | Where it lives after H4 |
|---|---|---|
| the Praticis methodology | the process: `scan` → `refine-business` → `refine-tech` → `implement` → `review`, one skill per stage (D16), the knowledge the stages feed and consult, the ROADMAP's principles. `scan` and `refine-business` exist; the others are planned (S5–S7) — the docs say so | aidd-stack (explanation) |
| aidd-stack | the suite that implements the methodology as a ready setup: compose (Neo4j, Qdrant, Obsidian vault, gateway, git and Obsidian MCPs, refresher, `knowledge`), installer, the `aidd` client, skills | aidd-stack |
| the indexer (the `aidd-indexer` package) | the code graph engine: tree-sitter, call resolution, the HTTP extractor, the linker, the refresher, the `atlas` MCP | its own repo |
| `atlas` | today, the name of the Neo4j database and of the read MCP (D6) | H4-D6 |
| conventions (`dotnet-praticis`) | extensions that teach the indexer an architecture pattern; the .NET one is the Praticis SDK's pattern | H4-D8 |

The repo's description on GitHub mentions the Praticis SDK. The docs say what the relationship is (the
`dotnet-praticis` convention recognizes the SDK's pattern) without anything depending on it to work.

## Goal

1. **The boundary between the two repositories** decided and carried out — code, tests, docs, image and history —,
   with aidd-stack consuming the indexer through a published version instead of `build: ./indexer`.
2. **Information architecture** of both repos: the README as the entry point and the docs organized by kind of
   reading (tutorial, guide, reference, explanation).
3. **Languages:** English as the source; `pt-BR`, `es` and `zh-CN` as translations with provenance, a glossary, a
   style guide and a check that flags an outdated translation.
4. **A contract with the assets process:** which images the docs use, in what format, with what variants and at what
   path.
5. Community files (`CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`, `CHANGELOG`, templates) and GitHub metadata.
   `CONTRIBUTING`, the PR and issue templates and the contributor path are H4.1's.
6. **An audit before publishing:** real names, secrets, numbers without a source, broken links.

## What to get from the author at the start

- The **name of the indexer's repo** (H4-D6) and, if there is one, the methodology's public name.
- The **state of the assets process**: what already exists, what is in production, when it arrives. The manifest
  (below) starts from that.
- **Reviewers per language**: the author reviews pt-BR; es and zh-CN need someone, or stay marked as machine
  translation.
- What of the **Praticis brand** third parties may reuse (the code is MIT; the brand, in general, is not).
- Whether there is public documentation of the **Praticis SDK** to link to.

## Decisions to make at the start

The recommendations are the starting point; the chat confirms them with the author before executing. H4-D1 was
decided by the author on 2026-10-19.

**Documentation and languages**

| # | Decision | Recommendation | Why |
|---|---|---|---|
| H4-D1 | Source language | **Decided (2026-10-19): English, for every doc in the repo**, the working docs too (ROADMAP, decisions, history, handoffs, the indexer guide). The other languages are translations of the public docs. Closes the ROADMAP's D5 | It is the project's standard (code, schema and ADRs in English) and open source's; a newcomer or their AI reads one language. The earlier recommendation kept the working docs in Portuguese; the author chose English for all |
| H4-D2 | Locales | `pt-BR`, `es` (neutral, Latin America), `zh-CN` (simplified), BCP 47 tags in the file names | `pt` and `zh` alone are ambiguous (pt-PT, zh-TW); fixing them now avoids renaming files later |
| H4-D3 | What gets translated | In tiers. **1** (four languages): READMEs, install and first steps, the methodology overview, FAQ. **2** (English + pt-BR): guides. **3** (English only): reference, contracts, schema, ADRs, the corpus report, CHANGELOG | Reference changes with every commit and is made of identifiers: it is the translation that ages first. The guides have pt-BR because it is the team's language |
| H4-D4 | Where the docs live | Markdown on GitHub itself, with the `docs/<locale>/` structure ready for a static site. The site (GitHub Pages) only when navigation calls for it — search, many pages per language —, with the tool chosen at that point by criteria: per-folder i18n, search that works in Chinese, Mermaid, a maintained project | GitHub already renders Mermaid and light/dark `<picture>`; a site is more infrastructure and does not change the content if the folder structure is the same |
| H4-D5 | How it is translated | Files in the repo; LLM-assisted translation with the glossary and the style guide in context; native speaker review when there is one. No Crowdin/Weblate until there are external translators | Four languages and few pages per tier; a translation platform is extra process with nobody to use it |

**Boundary and distribution**

| # | Decision | Recommendation | Why |
|---|---|---|---|
| H4-D6 | The indexer repo's name | **The author's call.** Facts: the package is `aidd-indexer`, the CLI is `aidd`, the MCP and the database are `atlas`. "Atlas" alone collides on GitHub with `ariga/atlas` (database schema as code) and with MongoDB Atlas — bad for search and for understanding. Recommendation: a name of its own for the repo and the product, `atlas` kept as the MCP's name inside the stack, and no command renamed in the first cut | A repo that stands alone needs a name that makes sense without aidd-stack; renaming the CLI, image and MCP along with the split mixes two changes |
| H4-D7 | Where `knowledge` lives | In aidd-stack, as a package of its own, taking `core/policy.py` and the `policy` and `knowledge` subcommands. Today it imports `core.config`, `core.manifest`, `core.policy` and `mcp.server.transport_security` from the indexer; the ones that stay in the indexer become the package's **declared public API** (what aidd-stack may import), versioned | The vault, insights and process policy are the methodology, not code indexing (D16, D17); the indexer alone does not need them |
| H4-D8 | Where `dotnet-praticis` lives | In the first cut, **with the indexer**, documented as the reference extension: 5 test modules and the `csharp-praticis-*` fixtures depend on it, and they are the most complete end-to-end test of the conventions mechanism (roles, architectures, `dispatch`, DI). It moves to aidd-stack, or to its own repo, when the Praticis SDK's release pace separates from the indexer's | Move what has a reason to move; taking the convention out now forces writing a generic test convention before any documentation |
| H4-D9 | History | `git filter-repo` taking the history of the indexer's paths (table below) to the new repo, with a sweep for real names and secrets **before** the first push (`--replace-text` if needed). In aidd-stack, one commit removes the paths; the history stays | `blame` and the log are worth a lot in the indexer (why each rule exists is in the commits); aidd-stack is already public, and the new repo is the chance not to republish what should not be there |
| H4-D10 | Distribution | The indexer publishes its image on GHCR, multi-architecture (amd64 and arm64 — there are devs on Apple Silicon Macs), per version tag; aidd-stack pins the version (tag + digest, as SO10 asks). The `knowledge` image becomes built in aidd-stack `FROM` the indexer image. A PyPI package only if someone asks for use without Docker | The whole stack runs in containers; a published image is what `install.sh` needs so as not to build another repo's code |
| H4-D11 | Schema owner | `neo4j/SCHEMA.md` and `neo4j/init/schema.cypher` go to the indexer, which is who writes the graph; an indexer command applies the schema and the `neo4j-init` service starts running it | The applied schema always matches the version of whoever writes; the stack does not copy another repo's file |
| H4-D12 | Versions | SemVer in both, a `CHANGELOG.md` in the Keep a Changelog format, a tagged release. The README's install command points at a release, not at `main` | Whoever installs through `curl \| bash` today gets any commit on `main` |

## Proposed boundary

| Today | Goes to | Note |
|---|---|---|
| `indexer/aidd_indexer/{cli.py,core/,languages/,conventions/,mcp/}` | indexer | except `core/policy.py` and the `policy`/`knowledge` subcommands (H4-D7) |
| `indexer/aidd_indexer/knowledge/`, `core/policy.py`, `indexer/policy.example.yaml`, `tests/test_knowledge.py`, `tests/test_policy.py` | aidd-stack | |
| `indexer/conventions/dotnet-praticis/`, the `csharp-praticis-*` fixtures | indexer | H4-D8 |
| the rest of `indexer/tests/`, `indexer/scripts/`, `indexer/tests/corpus_expected/` | indexer | the corpus and the fixtures are its regression |
| `indexer/Dockerfile` | indexer | the `base`/`indexer` stages; `knowledge` becomes an aidd-stack Dockerfile |
| `indexer/atlas.example.yaml`, `setup/conventions/hexagonal.example.yaml` | indexer | they document indexer formats; `install.sh` starts taking them from the image or the release |
| `neo4j/SCHEMA.md`, `neo4j/init/schema.cypher` | indexer | H4-D11; `neo4j/Dockerfile` (`mcp-neo4j`, debug profile) stays |
| `setup/` (`install.sh`, `install-check.sh`, `aidd`, `skills/`), `docker-compose.yml`, `gateway/`, `git/`, `obsidian/`, `qdrant/`, `antigravity/` | aidd-stack | `refresher` and `mcp-atlas` stay in the compose file, with the published image |
| `docs/indexer-evolution.md`, `docs/corpus-report.md`, `docs/golden-questions.md`, `docs/indexing-process.md`, ADR-002, ADR-003, handoffs H1 and H2 | indexer | |
| `docs/knowledge-contract.md`, handoff H3, this handoff | aidd-stack | |
| `docs/ROADMAP.md` | both | the indexer takes F0–F2 (except the skills), F1.13, U* and its part of security; aidd-stack keeps the skills (S*), knowledge (K*), the rest of security (SO*) and F3 |

What does not exist today and the indexer's repo needs: a **standalone** path — a minimal compose (Neo4j + indexer +
`atlas` MCP) and `index --dry-run --out` without a database —, so that its README has a quick start that does not go
through aidd-stack.

## The docs architecture

The same file names in every language (slugs in English), so that links map one to one and a site generator accepts
them without change. The working docs (ROADMAP, handoffs, ADRs) **do not move** in the repo they stay in: their paths
are cited in every handoff, in the history and in the skills.

**aidd-stack — README** (each section short, with a link to the docs):

1. Language selector; banner (asset, light/dark).
2. What it is, in one paragraph: the Praticis methodology and the suite that implements it.
3. The problem it solves, stated with what has already been measured (golden questions answered by the graph, the
   extractor's P/R). **No token savings before H3.**
4. The methodology in a diagram: the stages and what each one reads and writes.
5. What comes in the box: a service · port · role table.
6. Quick start: requirements (Docker, git, an MCP client), install, `install-check`, first `scan`.
7. Which orchestrators it works with, separating the validated (Claude Code) from the configured (Antigravity) and
   the planned.
8. State: what is stable and what is experimental, with a link to the ROADMAP.
9. Security (localhost only, a link to `SECURITY.md`), contributing, license, "made by Praticis".

**aidd-stack — `docs/<locale>/`:**

```
index.md
getting-started/   install.md · first-project.md (scan) · first-card.md (refine-business)
methodology/       overview.md · stages.md · knowledge.md (the insight lifecycle) · principles.md
guides/            tenants-and-sources.md · process-policy.md · continuous-refresh.md · other-orchestrators.md
                   troubleshooting.md (MCP blocked, disabledMcpjsonServers…) · upgrade.md · uninstall.md
reference/         components.md · cli.md · configuration.md (.env, policy.yaml) · knowledge-tools.md · vault-contract.md
security/          threat-model.md (closes SO15) · hardening.md
faq.md
```

**Indexer — README:** what it extracts (micro and macro, the graph in a diagram); languages and frameworks with the
corpus P/R table, with the date, the corpus size and a link to the method — "measured, not felt" is the project's
argument; a standalone quick start; the MCP's 11 tools; how to extend it (language, framework, convention); who uses
it (aidd-stack).

**Indexer — `docs/<locale>/`:** `concepts/` (the graph model, resolution strategies, `confidence`/`evidence`, refs
and snapshots), `getting-started/`, `guides/` (`atlas.yaml`, the ref policy, conventions, adding a language or a
framework, measuring with the corpus), `reference/` (schema, MCP tools, CLI, `convention.yaml`, `atlas.yaml`) and
`explanation/` (ADRs, the corpus report). The English `CONTRIBUTING.md` summarizes the guide's checklist (§6) and
points to `indexer-evolution.md`, which phase 0b rewrites in English for the new architecture.

## Languages: how it works

- **Files.** `README.md` (English), `README.pt-BR.md`, `README.es.md` and `README.zh-CN.md` at the root; docs in
  `docs/<locale>/<same path>`.
- **Selector.** The first line of each page, with the four languages, generated by a script — never by hand.
- **Provenance.** Each translation starts with a comment, invisible on GitHub:
  `<!-- i18n: source=docs/en/x.md source_sha=<sha> status=machine|reviewed reviewer=<handle> -->`.
- **Lag.** A script (`scripts/i18n_check.py`, in CI) compares `source_sha` with the last commit that touched the
  source and lists the outdated translations, the missing tier-1 pages and the broken links, anchors and images. An
  outdated page gets a visible notice ("this translation may be outdated — see the English version"). CI warns on lag
  and fails on missing tier-1 pages and on a broken link.
- **Glossary** (`docs/i18n/glossary.md`): term × language, with the list of what is **not** translated — skill,
  service and tool names (`scan`, `refine-business`, `atlas`, `knowledge`, `who_consumes`…), graph terms
  (`Snapshot`, `HttpEndpoint`, `ref`), `tenant`, MCP. What is translated, and how (skill, insight, vault), is decided
  with each language's reviewer.
- **Style guide** (`docs/i18n/style.md`): pt-BR with "você" and the imperative in instructions; neutral es, with
  "tú"; zh-CN with full-width punctuation in prose and a space between Chinese characters and Latin words or numbers.
- **Never translated:** code blocks, commands, configuration keys, identifiers, paths, terminal output, file names.
  Headings are translated, so anchors change per language: the script validates them with GitHub's slug algorithm.
- **Flow:** a change in English → CI flags the outdated translations → one PR per language (assisted translation +
  review) → `status: reviewed` when a native speaker reviewed it. Without a reviewer, `status: machine` and a visible
  note that the translation is machine-assisted: the reader knows what they are reading.

## A contract with the assets process

The two processes meet at a manifest, `docs/assets/README.md`: each slot with its use, dimensions, variants, path and
state (`pending` / `delivered`). The docs reference the slots by fixed path from the start, and `i18n_check.py` fails
if a published page points at an asset that does not exist.

| Slot | Where it shows | Format | Variants | Text in the image |
|---|---|---|---|---|
| logo (symbol) | READMEs, site, favicon | SVG | light/dark | no |
| banner / wordmark | top of the READMEs | SVG (+ PNG) | light/dark | only the name; the tagline goes in the Markdown, to be translated |
| social preview | GitHub Settings (manual upload, outside the repo) | PNG 1280×640 | one per repo | English |
| methodology diagram (featured) | README, `methodology/overview` | SVG | light/dark; one per language if it has text | avoid; if it has some, `name.<locale>.svg` |
| technical diagrams (components, graph model, flows) | reference and concepts | **Mermaid in the Markdown**, not an asset | GitHub renders it and follows the theme | translated with the page |
| screenshots and terminal recordings | first steps | PNG or a recording SVG | — | the output stays in English: it is what the tool prints |

Rules for whoever produces them: optimized SVG, with the logo's and the wordmark's text converted to curves (an image
on GitHub does not load fonts); light/dark through `<picture>` with `prefers-color-scheme`; up to ~200 KB per image;
the alt text is written in the docs, in each language, never embedded. A note in `docs/assets/brand/` and in the
README says what of the brand may be reused (the author's decision; the code stays MIT).

## Community files and metadata (in both repos)

H4.1 designs `CONTRIBUTING.md`, the PR and issue templates and `CODEOWNERS` around the method (the evidence each
contribution carries). The rest is here.

- `CONTRIBUTING.md` (English, with a pt-BR version), `CODE_OF_CONDUCT.md` (Contributor Covenant, which has official
  translations), `SECURITY.md` (channel: GitHub's *private vulnerability reporting*; what counts as a vulnerability
  here — MCP exposure, tenant isolation, poisoned memory, SO9), `CHANGELOG.md`, `.github/ISSUE_TEMPLATE/*.yml`,
  `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`.
- Issues preferably in English, accepted in all four languages (the template says so).
- A checklist of the settings that are not in a file: description, topics, website, social preview, Discussions,
  *private vulnerability reporting*, releases.

## Audit before publishing

- **Real names** (the usual rule, now with more people reading). The two findings while reading for this handoff (a
  service name in the ROADMAP's 2026-10-12 log and an environment variable in `H2-public-corpus.md`) were replaced on
  2026-10-18. Also sweep the history that goes to the new repo (H4-D9).
- **Secrets** in the whole history of both repos (gitleaks or trufflehog), before the new repo's first push.
- **Numbers:** every number in the public docs comes from a reproducible source (the corpus report, the golden
  questions), with a date. No productivity or token gains until H3 measures them.
- **Dangling references:** ADR-001 (Neo4j) is cited in the history and does not exist in `docs/adr/` — write it or
  drop the citation. aidd-stack's links to `indexer/...` start pointing at the new repo.

## Order

0. **Recycle the working docs** (a step the author asked for on 2026-10-18; details in the section below). The
   working docs had become a record of everything: some 600 KB, close to 150 thousand tokens, so as not to lose
   context. The step keeps in them only what is and will stay important, so that a contributor who downloads the
   project can hydrate their own AI with the context: what the project is, what has been done, why, where we are and
   where we are going. The public docs (steps 4 onward) come from that base. Two phases:
   - **0a, right after the F1.14 close** (the author wanted to put an end to H2 first; recycling H2's docs while it
     was still changing would be rework): the entry point, the compacted history, the distilled decisions and the
     minimal README. It touches only docs.
     *Done on 2026-10-19, with these results:*
     - *the new pieces: `AGENTS.md` (read directly by agent tools, with no `CLAUDE.md`), `docs/history.md`,
       `docs/decisions.md` and the minimal README;*
     - *the ROADMAP went from 148 to 39 KB, the corpus report from 178 to 12 KB, the golden questions from 26 to
       15 KB, and the closed handoffs became summaries;*
     - *the working docs went from ~640 to ~273 KB. The rest of the ~150 KB target is `indexer-evolution.md`
       (97 KB), rewritten in 0b;*
     - *the old text stays in git, at `1d73bb0`;*
     - *every doc was translated to English (H4-D1), except two: the H5 handoff, translated on its branch, which
       still edits it, and `indexer-evolution.md`, which 0b rewrites.*
   - **0b, after H5:** `indexer-evolution.md` rewritten in English for the new architecture (it is H5's step 11).
     Before that, rewriting the rules table would be wasted work: it becomes the recognizer catalog.
1. **Decisions** H4-D2…D12 and what to get from the author (the section above).
2. **The docs architecture as a sketch** — the titles and the question each page answers, without the text. It can
   run now, because it does not depend on paths.
3. **Splitting out the indexer**, after H5, to take the already refactored code. Mechanical and without changing
   behavior, like ADR-003; regression = `pytest`, the corpus byte for byte equal to the current baseline and a
   **clean install** of aidd-stack with the published image passing `install-check`. The new repo's CI: tests, a
   multi-architecture build, publishing to GHCR per tag. **Done when** both repos install and test on their own and
   one points to the other.
4. **English content** for both repos, reusing what exists after step 0: `knowledge-contract.md` →
   `vault-contract`, `SCHEMA.md` → reference, `corpus-report.md` → explanation, `indexer/README.md` split between the
   README and guides, the skills → `methodology/stages`. **Done when** someone who has never seen the project — a
   person, or a new agent session reading only the docs — installs it and runs the first `scan` without help.
   The contributor path (`CONTRIBUTING.md`, the playbooks, the explanation of the method, the templates and their
   acceptance test) is H4.1, which runs alongside and shares this step's English base.
5. **Language infra:** glossary, style guide, `i18n_check.py`, the CI workflow.
6. **Translations:** tier 1 in pt-BR (the author reviews), then es and zh-CN; tier 2 in pt-BR.
7. **Assets** as they are delivered, community files, repo settings and the first release of both.
8. *(Optional)* a site, when navigation calls for it (H4-D4).

## Step 0 — recycle the working docs

**The rule:** separate the current truth from history. Git keeps every version, so nothing is really lost. What has
to survive, distilled, are the decisions and the whys. The working docs **do not change paths** (see "The docs
architecture"). A closed handoff becomes a short summary in the same file, and is not deleted.

| Stays | Goes or is condensed |
|---|---|
| the current state, principles, what is open | the narrative of each increment (git and the corpus baselines keep it) |
| decisions with the why, 2 to 4 lines each | the log of the closed handoffs (H1, H2-public-corpus, H2-roadmap), after distilling decisions H2-D1…D20 |
| how to run, test and measure | numbers repeated across docs: each number lives in one place, and the others point to it |
| the corpus method and current result, the gap ranking | catalogs of cases inside prose |
| the active handoffs (H3, H4, H5) | the ROADMAP's daily log, which becomes one milestone per line |

**The structure:**

- **`AGENTS.md`, at the root:** the entry point for a contributor or their AI, in up to ~200 lines. The name is the
  one several agent tools already look for, and Claude Code reads it directly when there is no `CLAUDE.md`. It holds:
  - what the project is, in one paragraph;
  - the repo map, the architecture in one text figure and the principles;
  - how to install, test, run the corpus and measure;
  - where we are and the current focus;
  - where to find things.
- **`docs/ROADMAP.md`:** "Where we are" in a few lines, the principles, the phases and the tracks with the open
  items. A done item becomes one line with a link to where the result is.
- **`docs/history.md`:** the project's milestones, one per line, with the date and the commit or PR. The daily log
  that was in the ROADMAP is condensed here.
- **`docs/decisions.md`:** the decisions that did not become an ADR (H2-D1…D20, H4-D*, H5-D*), each with the context,
  the choice and the why. The ADRs stay as they are.
- **`docs/corpus-report.md`:** the method, the per-language table of the current baseline, the gap ranking and a
  short table of baselines (date, what changed, totals). The narrative of each increment goes.
- **`docs/golden-questions.md`:** the questions, the method and the result of the last round; the old rounds become
  one line each.
- **`README.md`:** minimal until step 4: what it is, how to install and a link to `AGENTS.md` and the ROADMAP.

**Done when:**
- the working docs add up to at most ~150 KB;
- a new agent session, reading only `AGENTS.md` and what it points to, answers right:
  - what the project does;
  - what phase it is in;
  - why the extractor is tree-sitter and not an LLM;
  - how to measure a change to the extractor;
  - what comes before SCIP;
- no internal link breaks;
- no decision in force is lost: each one has a line in `decisions.md` or in an ADR.

## Pitfalls

- Translating reference: it ages on the next commit. The tiers (H4-D3) exist for that.
- The multi-architecture image downloads the tree-sitter grammars **per architecture** at build time (it is one `.so`
  per language): check `selftest` on both.
- The build fingerprint (`indexer_build`) includes the installed convention packages. If `dotnet-praticis` moves out
  later, the computation must keep seeing it, or a snapshot stops re-indexing when it changes.
- Without the declared public API (H4-D7), an internal refactor of the indexer breaks `knowledge` in the other repo.
- The README's `curl | bash` is the first command a stranger runs: it must point at a release (H4-D12) and say what it
  installs before installing.
- The social preview is configured by hand in Settings; committing the image is not enough.

## Constraints and conventions

- No real project or tenant names in docs, code or published history.
- The public docs describe what exists and has been validated; what is a plan shows as a plan, with a link to the
  ROADMAP.
- A technical and factual tone, like the current docs: no promises and no "magic".
- The working docs' paths do not change (ROADMAP, handoffs, ADRs).
- A translation is never edited without updating its provenance header.

## Expected deliverables

- From step 0: `AGENTS.md`, `docs/history.md`, `docs/decisions.md`, the compacted working docs (at most ~150 KB), the
  closed handoffs reduced to summaries, and the minimal README.
- Two repositories with the boundary above carried out and aidd-stack installing the indexer's published image.
- READMEs in four languages in both repos; `docs/<locale>/` with tier 1 in all of them, tier 2 in pt-BR and tier 3 in
  English.
- Glossary, style guide, `i18n_check.py` and the CI workflow.
- `docs/assets/README.md` with the slots, and the delivered assets in place.
- Community files, repo settings checked and the first release with a `CHANGELOG`.
- The audit's result in the PR: what was found and what was done.
- ROADMAP: items P0–P6 checked and the indexer's ROADMAP born from the split.
