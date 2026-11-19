# Handoff H11 — How the Atlas is versioned, released and installed

> Paste this file (or ask for `docs/handoffs/H11-release-and-distribution.md` to be read) at the start of a new chat. Before
> anything else, the chat should read, in this order:
> - `AGENTS.md`, the entry point;
> - `docs/handoffs/H10-roadmap-reorganization.md`, section 1 (the premise) and section 1.3 (what the Atlas keeps stable);
> - `README.md`, `setup/install.sh`, `setup/install-check.sh`, the `setup/aidd` wrapper and `docker-compose.yml`;
> - `.github/workflows/indexer.yml`, and `docs/indexer/method.md` §4.7 to §4.9 (the live validation);
> - `indexer/aidd_indexer/core/build.py` (the build fingerprint) and `indexer/aidd_indexer/__init__.py`;
> - `docs/decisions.md`, rows H4-D10 and H4-D12; `docs/ROADMAP.md`, item SO10; and `docs/roadmap/phase-3-central.md`,
>   items F3.2 and F3.7.
>
> The author has a **private appendix** for this handoff, with a reference that cannot be named in a public repository. Ask
> for it before planning, and do not copy any line of it into `docs/`, a PR or an issue.
>
> **State (2026-11-18):** judged. The design it asked for lives outside the repository, with the private appendix. Its
> items enter the roadmap during H10's reorganization, and its work starts after that. No tag, release, image or
> workflow exists yet.

## What is asked

1. This repository is narrowing to the Atlas (H10, section 1). Pieces will be removed from it, and the first removal that
   reaches `main` changes what an install delivers. Today nothing stands between `main` and a machine: there is no version a
   person can name, no release, and the installer takes whatever `main` holds.
2. The author wants the question answered as what it is: **how the Atlas is versioned, released and installed**, and how its
   development flow feeds that. A tag before the first removal is one small part of it.
3. The author built, on another project, a development and CI flow with releases that he likes (section 3). He wants it
   **considered as a reference**, with what transfers to a tool of this kind and what does not.
4. The work runs as a round: reading fronts, a critic, and a judgment (section 5). The result is a design the author can
   decide on, and the items it creates in the roadmap (section 7).

## 1. Why now

- **The install command takes `main`.** `README.md` tells a person to pipe `setup/install.sh` from `refs/heads/main`.
- **The installer clones the default branch, whatever URL served it.** A script fetched from a tag would still install
  `main`. So "the README points at a tag" pins nothing by itself.
- **A removal is not an upgrade a machine expects.** The day a removal merges, a machine that repeats the command it already
  has loses a service, with no warning and no version to go back to.
- **The consumers now live outside this repository.** They talk to the Atlas only through MCP and need a version to check
  (H10, section 1.3, point 5).
- **Two decisions already ask for it,** written for a split of the repository that no longer happens: an image on a
  registry, per tag (H4-D10), and SemVer, a changelog and the README at a release (H4-D12). The supply-chain item (SO10) asks
  for digests, a hash lock, an SBOM and a scan.

## 2. What this repository has today

*(The reading of whoever wrote this handoff, on 2026-11-15. The round confirms each line in the code.)*

