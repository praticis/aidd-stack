# Decisions

> The decisions in force that did not become an ADR, with the context, the choice and the why. The ADRs live in
> `docs/adr/`: ADR-002 (tree-sitter as the base, SCIP as an enrichment) and ADR-003 (a core plus per-language
> modules). **Pending** decisions are in the ROADMAP ("Pending decisions"). When each one was made is in
> `docs/history.md`, and the original text stays in git.

## Stack (D1–D17)

| # | Decision | Why |
|---|---|---|
| D1 | Graph database: **Neo4j Community**. The alternative was Memgraph. | Official MCP, memory and license for internal use. Schema v1 in `neo4j/SCHEMA.md`. |
| D3 | Refs: the tenant's `always` = `[main, master]`. Feature branches come in through the `active` policy (≤ 14 days, ≤ 5 per repo, ephemeral, GC after 30 days) and through `refs.overrides`. | The organization does not use `develop`, which stays in the code's default for compatibility (2026-10-03, F0.3.6). |
| D6 | The name **Atlas**, for the Neo4j database and for the agent-facing MCP (`atlas.*` in the skills). `neo4j/` stays as the infra folder. | Intent tools replace raw Cypher (F0.6). |
| D7 | No default tenant: `AIDD_TENANT` comes from `install.sh` (`.env`), is `${AIDD_TENANT:?}` in the compose file and is required in the indexer. An `auto` that derives no tenant is an error. | A wrong tenant mixes clients' graphs. |
| D8 | Providers: **GitHub first** (F1). The manifest already accepts N sources per tenant. | Each tenant combines providers without changing the format. |
| D9 | A `local` source is read through `git archive` of the refs; revised by D15: also with a mirror, so the workspace stays read-only. | Read without touching the dev's checkout. |
| D10 | Default ref policy: `main`, `master` and `develop` always; active ones ≤ 14 days, ≤ 5 per repo; GC of ephemeral ones after 30 days. | Bounds the indexing cost per repo. |
| D11 | Areas: an optional `areas:` section in `atlas.yaml` (`Repo.area`, groups the `plan`). Domain nodes and Backstage/Compass wait for F2. | Grouping without a premature domain model. |
| D12 | Install ≠ update. The bootstrap indexes the local refs as cloned (no fetch, no credential); keeping the atlas current is a process of its own. | The install cannot depend on a credential or on the network. |
| D13 | Automatic refresh with a dedicated read-only PAT, never the personal key; a 15 min interval. D13's and D14's scheduler was replaced by D15. | A minimal, revocable service credential. |
| D15 | The refresher is a compose service (`aidd daemon`) with bare mirrors in `~/.aidd/mirrors`. The workspace is mounted read-only, and the containers run as the host user. Replaces D14 (systemd on WSL) and D12's fetch on the host. | Works the same on macOS, Linux and WSL, and Docker restarts it. |
| D16 | Knowledge is a stack mechanism, not a skill: an MCP service (`knowledge`) that every stage consumes. The stage's model decides what to record; the service writes it. SARIF and Sonar come in through `aidd ingest`. | The skills mirror the stages and stay few. A hook runs shell and cannot tell a pattern from noise. The atlas stays read-only. |
| D17 | The process policy lives in `policy.yaml` (coverage, harness, review, knowledge), separate from `atlas.yaml`, which says how to read the code. It has the same layers (defaults → tenant → area → repo), and the skills read the effective policy through `policy_for`. | `profile` already means the compose profiles; the skills never do the merge. |

## H2: public corpus and HTTP extractor precision (H2-D1–D21)

