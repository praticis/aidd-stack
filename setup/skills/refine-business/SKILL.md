---
name: refine-business
description: Understand one or more Jira cards and map what needs to change, and in which projects — use when the user gives a card ID/key (or asks "what does card X need") and wants to plan or scope the work before implementation starts. Also use to refine a card that's underspecified, in a back-and-forth loop with the user.
argument-hint: "<card-key> [card-key...]"
jira_cloud_url: ""
jira_cloud_id: ""
tenant: auto
---

# refine-business — card understanding and project impact mapping

You have access to the Atlassian MCP tools (Jira) and the same `obsidian`,
`qdrant`, and `git` tools the `scan` skill uses.

## Card ID(s)

If this skill was invoked with `$ARGUMENTS`, treat that as the card
key(s) (space-separated). Otherwise, use whatever card ID/key the user
mentioned in their message — the skill works the same either way, this
only affects how you get the value.

## Step 0 — resolve the Jira cloudId (once, cheaply)

Look at this file's frontmatter:

- If `jira_cloud_id` is already set → use it directly. Do **not** call
  `getAccessibleAtlassianResources`.
- Otherwise → call `getAccessibleAtlassianResources` once, find the
  site matching `jira_cloud_url` (or ask the user which site if more
  than one matches / `jira_cloud_url` is empty), and tell the user the
  `cloudId` you found so they can save it into this file's frontmatter
  for next time.

## Step 1 — determine the tenant

Same logic as `scan`'s frontmatter `tenant` field (`auto` derives from
the workspace subfolder; otherwise use the fixed value as-is). This
`<tenant>` is the Qdrant collection to search in the steps below.

## Step 2 — safeguard: make sure the workspace is actually scanned

Before trusting any project-matching in step 4, check coverage:

1. List the project folders under this tenant's part of the
   workspace (each folder containing a `.git` directory counts as a
   project).
2. For each one, check with `qdrant-find` (`collection_name: "<tenant>"`,
   `type: "conventions"`, filtering by `project: "<folder-name>"`)
   whether it already has a saved mapping.
3. If you find projects with **no** saved mapping, tell the user which
   ones, and ask before running `scan` on them — don't silently scan
   an unknown number of repositories. If it's just one or two, it's
   usually fine to just say you're doing it and proceed; if it's many,
   wait for a yes.

This exists because step 4's project-matching can only find a project
that has actually been scanned — an unscanned project is invisible to
that search, not just deprioritized.

## Step 3 — fetch the card(s)

For each card ID/key:

1. Call `getJiraIssue` to get summary, description, and acceptance
   criteria.
2. If the description looks thin or ambiguous, also call
   `listJiraIssueComments` — the missing context is often already
   sitting in a comment thread.

## Step 4 — find which projects are plausibly affected

Use `qdrant-find` with `collection_name: "<tenant>"`, `type: "conventions"`,
and the card's summary + description as the query (semantic search,
no `project` filter this time — you want it to surface candidates
across every project `scan` has already mapped for this tenant).

Treat the top matches as **candidates**, not certainties — a project
scoring low doesn't mean it's unaffected, just that its saved
convention summary didn't mention anything semantically close to the
card. Say so plainly if you're not confident about scope.

## Step 5 — draft the "WHAT TO DO", per project

For each candidate project, write a short, concrete paragraph: what
needs to change in that project specifically, in plain language (not
code, not a spec yet — that's the next phase's job). If a card clearly
needs coordination between two projects (e.g. "project A publishes an
event, project B needs to consume it and send an email"), say that
explicitly, naming both projects and the interaction between them.

## Step 6 — refine with the user, in a loop

If the card is underspecified (missing acceptance criteria, unclear
which system owns some behavior, contradicts what you found in step
4), **stop and ask** — don't guess and move on. Keep the loop going,
re-reading the card with `getJiraIssue` if the user tells you they
updated it on the Jira side, until the "what to do" per project is
something the user actually agrees with.

## Step 7 — save the result

Once the user confirms the understanding is complete, save it to the
vault via `obsidian`, at `<tenant>/cards/<card-key>.md`, with:
- The card key, title, and a short restatement of what it asks for
- The final "what to do" breakdown per project from step 5
- Anything from the refinement loop worth remembering (a decision the
  user made about scope, an edge case they called out)

This is the handoff artifact for whoever writes the technical spec
next (human, or the `tech-refine` skill) — write it for that reader,
not as a transcript of this conversation.

## Never do without explicit confirmation

- Never call `editJiraIssue`, `addOrEditJiraIssueComment`, or any
  other write tool on the card unless the user explicitly asks you to
  post something back to Jira. Understanding and drafting is silent
  by default; writing to Jira is not.
- Never treat a single low-confidence project match from step 4 as
  definitive scope — flag uncertainty instead of picking one.