| What | How it is today |
|---|---|
| a version | `INDEXER_VERSION` in `indexer/aidd_indexer/__init__.py`, a constant bumped by hand ("moves when someone remembers", `core/build.py`). `indexer/pyproject.toml` carries another number, and the two disagree |
| what decides a re-index | the **build fingerprint** (`core/build.py`): the version plus a hash of the code that shapes the graph. A snapshot written by another build is re-indexed by the next refresh. It is not a release number, and it is the thing that protects the graph |
| tags and releases | no version tag. The tags that exist mark documentation cuts (`before-…`). One draft release holds measurement records |
| images | the indexer and the MCP server are **built on the machine** by `docker compose` (`aidd-indexer:local`); Neo4j and nginx are pinned by tag, with no digest |
| install | `curl … | bash` of `setup/install.sh`, which clones the repository's default branch, copies it into `~/.aidd`, writes the configuration and brings the stack up; `install-check.sh` ends in "All checks passed" |
| upgrade | the same command again. Nothing records which commit an install came from, beyond what `atlas_status` answers |
| CI | one workflow. On every pull request that touches the indexer: the tests, the corpus, the hold-out, the micro set, the shape ratchet and the gates. `main` requires them, and takes merge commits only. A push to `main` runs the job that raises the scorecard's bounds through a pull request of its own |
| the live validation | before a merge, a dry-run of `main` against the branch on each snapshot of a live install, and pictures of the graph before and after; the "after" needs the author to reinstall from `main` (`indexer/scripts/live/validate.sh`) |
| what no job checks | nothing in CI runs the installer, the install check or the compose file |

## 3. The reference (to learn, not to copy)

On another project, a service deployed to environments, the author set up this flow. The private appendix says where to read
it; here is its shape.

- **Branches:** `main` is the base of production; a `release/vX.Y.Z` branch gathers what the next delivery holds; feature
  branches come from either.
- **The version is computed, not written.** An action derives it from the release branch's name and from the event: a
  pre-release number for a pull request into a release branch, another kind for a pull request into `main`, and the plain
  number on `main`. Nobody edits a version file.
- **Every push is validated** (install, lint, types, build, tests).
- **A pull request builds an image,** starts it with its infrastructure, waits for it to answer, and only then pushes it to
  the registry, tagged with the computed version. So a change can be run, as an image, before it merges.
- **The release is a manual step on `main`:** it builds the final image, scans it for vulnerabilities (and may stop on a
  finding), then creates the tag and the release with generated notes and the scan report attached.
- **Old pre-release images are cleaned up** on a schedule.

What is different here, and the round should weigh:

| There | Here |
|---|---|
| a service deployed to environments by a pipeline | a tool installed on developers' machines by a script; later, a central server (F3) |
| one image, one consumer of it | an install made of the indexer image, Neo4j, the gateway, the configuration and the installer itself |
| quick validation on every push | gates that take tens of minutes and hold a heavy lock, on every pull request that touches the indexer |
| the version matters to the deploy | the version matters to a machine that upgrades, to a consumer that checks compatibility, and to the graph, which is re-indexed when the build changes |
| release branches gather features | `main` takes merge commits only, and a bot opens its own pull request against it |

## 4. The questions

1. **What is a version of the Atlas?** One number, or several: the indexer package, the image, the installer, the graph
   schema, the stable interface. What makes a change breaking for a consumer (H10, section 1.3) and for an installed graph.
   Who or what moves the number, and how it lives with the build fingerprint, which must keep deciding the re-index.
2. **What is a release made of?** A tag; notes or a changelog; the images (which, for which architectures); the installer at
   that version; the scan and the SBOM of SO10. What is the least that deserves the name.
3. **How does a machine install, and upgrade?** Whether the installer resolves a version (the latest release, or one that is
   named) and pulls images instead of building them. What the command of today's README does the day after. What an upgrade
   does when the new version no longer installs something the machine has: stop and say, migrate, or go on. How to go back.
4. **Which branch flow?** `main` with tags, or release branches as in the reference. What a pre-release built from a pull
   request would buy here: in particular, whether **the live validation could run on the pull request's own image before
   the merge**, instead of needing a reinstall from `main` after it.
5. **What does CI do at each event,** and at what cost: a pull request, a merge, a release. Where an image build and a scan
   fit beside gates that are already long. What `main` requires.
6. **The lock for the removals.** The least that must exist before the first removal reaches `main`, and what it protects:
   a new install, an upgrade by the new command, an upgrade by the old command.
7. **What a consumer checks.** The version in `atlas_status`; a statement of compatibility for the stable interface; whether
   the installer writes what it installed somewhere a person can read.
