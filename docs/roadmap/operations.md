# Operations — roadmap

> How the Atlas is installed, released, refreshed and kept safe. The installation and release items are here; the
> refresh (`U`) and security and operations (SO7 to SO15) items are still in `docs/ROADMAP.md`. The fields are
> H10-D2's.

## Installation and release

- [ ] SO16 The installer merges its entries into a repository's MCP configuration; today it replaces the whole file
  - **Done when:** the installer merges, by name, the entries of the template of the tree it installs, and never
    removes or edits another one; an entry of the same name with another address is kept, and the run says so; a run
    on a repository whose `.mcp.json` has another server keeps that entry
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N2
- [ ] SO17 A CI job checks the install; today a pull request that touches only `setup/`, the compose file or the
  gateway runs no check of them
  - **Done when:** the job `install` runs on every pull request, and its first step decides whether there is something
    to check: a change to `setup/`, `docker-compose.yml`, `gateway/`, `neo4j/`, a `Dockerfile`, `CHANGELOG.md`, a
    folder the installer copies, or the workflow itself. Then it checks the syntax of the scripts and of the compose
    file and runs the tests of `setup/`. `main` requires the job: the author adds it to the ruleset once it is on `main`
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] SO18 A release is published by a pull request that moves the line of the entry script naming it
  - **Done when:** a pull request that changes the release the entry script names changes nothing else, and it either
    raises the line or takes it back to the value it had just before. Raising, its check refuses a name that is not a
    `vX.Y.Z` tag on the first-parent history of `main` or of a maintenance branch `maint/X.Y`, a version not above the
    one the line names, a version with no dated section in `CHANGELOG.md`, and a version that drops a service or
    changes the image of a service with a volume without an incompatible step. A release of an older line joins the
    list of published releases without moving the line. The check computes the build the tag gives and refuses a pull
    request that records another one. A workflow started by hand takes a version and a commit, runs those checks and
    the part of the rehearsal that fits a runner, computes the build and opens that pull request; the script it runs
    also runs on a machine. The tag is the author's, signed, and the merge is what publishes. `docs/indexer/method.md`
    says what a release is and who publishes one
  - **Verified by:** anyone
  - **Depends on:** N1, SO17
- [ ] SO19 The release a consumer checks; today `atlas_status` answers the indexer's version and build, not the release
  installed
  - **Done when:** `atlas_status` and `/healthz` answer the installed release under a name of its own, read from the
    environment; a test shows `indexer_build()` is the same with and without it; no command is added to `cli.py`;
    `install-check.sh` warns when the running build is not the one the release recorded; `indexer/pyproject.toml` and
    `INDEXER_VERSION` agree, and a test says so; `docs/atlas-interface.md` says what a consumer may rely on within one
    version line, which field to compare, and that the compose project name is the Atlas's
  - **Verified by:** anyone
  - **Depends on:** N1, F1.21
- [ ] SO20 The live validation closes before the merge, from an install made from a checkout of the pull request
  - **Done when:** `docs/indexer/method.md` §4.7 to §4.9 and §4.17, and the pull request template, describe the round
    with the install made from a checkout of the pull request, up to date with `main`, one pull request at a time; a
    new step of `validate.sh` passes when what an install reads (the folders the installer copies, the compose file and
    `setup/`) is the same in the merged tree and in the validated one, and otherwise says which paths differ and what
    the round then costs; one pull request was validated both ways, with the same counts; one command on the author's
    machine chains the checkout of `main`, the reinstall and the `after` step
  - **Verified by:** the author (the live validation runs on his install)
  - **Depends on:** N2
- [ ] SO21 A published image per release, which carries H4-D10's proposal into this repository. It starts when one of
  these holds: F3.1 or F3.2 starts; an install must not build; the build of a new release fails on real machines
  - **Sketch:** missing where the image is published, for which architectures, and how an install picks between
    pulling it and building it; first step: the compose file reads the indexer image from a variable, and the image
    carries its release and commit as labels
  - **Verified by:** the author (whether a trigger holds is his call)
  - **Depends on:** SO18
- [ ] SO22 The install rehearsed in CI: a job installs the tree on a runner and ends in "All checks passed", and runs
  the rehearsal when a pull request drops a service or moves the release the entry script names
  - **Sketch:** missing whether the stack installs on a hosted runner, and where the rehearsal runs if it does not;
    first step: find out whether the stack installs on a hosted runner
  - **Verified by:** anyone
  - **Depends on:** N1
