---
name: scan
description: Project conventions and architecture — use ALWAYS before implementing anything new (endpoint, use case, fix, test), even if the request doesn't mention conventions. Instantly retrieves the already-saved mapping (architecture, naming, contracts, tests, decisions), or, the first time in this solution, scans and saves that mapping for future sessions. Uses the `atlas` code graph when available, with a full fallback to reading the tree.
tenant: auto
---

# Scan — project reconnaissance

You have access to four MCP tools: `atlas` (the code graph — repos,
modules, files, symbols, calls, imports; read-only), `obsidian`
(spec/ADR vault), `qdrant` (semantic memory of lessons and
conventions), and `git` (repository operations).

## Determining the tenant

Look at the `tenant` field in this file's frontmatter:

- If it's `auto` → `<tenant>` is the name of the subfolder immediately
  below the projects workspace root (e.g. in
  `~/workspace/company-name/project-name`, `<tenant>` = `company-name`; in
  `~/workspace/personal/my-app`, `<tenant>` = `personal`).
- Otherwise → use the value as-is as `<tenant>` (e.g. `custom-tenant`).

`<tenant>` is used as the Qdrant **collection name** throughout this
skill — each tenant gets its own physically separate collection, not
a shared one filtered by payload. (`atlas` is already scoped to the
tenant server-side; never pass a tenant to it.)

**IMPORTANT — a common mistake to avoid**: `<tenant>` is NOT the
current repository/project name. If `tenant` is a fixed value (not
`auto`), that exact same value is the `collection_name` for **every**
project you work on from this machine — never substitute the current
project's name as the collection name, even if it feels more natural.
The project name only ever goes in the `project` field of the
payload, never in `collection_name`.

## Vault layout

```
<tenant>/
├── knowledge/
│   ├── shared/                      (reserved — cross-project notes)
│   └── <current-repo-name>/
│       └── <current-repo-name>.md   (this skill's file — see below)
└── refine-business/                 (written by the refine-business skill, not this one)
```

`<current-repo-name>.md` is this project's **index page**, not just a
one-off dump. Other skills or later sessions may add sibling files
inside the same `<current-repo-name>/` folder (code-review notes,
incident write-ups, anything else that accumulates about this
project). When that happens, this index page should grow a short
list of links to them — but don't invent that section before any such
file actually exists.

## Always run at the start of the session

0. **Ask the code graph first (`atlas`, with fallback).**
   Call `atlas_status`. Then:
   - If the call fails, the tool is not listed, or `<current-repo-name>`
     is not among `repos` → atlas is **unavailable for this repo**.
     Say so in one line and continue with steps 1–3 exactly as written
     below (reading the tree yourself). Never block on atlas.
   - Otherwise call `repo_map` for `<current-repo-name>`. Pass
     `ref: "<current branch>"` when `git branch --show-current` is
     listed in that repo's `snapshots`; omit `ref` otherwise (the
     default branch is used). Keep the result as **the structural
     ground truth** for this session: modules and their sizes, entry
     points (HTTP handlers, controllers, commands), external packages,
     symbol kinds. Do not re-derive that list by walking folders.
   - Note the snapshot identity from the response (`ref`, `sha`,
     `indexed_at`) — it goes into the vault page (step 3) so staleness
     is visible later. If `sha` differs from `git rev-parse --short HEAD`,
     the graph is a few commits behind (it refreshes every ~15 min):
     still use it, and mention the gap when it matters.

1. Use `qdrant-find` with `collection_name: "<tenant>"` (the tenant
   value determined above — re-check it if you're unsure), filtering
   by `project: "<current-repo-name>"` and `type: "conventions"`, to
   check whether a saved mapping for this project already exists.
   (If the collection doesn't exist yet, treat it the same as "not
   found" — proceed to step 3.)

2. **If it already exists**: load these conventions as context and
   follow them in any new implementation. If the `repo_map` from step 0
   contradicts them (a layer/module that no longer exists, a new
   adapter, a new external dependency), update the `## Identified
   conventions` section of the vault page and re-store the lesson in
   qdrant; otherwise do not repeat step 3.

3. **If it doesn't exist (first time opening this solution)**: produce
   an objective summary covering:
   - Identified architecture and layers — from `repo_map.modules` and
     `repo_map.entry_points` when atlas is available (confirm with a
     quick look at 2–3 representative files); from the folder
     structure otherwise
   - Naming conventions (classes, files, branches, commits) — read
     representative files; `find_symbol` with `kind` (e.g. `struct`,
     `interface`, `class`) shows naming at scale
   - Testing patterns (framework, coverage, folder structure) — test
     files are visible in `repo_map.modules` (`*_test.go`, `*.spec.ts`,
     `*Tests.cs` counts) and in the source tree
   - Apparent architectural decisions (implicit ADRs in the code) —
     `symbol_context` on a central symbol (e.g. the request decoder,
     the DI container, the base repository) reveals the enforced
     patterns quickly
   - External dependencies and integrations — `repo_map.external_packages`

   Then:
   - Save this summary to the vault via `obsidian`, at the path
     `<tenant>/knowledge/<current-repo-name>/<current-repo-name>.md`
     (create the folders if they don't exist yet). If the page
     already exists, update/complement it rather than overwriting —
     add or revise the `## Identified conventions` section, leaving
     any other section intact (including a links section pointing to
     sibling files, if one has been added since). When atlas was
     used, add a short `## Source` line: `atlas <repo>@<ref> <sha>
     (indexed <indexed_at>)`; otherwise `tree scan (atlas unavailable)`.
   - Save the same summary to `qdrant` as a lesson, using
     `qdrant-store` with `collection_name: "<tenant>"` (same value as
     step 1 — not the project name) and payload
     `{"project": "<current-repo-name>", "type": "conventions"}`
     (the collection itself now identifies the tenant, so it's no
     longer part of the payload), so the next session retrieves it
     instantly without needing to scan everything again.

If `obsidian` or `qdrant` are unavailable in the session, say so in one line and still deliver the summary in the conversation; do not silently skip persistence — tell the user the mapping was **not** saved to the vault/collection so the next session will scan again.

## From here on

Every new implementation must follow the conventions loaded in step 1
or identified in step 3 — do not introduce an architectural or naming
pattern different from what already exists in the project without
explicitly justifying why.

Before touching code, locate the existing pattern and the blast radius
through atlas when it is available — it is faster and more complete
than grep:

- `find_symbol` to find where something similar already exists (pass
  the same `ref` as in step 0 when you are on a feature branch);
- `symbol_context` on the symbol you are about to change: definition,
  container, what it calls, **who calls it**, what the file imports;
- `who_calls` to list every caller of a function you are changing —
  those are the tests and call sites to re-check;
- `cypher_readonly` for anything the other tools do not answer
  (schema: Repo, Snapshot, Module, File, Symbol, Package; edges
  HAS_SNAPSHOT, CONTAINS, IN_SNAPSHOT, CALLS, IMPORTS; `$tenant` is
  bound for you; add `LIMIT`).

Calls in the graph are resolved by name inside the repo (each `CALLS`
edge carries its `strategy`): treat `same-file`/`same-module` hits as
reliable and `unique-name` hits as likely. Calls into external packages
and the standard library are not in the graph. If a tool errors or the
repo/branch is not indexed, fall back to grep and reading files —
never stop because atlas is missing.

At the end of a relevant task (a non-obvious bug fix, a design
decision, a workaround), save a new lesson via `qdrant-store` with
`collection_name: "<tenant>"` (never the project name) and payload
`{"project": "<current-repo-name>", "type": "lesson"}`.