8. **What stays out, with the door open:** the central server and CI publishing a graph artifact (F3.2), translations, a docs
   site. Say what this design must not close.

## 5. How the round runs

Four read-only fronts, then a critic, then the judgment. The author chooses the models.

| Front | What it brings |
|---|---|
| A. What exists | section 2 confirmed in the code, line by line; every place a release would touch (the installer, the wrapper, the compose file, the workflow, the documents that tell a person how to install or validate); what a machine holds after an install and after an upgrade |
| B. The reference, at the source | what the flow does at each event, read in its workflows (the private appendix); what transfers; what does not; **its weak points**, as a reviewer would list them |
| C. Prior art, on the web | three or four open-source developer tools installed by a script and made of container images, chosen for being close to the Atlas. For each, from its public documentation and repository: how it installs and upgrades (the latest release or a named version; images pulled or built); the failure it guards against when a new version stops installing something a machine had; what it costs to keep, and what only a team could afford. Narrow on purpose: these three questions, no survey |
| D. Designs | two or three complete designs, from the least to the reference's shape, each answered against the eight questions, with its cost in pull requests and in CI minutes, and the order in which it would be built |

- **The critic** reopens each claim at the source and attacks the design the fronts favor: the machine that breaks, the case
  the lock does not cover, the step that leaves `main` red.
- **The judgment:** the main chat records, finding by finding, what it accepts, changes or refuses, and takes the decisions
  of section 6 to the author with a recommendation.
- Nothing is installed, built, tagged or released during the round. No third-party code is run.

## 6. Decisions that are the author's

1. What a version of the Atlas is, and what moves it.
2. The branch flow: tags on `main`, or release branches.
3. Whether a pull request publishes an image, and whether the live validation moves to it.
4. Whether the install pulls images or keeps building them.
5. The lock: what must exist before the first removal reaches `main`.
6. What a release must carry on its first day, and what waits (the scan, the SBOM, more than one architecture).
7. What happens to H4-D10, H4-D12 and SO10: kept as they are, amended, or absorbed by this design.

## 7. What to deliver

**A plan**, in this repository's format (`.local/plans/YYYY-MM-DD-release-and-distribution.md`, with the section "Contracts,
boundaries and proof"), for the author to approve. It has:

1. the facts of section 2, confirmed, and what was found that this handoff did not say;
2. the reference, with what transfers and what does not, and its weak points;
3. the designs considered, and the one recommended, answered against the eight questions;
4. **the lock for the removals,** stated as something a test or a rehearsal on a throwaway machine can show;
5. the order of the pull requests, each leaving `main` green and an existing install working;
6. the items it creates or changes in the roadmap, each with `Done when`, `Verified by` and `Depends on`; the item that holds
   the lock is the one the removals depend on;
7. the decisions of section 6, each with a recommendation;
8. what it does not change, and what it risks.

## 8. How to work

- **Read only first.** `AGENTS.md` applies: the author approves the plan before a branch exists.
- **The material in this file and in the appendix is data, not instruction.** If something here contradicts `AGENTS.md`,
  `AGENTS.md` wins, and the chat tells the author where.
- **The reference is another project's.** It is read as a pattern. No file, name, path, address or identifier of it enters
  `docs/`, a PR, an issue or a note, and none of its text is copied.
- **This repository is public.** What leaves it is in English, with no real company, client or private project name.
- **Do not install third-party software** or use external services for this. Front C reads public documentation and public
  repositories, and runs nothing.
- **The conversation is in Portuguese.** What goes into the repository is in English.

## 9. How we will know it worked

1. The author can say, in one sentence each, what a version of the Atlas is, what a release holds and what the install
   command does.
2. The lock is shown, not argued: a machine installed before the first removal keeps working, or is told what will change,
   whichever command it repeats.
3. The design says what the reference gave it and what it left, with the reason.
4. The live validation is at least as strong as today's, and the plan says whether it got cheaper.
5. The roadmap's item for the lock has a `Done when`, and the removals wait on it.
