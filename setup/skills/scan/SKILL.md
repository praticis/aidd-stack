---
name: scan
description: Project conventions and architecture — use ALWAYS before implementing anything new (endpoint, use case, fix, test), even if the request doesn't mention conventions. Instantly retrieves the already-saved mapping (architecture, naming, contracts, tests, decisions), or, the first time in this solution, scans and saves that mapping for future sessions.
tenant: auto
---

# Scan — project reconnaissance

You have access to three MCP tools: `obsidian` (spec/ADR vault),
`qdrant` (semantic memory of lessons and conventions), and `git`
(repository operations).

## Determining the tenant

Look at the `tenant` field in this file's frontmatter:

- If it's `auto` → `<tenant>` is the name of the subfolder immediately
  below the projects workspace root (e.g. in
  `~/workspace/company-name/project-name`, `<tenant>` = `company-name`; in
  `~/workspace/personal/my-app`, `<tenant>` = `personal`).
- Otherwise → use the value as-is as `<tenant>` (e.g. `custom-tenant`).

`<tenant>` is used as the Qdrant **collection name** throughout this
skill — each tenant gets its own physically separate collection, not
a shared one filtered by payload.

**IMPORTANT — a common mistake to avoid**: `<tenant>` is NOT the
current repository/project name. If `tenant` is a fixed value (not
`auto`), that exact same value is the `collection_name` for **every**
project you work on from this machine — never substitute the current
project's name as the collection name, even if it feels more natural.
The project name only ever goes in the `project` field of the
payload, never in `collection_name`.

## Always run at the start of the session

1. Use `qdrant-find` with `collection_name: "<tenant>"` (the tenant
   value determined above — re-check it if you're unsure), filtering
   by `project: "<current-repo-name>"` and `type: "conventions"`, to
   check whether a saved mapping for this project already exists.
   (If the collection doesn't exist yet, treat it the same as "not
   found" — proceed to step 3.)

2. **If it already exists**: load these conventions as context and
   follow them in any new implementation. Do not repeat step 3.

3. **If it doesn't exist (first time opening this solution)**: scan
   the repository structure (folder organization, layer/DDD pattern,
   naming conventions, testing stack, recurring architectural
   patterns) and produce an objective summary covering:
   - Identified architecture and layers
   - Naming conventions (classes, files, branches, commits)
   - Testing patterns (framework, coverage, folder structure)
   - Apparent architectural decisions (implicit ADRs in the code)

   Then:
   - Save this summary to the vault via `obsidian`, at the path
     `<tenant>/<current-repo-name>.md` (create the `<tenant>/` folder
     inside the vault if it doesn't exist yet). If the page already
     exists, update/complement it rather than overwriting — add or
     revise the `## Identified conventions` section.
   - Save the same summary to `qdrant` as a lesson, using
     `qdrant-store` with `collection_name: "<tenant>"` (same value as
     step 1 — not the project name) and payload
     `{"project": "<current-repo-name>", "type": "conventions"}`
     (the collection itself now identifies the tenant, so it's no
     longer part of the payload), so the next session retrieves it
     instantly without needing to scan everything again.

## From here on

Every new implementation must follow the conventions loaded in step 1
or identified in step 3 — do not introduce an architectural or naming
pattern different from what already exists in the project without
explicitly justifying why.

At the end of a relevant task (a non-obvious bug fix, a design
decision, a workaround), save a new lesson via `qdrant-store` with
`collection_name: "<tenant>"` (never the project name) and payload
`{"project": "<current-repo-name>", "type": "lesson"}`.