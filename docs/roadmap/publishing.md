# Publishing and documentation — roadmap

> The repository is public. These items give it documentation for newcomers, in English and the languages H4
> proposes, a contributor path, and a repository of its own; most of their proposals are in
> `docs/handoffs/H4-public-docs.md`. The fields are H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

- [ ] P0 Recycle the working docs (H4 step 0, asked for on 2026-10-18): the current truth separated from history; an
  `AGENTS.md` at the root as the entry point for a contributor and their AI; the ROADMAP log condensed into
  `docs/history.md`; the decisions distilled into `docs/decisions.md`; the corpus report with only the method, the
  current baseline and the gaps; from ~600 KB to a ceiling per growth file (`indexer/scripts/checks/docs_ceilings.txt`), with no total. Phase 0a done on 2026-10-19, with every doc in
  English (H4-D1); phase 0b (the extractor guide, rewritten in English) after H5
  - **Done when:** no file of `docs/` is in Portuguese (the indexer guide rewritten in English, or replaced by pages in
    English), and `AGENTS.md` names none
  - **Verified by:** anyone
  - **Depends on:** F1.17
  - **In progress:** H4
- [ ] P1 Redecide H4 with the premise (H10-D1): the H4 proposals that H10-D1 and H11-D1 left open, for the one
  repository, reviewers per language, and a sketch of the docs architecture
  - **Done when:** the H4 section of `docs/decisions.md` holds no proposal: each row is decided by the author, marked
    superseded or moot, or tied to the open item that decides what is left of it; H4 says who reviews each language's
    translation, or that it stays marked as machine translation; one list in `docs/handoffs/H4-public-docs.md` puts each
    file of `docs/` in one of three classes: what someone from outside needs to clone the project and follow its
    reasoning, a record (as `docs/history.md`, `docs/decisions.md` and `docs/corpus-report.md`), or what leaves, with
    the item that takes it out; and the resume test (`docs/indexer/resume-test.md`) passes every criterion of its §3
    with a reading order whose files in `docs/` are all of the first class
  - **Verified by:** the author (the decisions are his, and the resume test runs on his account)
  - **Depends on:** nothing
- [ ] P2 **The Atlas in its own repository**, named `aidd-atlas` (H10-D1), after the release of the reduced Atlas:
  whether it is a new repository born from one commit with the reduced tree or this one renamed, where the history
  stays, how the new tree is proven, and, if it is a new one, how the install entry passes to it are its design. This
  repository is never deleted or made private
  - **Sketch:** missing the four choices the text names, and, if the new repository is born from one commit, what
    becomes of the rules of `docs/indexer/method.md` that expect a split to carry the history (the merge commit's body,
    the pointers by tag, the template that moves by itself); first step: list what names this repository or points into
    its history (the install address of each release, the `#NN` references, the `git show` pointers) and what each
    choice does to each
  - **Verified by:** the author (the repository's name and settings are his)
  - **Depends on:** N11
  - **Not to do:** give this repository's name to another one before the install entry has moved and this repository's
    last release has said so, or serve under that name an entry script that installs anything but a pointer to where the
    Atlas went; rewrite this repository's history, whose hashes the docs cite
- [ ] P3 English content for the repository (README + `docs/en/`), validated by someone who has never seen the project
  - **Done when:** a reader who has never seen the project, a person or a new agent session given only the README and
    the English pages it links to, installs the Atlas and gets an answer from `atlas_status` and `repo_map` on a
    repository of their own, without help
  - **Verified by:** the author (he finds the reader and watches the run; no CI job installs the stack)
  - **Depends on:** P0, P1
- [ ] P3.1 The contributor path (H4.1, `docs/handoffs/H4.1-contributor-path.md`): `CONTRIBUTING.md`, playbooks per
  contribution type, the method explained, PR and issue templates, the method's checks in CI, and an acceptance test
  in which a fresh agent re-enacts past increments and follows the method on its own
  - **Done when:** the acceptance test of `docs/handoffs/H4.1-contributor-path.md` passes: each of its five tasks shows
    its behaviors in two runs of a fresh agent session, scored by a person
  - **Verified by:** the author (a person scores the runs; a model does not judge its own)
  - **Depends on:** P0, P1
- [ ] P4 Languages: a glossary, a style guide, `i18n_check.py` in CI; translations per tier into pt-BR, es and zh-CN
  - **Sketch:** missing which pages each language gets and what `i18n_check.py` checks, which H4's open proposals decide
    (the locales, the tiers); first step: the glossary's terms kept in English in every language, taken from the names
    `docs/atlas-interface.md` promises
  - **Verified by:** anyone
  - **Depends on:** P3
- [ ] P5 Visual assets (manifest `docs/assets/README.md`), community files and GitHub settings for the repository; its
  releases follow H11-D1
  - **Sketch:** missing the list of community files and settings; first step: H4's list of community files and of the
    settings that live outside a file (`docs/handoffs/H4-public-docs.md`), each kept, changed or dropped for the one
    repository
  - **Verified by:** the author (the repository's settings are his)
  - **Depends on:** P3
- [ ] P6 *(optional)* A docs site, when navigation calls for it
  - **Sketch:** missing what says navigation calls for a site, and where it is served; first step: the pages of
    `docs/en/`, each with how many links away from the README it is
  - **Verified by:** the author (whether navigation calls for a site is his call)
  - **Depends on:** P3