| # | Decision | Why |
|---|---|---|
| H2-D1 | H2 has two increments: H2a (the instrument and report v1 with 15 repos) and H2b (~40 repos and the extractor's evolution). | Validate the instrument on a small set before widening it. |
| H2-D2 | Each corpus repo is pinned by SHA, not by HEAD. | With HEAD, the baseline moves by itself and the diff stops meaning anything. |
| H2-D3 | Clones and outputs live outside the repo, in `~/.cache/aidd-corpus/{repos,runs/<date>-<label>}`. | `/tmp` goes away on reboot, and the corpus is not versioned. |
| H2-D4 | An expected list comes only from a committed spec, a published route dump or reading the code. The apps never run. | Running the app executes third-party code. |
| H2-D5 | Routes and calls have separate metrics. Call recall counts only calls with a literal or template path. | The error profiles differ; a URL built at run time is not an extractor failure. |
| H2-D6 | Precision samples from what was extracted; recall samples from the source. | Sampling only from the extracted never shows a false negative. |
| H2-D7 | tRPC is out of scope. | They are procedures, not REST routes. |
| H2-D8 | Java/Kotlin are out. | They are not a language the indexer parses. |
| H2-D9 | Generated clients (NSwag, openapi-generator, oazapfts, ..) are extracted as `HttpCall` with `via: generated-client`, one recognizer per generator. | In v2 there were 371 operations and none extracted. Each generator always writes the same shape, so the FP risk is low. |
| H2-D10 | An inherited `[Route]` in ASP.NET follows inheritance; an ambiguous base name does not inherit. It was one level and became four in F1.14. | 128 jellyfin routes without a prefix; later, Radarr. |
| H2-D11 | **Precision before recall:** a rule that raises recall and drops precision in any repo does not go in. | An FP becomes a wrong edge in the graph after the linker. |
| H2-D12 | A route or call with a prefix the code has and that got lost counts as an error. A config or env prefix (`BaseAddress`, `*_URL`) does not, because it belongs to the linker. | The path is the linker's key. |
| H2-D13 | Measure what the graph receives (after `_dedupe`), without working around the merge of equal routes across apps. | The merge was a real defect (`multi-app-repo`, solved in F1.14 item 5). |
| H2-D14 | H2-D11 judges the error the rule introduces. A new item wrong only because it inherits an already categorized defect counts, but does not block the rule. | Refusing the rule would leave the right items out, and the inherited defect belongs to another rule. |
| H2-D15 | An expected list with a spec is the spec plus the routes checked in the code: a route that exists only in the spec goes out, and a real route outside the spec goes in. | The spec documents the public API, not everything the code serves. |
| H2-D16 | An item that needs more than one fix gets a single category: the most specific one beyond the mount graph. | The ranking says which rule unlocks what. |
| H2-D17 | The item counts in its file's language. The expected list declares `language` per kind when it differs from the repo's, and each category carries its number of repos. | Mixed repos mixed languages, and one large repo does not rank a category alone. |
| H2-D18 | **Portfolio priority:** .NET first, Go and Python (FastAPI/Flask) second, TS third. Django is deferred. | The corpus weighs by the volume of public repos, not by what the real projects use. |
| H2-D19 | TS joins H2 after .NET, Go and Python are essentially closed, in stages with a corpus run and a commit each. | Reuses the mount graph and the `compose` that Go and Python already use. |
| H2-D20 | **Hold-out:** repos the rules never saw, matching the portfolio's profile. The expected list is written before the run, the sample is seeded and judged at the source, and it is measured once, with no tuning. A hold-out repo that gets worked on becomes corpus. | A hold-out that guides rules becomes corpus. The 16 of 2026-10-17 showed overfitting (C# R 48.5 %, Go 19.7 %). |
| H2-D21 | The new hold-out of the F1.14 close moves to after H5, as the first step of its own handoff, also measured on the commit before H5. | H5 changes no behavior; what the hold-out shows is fixed in the refactored code; a difference between the two commits is an H5 regression. Accepted cost: an unseen precision defect stays in the install during H5. |

## H4: public docs and the indexer in its own repo (H4-D1–D12)

These are **proposals**: H4 confirms them with the author before executing. H4-D6 is the author's call. H4-D1 was
decided by the author on 2026-10-19.

| # | Proposal | Why |
|---|---|---|
| H4-D1 | **Every doc in the repo is written in English**, the working docs too (ROADMAP, decisions, history, handoffs, the indexer guide). The other languages are translations of the public docs; this closes D5. | It is the open source standard and the project's (code, schema and ADRs in English), and a newcomer or their AI reads one language. The working docs were in Portuguese until 2026-10-19. |
| H4-D2 | Locales `pt-BR`, `es` (neutral) and `zh-CN`, with BCP 47 tags on the files. | `pt` and `zh` alone are ambiguous. |
| H4-D3 | Translation in tiers: 1 (READMEs, install, overview, FAQ) in all four languages; 2 (guides) in English and pt-BR; 3 (reference, contracts, schema, ADRs, corpus report, CHANGELOG) in English only. | Reference changes with every commit and is the translation that ages first. |
| H4-D4 | Markdown on GitHub with `docs/<locale>/`. A site only when navigation calls for it. | GitHub already renders Mermaid and `<picture>`. |
| H4-D5 | LLM-assisted translation with a glossary and a style guide, and native review when there is one. No Crowdin/Weblate for now. | Few pages per tier, and there is no external translator. |
| H4-D6 | The name of the indexer's repo is **the author's call**. The suggestion is a name of its own, keeping `atlas` as the MCP's name, without renaming commands in the first cut. | "Atlas" collides with `ariga/atlas` and with MongoDB Atlas. |
| H4-D7 | `knowledge` stays in aidd-stack as a package of its own. What it imports from the indexer becomes a declared, versioned public API. | Vault, insights and policy are the methodology, not indexing (D16, D17). |
| H4-D8 | `dotnet-praticis` stays with the indexer in the first cut, as the reference extension. | 5 test modules and the `csharp-praticis-*` fixtures depend on it. |
| H4-D9 | `git filter-repo` carries the indexer's history to the new repo, with a sweep for names and secrets before the first push. | `blame` and the log keep why the rules are so, and the new repo is the chance not to republish what it shouldn't. |
| H4-D10 | An image on GHCR, multi-architecture (amd64 and arm64), per tag. aidd-stack pins tag and digest. | `install.sh` should not build another repo's code. |
| H4-D11 | `SCHEMA.md` and `schema.cypher` move to the indexer, which applies the schema. | The schema always matches the version of whoever writes. |
| H4-D12 | SemVer, a `CHANGELOG.md` in the Keep a Changelog format, and the README pointing at a release. | Today `curl \| bash` gets any commit on `main`. |

## H5: the indexer refactor before SCIP (H5-D1–D5, decided by the author on 2026-10-18)

| # | Decision | Why |
|---|---|---|
| H5-D1 | **The order:** end of F1.14 → H4 phase 0a → H5 → new hold-out (H2-D21) → P2 → SCIP (F1.1, F1.2). H5 absorbs the catalog and the `built_bundle` thresholds (debts of F1.14 item 7). | SCIP needs one place to plug into (a type service), and the extractor grew into god methods and two parallel type systems. |
| H5-D2 | The framework catalog is YAML, with a validated schema and a test. | It is the same format as the conventions. |
| H5-D3 | The targets are complexity ≤ 9 and modules ≤ 300 lines. During H5 the CI only reports; the author turns on blocking. | Code that fits in one reading; blocking comes once the whole code meets them. |
| H5-D4 | A general review of the comments: only what is pertinent stays, with no reference to docs and no project name. | The docs are going to be reorganized, and the code is public. |
| H5-D5 | The MCP is in scope; `cli.py` waits for P2. | P2 will touch the CLI when it splits the repo. |

## H6: the extraction pipeline (H6-D1–D4 decided by the author on 2026-10-19, H6-D5–D6 on 2026-10-20)

| # | Decision | Why |
|---|---|---|
| H6-D1 | **The order:** design H6 now, refactor H5 toward the design, then plug H6 in, then the new hold-out, P2 and SCIP. | H5's types, facts and recognizers take the shape the pipeline needs, so nothing is built twice. |
| H6-D2 | The per-file incremental cache is a requirement. | A refresh after a one-file push should not re-parse the snapshot, and a branch shares most of its files with `main`. |
| H6-D3 | The second read (a rule that needs a tree and another file's fact) is chosen by measurement: resolving in the reduce from summaries, or a second map that re-parses. | Each changes the scanners, the cache and the memory differently; numbers decide. |
| H6-D4 | A technology joins the compose only if it adds no failure handling to build. | A gain in speed that brings retries, duplicate deliveries or stalled jobs to handle costs more than it gives. |
| H6-D5 | **The second read is a second map (B) that reads the file again and scans it with its directory's context, read-only.** Its cache is keyed per package (D): the directory's context, cut to what scanners read, plus the other directories it looked up and its questions to the repo's structure, each with its answer. Resolving in the reduce (A) is dropped. Keying by the entries read (C) stays a refinement. | Step 1: B with D was identical everywhere and changed no scanner. A would turn reads that decide control flow into conditional items. C re-runs 4 times fewer scans at the p90, but it tracks every read. |
| H6-D6 | **The map's batches are files, largest first, cut to a size in lines,** not modules. | The reduce joins the contexts, so a package can be split. A cut by count left the run waiting on the batch of the largest files. |

## H7: regression gates in CI (H7-D1, D3 and D5, decided with the author on 2026-10-19)

| # | Decision | Why |
|---|---|---|
| H7-D1 | The baselines live in the Actions cache, keyed by the code's tree; a miss recomputes them. GHCR comes later, for contributors' downloads. | The extraction is deterministic: a baseline is derived data, and git keeps what must not be lost. |
| H7-D3 | The gates run on every PR that touches the indexer; every push to `main` fills the baselines. | A gate that runs only when someone remembers is not a gate. |
| H7-D5 | Slice 1 before H6's step 1. | The method's checks go into the repo while the context that built them is fresh. |

## Of the working process

| Decision | Why |
|---|---|
| **No LLM as parser.** Extraction is deterministic (tree-sitter); a gap that needs the type of an expression not declared in sight becomes `needs-resolver` and waits for F1.2's resolver. | Reproducible and measurable on the corpus; the boundary with SCIP is in ADR-002. |
| Every change to the extractor follows the cycle: a fixture that fails without the rule → corpus `--baseline` → item-by-item judgment at the source → expected lists (H2-D15/D17) → a new baseline. | A regression in one repo while another improves is the common case. |
| A change to the extractor headed for `main` is validated on a live install before the merge: a dry-run of `main` against the branch on each snapshot and pictures of the graph before and after the reinstall. | Only that showed PR #5's two TS wrapper defects in real code, which the corpus did not have (increment 12). |
| No real tenant or private project name in docs, code, tests or fixtures; public repos may be named. | The repo is public. |
